import logging
import os
import sys
import time
import traceback
from typing import Any, Dict


LOGGER_NAME = "ai_news_agentic"
LOG_FILE = os.path.join("logs", "ai_news.log")


def get_ai_news_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def start_timer() -> float:
    return time.perf_counter()


def elapsed_seconds(start_time: float) -> float:
    return time.perf_counter() - start_time


def summarize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    categorized_articles = state.get("categorized_articles", {})
    messages = state.get("messages", [])
    markdown_report = state.get("markdown_report", "")

    return {
        "frequency": state.get("frequency"),
        "messages_count": len(messages) if isinstance(messages, list) else 1,
        "raw_articles_count": len(state.get("raw_articles", [])),
        "skipped_articles_count": len(state.get("skipped_articles", [])),
        "verified_articles_count": len(state.get("verified_articles", [])),
        "categories_count": len(categorized_articles),
        "categories": list(categorized_articles.keys()) if isinstance(categorized_articles, dict) else [],
        "markdown_report_chars": len(markdown_report or ""),
        "review_status": state.get("review_status"),
        "reviewer_feedback": state.get("reviewer_feedback"),
        "revision_count": state.get("revision_count"),
        "filename": state.get("filename"),
        "workflow_status": state.get("workflow_status"),
        "errors": state.get("errors", []),
        "no_new_articles": state.get("no_new_articles"),
        "memory_skipped_count": state.get("memory_skipped_count"),
        "memory_stored_count": state.get("memory_stored_count"),
    }


def log_agent_started(logger: logging.Logger, agent_name: str, state: Dict[str, Any]) -> float:
    logger.info("[%s] Started", agent_name)
    logger.info("[%s] Current state: %s", agent_name, summarize_state(state))
    return start_timer()


def log_agent_finished(logger: logging.Logger, agent_name: str, start_time: float) -> None:
    logger.info("[%s] Finished in %.2f seconds", agent_name, elapsed_seconds(start_time))


def log_agent_exception(logger: logging.Logger, agent_name: str, state: Dict[str, Any]) -> None:
    logger.error("[%s] Exception occurred", agent_name)
    logger.error("[%s] Current graph state: %s", agent_name, summarize_state(state))
    logger.error("[%s] Full traceback:\n%s", agent_name, traceback.format_exc())
