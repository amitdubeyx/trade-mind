"""
News Fetcher module for TradeMind
Fetches latest public news about companies and indices via Google News RSS.
"""
from typing import List, Dict, Any
import urllib.parse
import feedparser
import requests
from bs4 import BeautifulSoup

from src.settings import (
    HTTP_TIMEOUT_SECONDS,
    NEWS_COUNTRY,
    NEWS_EDITION,
    NEWS_LANGUAGE,
    NEWS_MAX_ITEMS,
    NEWS_QUERY_SUFFIX,
    NEWS_SUMMARY_MAX_CHARS,
)

def clean_html(text: str) -> str:
    """Removes HTML tags from RSS summaries/titles."""
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return " ".join(soup.get_text(separator=" ").split())

def fetch_company_news(query: str, max_items: int = NEWS_MAX_ITEMS) -> List[Dict[str, Any]]:
    """
    Fetches latest news from Google News RSS for India/English.
    Args:
        query: Company or index name (e.g. 'Nifty 50', 'Reliance Industries share')
        max_items: Number of articles to return
    Returns:
        List of dicts with 'title', 'link', 'published', 'source', 'summary'
    """
    clean_query = query.strip()
    if not clean_query:
        return []

    try:
        item_limit = max(0, min(int(max_items), 50))
    except (TypeError, ValueError):
        item_limit = NEWS_MAX_ITEMS
    if item_limit == 0:
        return []

    search_term = f"{clean_query} {NEWS_QUERY_SUFFIX}".strip()
    query_params = urllib.parse.urlencode(
        {
            "q": search_term,
            "hl": NEWS_LANGUAGE,
            "gl": NEWS_COUNTRY,
            "ceid": NEWS_EDITION,
        }
    )
    rss_url = f"https://news.google.com/rss/search?{query_params}"

    news_list = []
    seen = set()
    try:
        response = requests.get(
            rss_url,
            headers={"User-Agent": "TradeMind/0.1 (+https://news.google.com)"},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        for entry in feed.entries:
            title = clean_html(entry.get("title", ""))
            link = entry.get("link", "")
            identity = (title.casefold(), link)
            if not title or identity in seen:
                continue
            seen.add(identity)

            published = clean_html(entry.get("published", "") or entry.get("updated", ""))
            # RSS summaries often contain a full article excerpt and repeated
            # markup. Keep enough context for the UI/LLM without bloating the
            # prompt or rendering a wall of text.
            summary = clean_html(entry.get("summary", ""))[:NEWS_SUMMARY_MAX_CHARS]

            raw_source = entry.get("source", {})
            if isinstance(raw_source, dict):
                source = raw_source.get("title", "Google News")
            else:
                source = str(raw_source or "Google News")

            # Fallback source extract from title if formatted as "Title - Source"
            if " - " in title and (not source or source == "Google News"):
                parts = title.rsplit(" - ", 1)
                title = parts[0]
                source = parts[1]

            news_list.append({
                "title": title,
                "link": link,
                "published": published,
                "source": source,
                "summary": summary
            })
            if len(news_list) >= item_limit:
                break

    except (requests.RequestException, ValueError, TypeError):
        # News is an optional enrichment. A provider outage should leave the
        # price/technical dashboard usable and simply produce an empty feed.
        return []

    return news_list
