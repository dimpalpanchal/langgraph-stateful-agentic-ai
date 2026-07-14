import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple


class NewsMemoryManager:
    """
    JSON-backed memory for published AI news articles.
    """

    def __init__(self, memory_file: str = "./memory/news_memory.json"):
        self.memory_file = memory_file
        os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)

    def load_memory(self) -> Dict[str, Any]:
        if not os.path.exists(self.memory_file):
            return {"published_articles": []}

        with open(self.memory_file, "r", encoding="utf-8") as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                data = {"published_articles": []}

        if "published_articles" not in data or not isinstance(data["published_articles"], list):
            data["published_articles"] = []

        return data

    def save_memory(self, memory: Dict[str, Any]) -> None:
        with open(self.memory_file, "w", encoding="utf-8") as file:
            json.dump(memory, file, indent=2, ensure_ascii=False)

    def article_hash(self, article: Dict[str, Any]) -> str:
        source = "|".join(
            [
                str(article.get("title", "")).strip().lower(),
                str(article.get("url", "")).strip().lower(),
                str(article.get("published_date", "")).strip().lower(),
            ]
        )
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    def filter_new_articles(self, articles: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        memory = self.load_memory()
        published_articles = memory.get("published_articles", [])
        published_urls = {
            str(article.get("url", "")).strip().lower()
            for article in published_articles
            if article.get("url")
        }
        published_hashes = {
            str(article.get("article_hash", "")).strip()
            for article in published_articles
            if article.get("article_hash")
        }

        new_articles = []
        skipped_articles = []

        for article in articles:
            url = str(article.get("url", "")).strip().lower()
            article_hash = self.article_hash(article)

            if url in published_urls or article_hash in published_hashes:
                skipped_articles.append(article)
                continue

            new_articles.append(article)

        return new_articles, skipped_articles

    def store_published_articles(
        self,
        categorized_articles: Dict[str, List[Dict[str, Any]]],
    ) -> int:
        memory = self.load_memory()
        published_articles = memory.get("published_articles", [])
        existing_urls = {
            str(article.get("url", "")).strip().lower()
            for article in published_articles
            if article.get("url")
        }
        existing_hashes = {
            str(article.get("article_hash", "")).strip()
            for article in published_articles
            if article.get("article_hash")
        }

        stored_count = 0
        processed_timestamp = datetime.now(timezone.utc).isoformat()

        for category, articles in categorized_articles.items():
            for article in articles:
                article_hash = self.article_hash(article)
                url = str(article.get("url", "")).strip().lower()

                if url in existing_urls or article_hash in existing_hashes:
                    continue

                published_articles.append(
                    {
                        "title": article.get("title", ""),
                        "url": article.get("url", ""),
                        "published_date": article.get("published_date", ""),
                        "processed_timestamp": processed_timestamp,
                        "category": category,
                        "article_hash": article_hash,
                    }
                )
                existing_urls.add(url)
                existing_hashes.add(article_hash)
                stored_count += 1

        memory["published_articles"] = published_articles
        self.save_memory(memory)
        return stored_count
