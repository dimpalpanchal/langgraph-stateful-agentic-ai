import os
from typing import Any, Dict, List
from urllib.parse import urlparse

from langchain_core.prompts import ChatPromptTemplate
from tavily import TavilyClient

from memory.memory_manager import NewsMemoryManager
from src.langgraphagenticai.state.state import NewsState
from src.langgraphagenticai.utils.logging_utils import (
    get_ai_news_logger,
    log_agent_exception,
    log_agent_finished,
    log_agent_started,
)


logger = get_ai_news_logger()


def _message_content(message: Any) -> str:
    if hasattr(message, "content"):
        return str(message.content)
    return str(message)


def _normalize_frequency(state: NewsState) -> str:
    frequency = state.get("frequency")
    if not frequency:
        messages = state.get("messages", [])
        if messages:
            frequency = _message_content(messages[0])
    frequency = (frequency or "daily").strip().lower()
    aliases = {
        "day": "daily",
        "daily": "daily",
        "week": "weekly",
        "weekly": "weekly",
        "month": "monthly",
        "monthly": "monthly",
        "year": "year",
        "yearly": "year",
    }
    return aliases.get(frequency, "daily")


def _deduplicate_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    unique_articles = []
    seen_urls = set()

    for article in articles:
        url = (article.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        unique_articles.append(article)

    return unique_articles


def _article_to_text(article: Dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Title: {article.get('title', '')}",
            f"Content: {article.get('content', '')}",
            f"URL: {article.get('url', '')}",
            f"Date: {article.get('published_date', '')}",
        ]
    )


class SupervisorAgent:
    """
    Initializes the AI News workflow state and defines the execution order.
    """

    def plan(self, state: NewsState) -> Dict[str, Any]:
        start_time = log_agent_started(logger, "Supervisor", state)
        try:
            frequency = _normalize_frequency(state)
            logger.info("[Supervisor] Normalized frequency: %s", frequency)
            logger.info("[Supervisor] Routing to Research Agent")

            result = {
                "frequency": frequency,
                "raw_articles": [],
                "skipped_articles": [],
                "verified_articles": [],
                "categorized_articles": {},
                "markdown_report": "",
                "review_status": "pending",
                "reviewer_feedback": "",
                "revision_count": 0,
                "workflow_status": "supervisor_planned",
                "errors": [],
                "no_new_articles": False,
                "memory_skipped_count": 0,
                "memory_stored_count": 0,
            }
            logger.info("[Supervisor] State updates: frequency=%s, workflow_status=%s", frequency, result["workflow_status"])
            log_agent_finished(logger, "Supervisor", start_time)
            return result
        except Exception:
            log_agent_exception(logger, "Supervisor", state)
            raise


class ResearchAgent:
    """
    Fetches AI news from Tavily and removes duplicate URLs.
    """

    def __init__(self):
        self.tavily = TavilyClient()
        self.memory_manager = NewsMemoryManager()

    def research(self, state: NewsState) -> Dict[str, Any]:
        start_time = log_agent_started(logger, "Research", state)
        try:
            frequency = _normalize_frequency(state)
            time_range_map = {"daily": "d", "weekly": "w", "monthly": "m", "year": "y"}
            days_map = {"daily": 1, "weekly": 7, "monthly": 30, "year": 366}

            response = self.tavily.search(
                query="Top Artificial Intelligence (AI) technology news India and globally",
                topic="news",
                time_range=time_range_map[frequency],
                include_answer="advanced",
                max_results=20,
                days=days_map[frequency],
            )

            retrieved_articles = response.get("results", [])
            deduplicated_articles = _deduplicate_articles(retrieved_articles)
            duplicates_removed = len(retrieved_articles) - len(deduplicated_articles)
            memory = self.memory_manager.load_memory()
            logger.info("[Memory] Memory loaded with %s published articles", len(memory.get("published_articles", [])))
            raw_articles, skipped_articles = self.memory_manager.filter_new_articles(deduplicated_articles)
            no_new_articles = len(raw_articles) == 0
            logger.info("[Research] Retrieved %s articles", len(retrieved_articles))
            logger.info("[Research] Removed %s duplicate URLs", duplicates_removed)
            logger.info("[Memory] Articles skipped: %s", len(skipped_articles))
            if no_new_articles:
                logger.info("[Research] No new AI news found")
            logger.info("[Research] State updates: raw_articles=%s, skipped_articles=%s, no_new_articles=%s, workflow_status=research_complete", len(raw_articles), len(skipped_articles), no_new_articles)
            log_agent_finished(logger, "Research", start_time)
            return {
                "frequency": frequency,
                "raw_articles": raw_articles,
                "skipped_articles": skipped_articles,
                "no_new_articles": no_new_articles,
                "memory_skipped_count": len(skipped_articles),
                "workflow_status": "research_complete",
            }
        except Exception:
            log_agent_exception(logger, "Research", state)
            raise


class FactCheckerAgent:
    """
    Performs lightweight reliability checks before articles reach the writer.
    """

    blocked_domains = {"localhost", "example.com"}

    def verify(self, state: NewsState) -> Dict[str, Any]:
        start_time = log_agent_started(logger, "Fact Checker", state)
        try:
            verified_articles = []
            errors = list(state.get("errors", []))
            raw_articles = _deduplicate_articles(state.get("raw_articles", []))

            if state.get("no_new_articles"):
                logger.info("[Fact Checker] No new articles to process")
                log_agent_finished(logger, "Fact Checker", start_time)
                return {
                    "verified_articles": [],
                    "errors": errors,
                    "workflow_status": "fact_check_skipped_no_new_articles",
                }

            for article in raw_articles:
                url = (article.get("url") or "").strip()
                parsed_url = urlparse(url)
                domain = parsed_url.netloc.lower().replace("www.", "")
                content = (article.get("content") or article.get("title") or "").strip()

                if parsed_url.scheme not in {"http", "https"} or not domain:
                    continue
                if domain in self.blocked_domains:
                    continue
                if not content:
                    continue

                verified_articles.append(article)

            rejected_articles = len(raw_articles) - len(verified_articles)
            if not verified_articles:
                errors.append("No verified articles were available after fact checking.")

            logger.info("[Fact Checker] Processed %s articles", len(raw_articles))
            logger.info("[Fact Checker] Approved %s articles", len(verified_articles))
            logger.info("[Fact Checker] Rejected %s articles", rejected_articles)
            logger.info("[Fact Checker] State updates: verified_articles=%s, errors=%s", len(verified_articles), len(errors))
            log_agent_finished(logger, "Fact Checker", start_time)
            return {
                "verified_articles": verified_articles,
                "errors": errors,
                "workflow_status": "fact_check_complete",
            }
        except Exception:
            log_agent_exception(logger, "Fact Checker", state)
            raise


class CategorizerAgent:
    """
    Groups verified news articles into practical AI-news categories.
    """

    category_keywords = {
        "Business and Funding": ["funding", "revenue", "startup", "earnings", "investment", "market", "stock"],
        "Products and Platforms": ["launch", "product", "platform", "model", "tool", "feature", "app"],
        "Policy and Safety": ["regulation", "law", "policy", "safety", "risk", "copyright", "lawsuit"],
        "Research and Infrastructure": ["research", "chip", "data center", "infrastructure", "compute", "benchmark"],
    }

    def categorize(self, state: NewsState) -> Dict[str, Any]:
        start_time = log_agent_started(logger, "Categorizer", state)
        try:
            categorized_articles = {category: [] for category in self.category_keywords}
            categorized_articles["General AI News"] = []
            verified_articles = state.get("verified_articles", [])

            if state.get("no_new_articles"):
                logger.info("[Categorizer] No new articles to categorize")
                log_agent_finished(logger, "Categorizer", start_time)
                return {
                    "categorized_articles": {},
                    "workflow_status": "categorization_skipped_no_new_articles",
                }

            for article in verified_articles:
                searchable_text = " ".join(
                    [
                        str(article.get("title", "")),
                        str(article.get("content", "")),
                    ]
                ).lower()

                matched_category = "General AI News"
                for category, keywords in self.category_keywords.items():
                    if any(keyword in searchable_text for keyword in keywords):
                        matched_category = category
                        break

                categorized_articles[matched_category].append(article)

            categorized_articles = {
                category: articles
                for category, articles in categorized_articles.items()
                if articles
            }

            logger.info("[Categorizer] Processed %s articles", len(verified_articles))
            logger.info("[Categorizer] Created %s categories", len(categorized_articles))
            logger.info("[Categorizer] State updates: categories=%s", list(categorized_articles.keys()))
            log_agent_finished(logger, "Categorizer", start_time)
            return {
                "categorized_articles": categorized_articles,
                "workflow_status": "categorization_complete",
            }
        except Exception:
            log_agent_exception(logger, "Categorizer", state)
            raise


class WriterAgent:
    """
    Generates the markdown AI news report with the configured LLM.
    """

    def __init__(self, llm):
        self.llm = llm

    def write(self, state: NewsState) -> Dict[str, Any]:
        start_time = log_agent_started(logger, "Writer", state)
        try:
            frequency = _normalize_frequency(state)
            categorized_articles = state.get("categorized_articles", {})
            revision_count = state.get("revision_count", 0)
            reviewer_feedback = state.get("reviewer_feedback", "")
            previous_markdown_report = state.get("markdown_report", "")
            is_revision = bool(reviewer_feedback and previous_markdown_report)

            if state.get("no_new_articles"):
                markdown_report = "No new AI news found."
                logger.info("[Writer] No new articles found; returning no-news message")
                logger.info("[Writer] State updates: markdown_report_chars=%s, revision_count=%s", len(markdown_report), revision_count)
                log_agent_finished(logger, "Writer", start_time)
                return {
                    "markdown_report": markdown_report,
                    "revision_count": revision_count,
                    "workflow_status": "writing_skipped_no_new_articles",
                }

            if reviewer_feedback:
                revision_count += 1

            articles_by_category = []
            for category, articles in categorized_articles.items():
                article_text = "\n\n".join(_article_to_text(article) for article in articles)
                articles_by_category.append(f"## {category}\n{article_text}")

            source_text = "\n\n".join(articles_by_category) or "No verified articles were available."

            if is_revision:
                prompt_template = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            """You are the Writer Agent revising an existing AI news report.
Improve the existing draft based on the reviewer feedback.
Preserve strong sections and only improve weak or missing areas.
Use the provided articles only as source material.
Do not invent articles, URLs, dates, companies, or claims.
Keep clear markdown headings.""",
                        ),
                        (
                            "user",
                            """Timeframe: {frequency}
Current revision number: {revision_count}

Reviewer feedback:
{feedback}

Previous markdown draft:
{previous_draft}

Source articles for verification and missing detail:
{articles}

Revise the previous markdown draft. Preserve good sections and improve only the areas identified by the reviewer.""",
                        ),
                    ]
                )
                prompt = prompt_template.format(
                    frequency=frequency,
                    revision_count=revision_count,
                    feedback=reviewer_feedback,
                    previous_draft=previous_markdown_report,
                    articles=source_text,
                )
                logger.info("[Writer] Revising existing markdown report")
                logger.info("[Writer] Using previous draft and reviewer feedback for revision")
                logger.info(
                    "[Writer] Revision context: previous_draft_chars=%s, feedback_chars=%s, revision_count=%s",
                    len(previous_markdown_report),
                    len(reviewer_feedback),
                    revision_count,
                )
            else:
                prompt_template = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            """You are the Writer Agent for an AI news report.
Create a professional markdown report using only the provided articles.
Requirements:
- Start with a short executive summary.
- Group articles by the provided categories.
- For each article include a concise summary and source link.
- Preserve dates when available.
- Do not invent articles, URLs, dates, companies, or claims.
- Use clear markdown headings.""",
                        ),
                        (
                            "user",
                            "Timeframe: {frequency}\nReviewer feedback to address: {feedback}\n\nArticles:\n{articles}",
                        ),
                    ]
                )
                prompt = prompt_template.format(
                    frequency=frequency,
                    feedback=reviewer_feedback or "None",
                    articles=source_text,
                )

            response = self.llm.invoke(prompt)

            logger.info("[Writer] Processed %s categories", len(categorized_articles))
            logger.info("[Writer] Generated markdown report")
            logger.info("[Writer] State updates: markdown_report_chars=%s, revision_count=%s", len(response.content), revision_count)
            log_agent_finished(logger, "Writer", start_time)
            return {
                "markdown_report": response.content,
                "revision_count": revision_count,
                "workflow_status": "writing_complete",
            }
        except Exception:
            log_agent_exception(logger, "Writer", state)
            raise


class ReviewerAgent:
    """
    Reviews the generated markdown and approves or requests one revision.
    """

    def review(self, state: NewsState) -> Dict[str, Any]:
        start_time = log_agent_started(logger, "Reviewer", state)
        try:
            markdown_report = (state.get("markdown_report") or "").strip()
            verified_articles = state.get("verified_articles", [])
            revision_count = state.get("revision_count", 0)
            feedback = []

            if not markdown_report:
                feedback.append("The report is empty.")
            if verified_articles and "http" not in markdown_report:
                feedback.append("The report should include source links.")
            if len(markdown_report) < 200 and verified_articles:
                feedback.append("The report is too short for the number of verified articles.")
            if "##" not in markdown_report and verified_articles:
                feedback.append("The report should use markdown section headings.")

            logger.info("[Reviewer] Processed report with %s characters", len(markdown_report))
            if feedback and revision_count < 1:
                logger.info("[Reviewer] Rejected report")
                logger.info("[Reviewer] Feedback: %s", " ".join(feedback))
                log_agent_finished(logger, "Reviewer", start_time)
                return {
                    "review_status": "rejected",
                    "reviewer_feedback": " ".join(feedback),
                    "workflow_status": "review_rejected",
                }

            logger.info("[Reviewer] Approved report")
            log_agent_finished(logger, "Reviewer", start_time)
            return {
                "review_status": "approved",
                "reviewer_feedback": "Approved for saving.",
                "workflow_status": "review_approved",
            }
        except Exception:
            log_agent_exception(logger, "Reviewer", state)
            raise


class SaveReportNode:
    """
    Saves the approved markdown report to the AINews output folder.
    """

    def save(self, state: NewsState) -> Dict[str, Any]:
        start_time = log_agent_started(logger, "Save", state)
        try:
            frequency = _normalize_frequency(state)
            markdown_report = state.get("markdown_report", "")
            filename = f"./AINews/{frequency}_summary.md"
            memory_manager = NewsMemoryManager()

            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "w", encoding="utf-8") as file:
                file.write(f"# {frequency.capitalize()} AI News Summary\n\n")
                file.write(markdown_report)

            memory_stored_count = 0
            if state.get("no_new_articles"):
                logger.info("[Memory] Memory update skipped because no new articles were found")
            else:
                memory_stored_count = memory_manager.store_published_articles(state.get("categorized_articles", {}))
                logger.info("[Memory] Memory updated")
                logger.info("[Memory] Articles stored: %s", memory_stored_count)

            logger.info("[Save] Processed report with %s characters", len(markdown_report))
            logger.info("[Save] Saved report to %s", filename)
            log_agent_finished(logger, "Save", start_time)
            return {
                "filename": filename,
                "memory_stored_count": memory_stored_count,
                "workflow_status": "report_saved",
            }
        except Exception:
            log_agent_exception(logger, "Save", state)
            raise


def route_after_review(state: NewsState) -> str:
    route = "save_report" if state.get("review_status") == "approved" else "writer_agent"
    logger.info("[GraphBuilder] Conditional routing decision after Reviewer: %s", route)
    return route
