"""
TrendPulse AI - Financial News Collection & Storage Service
Collects authentic financial news via Google News Financial RSS and Yahoo Finance news,
applies AI sentiment classification, and persists articles to the SQLite database.
"""

import logging
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, Any, List

import requests
import yfinance as yf

from .models import FinancialNews
from .sentiment_engine import analyze_headline_sentiment
from .stock_service import POPULAR_STOCKS

logger = logging.getLogger(__name__)

# Cache news queries in-memory for 120s to prevent spamming
_NEWS_CACHE = {}
NEWS_CACHE_TTL = 120


def _clean_text(text: str) -> str:
    """Removes HTML entities and trims whitespace."""
    if not text:
        return ""
    import html
    return html.unescape(text).strip()


def _resolve_company_name(ticker: str) -> str:
    """Gets readable search name for a ticker."""
    meta = next((s for s in POPULAR_STOCKS if s["ticker"] == ticker), None)
    if meta:
        return meta["name"]
    # If ticker has suffix like .NS, strip it
    base = ticker.replace(".NS", "").replace(".BO", "")
    return base


def fetch_news_from_google_rss(ticker: str, max_articles: int = 15) -> List[Dict[str, Any]]:
    """
    Fetches real-time financial news headlines via Google News RSS feed.
    Legitimate public RSS endpoint with publisher, date, link, and headline.
    """
    company_name = _resolve_company_name(ticker)
    clean_ticker = ticker.replace(".NS", "").replace(".BO", "")
    
    # Query prioritizing financial / stock news
    search_query = f"{company_name} {clean_ticker} stock financial"
    encoded_query = urllib.parse.quote(search_query)
    
    # Detect if Indian stock
    is_india = ".NS" in ticker or ".BO" in ticker or "India" in company_name
    hl = "en-IN" if is_india else "en-US"
    gl = "IN" if is_india else "US"
    ceid = "IN:en" if is_india else "US:en"

    url = f"https://news.google.com/rss/search?q={encoded_query}&hl={hl}&gl={gl}&ceid={ceid}"
    headers = {
        "User-Agent": "TrendPulseFinancialTracker/1.0 (Mozilla/5.0 Windows NT 10.0; Win64; x64)"
    }

    articles = []
    try:
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            items = root.findall(".//item")

            for item in items[:max_articles]:
                title_elem = item.find("title")
                link_elem = item.find("link")
                pubdate_elem = item.find("pubDate")
                source_elem = item.find("source")

                if title_elem is None or not title_elem.text:
                    continue

                full_title = _clean_text(title_elem.text)
                link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                
                # Extract publisher from <source> tag or title suffix
                publisher = "Financial Media"
                if source_elem is not None and source_elem.text:
                    publisher = _clean_text(source_elem.text)
                elif " - " in full_title:
                    parts = full_title.rsplit(" - ", 1)
                    full_title = parts[0]
                    publisher = parts[1]

                # Parse date
                pub_dt = datetime.now(timezone.utc)
                if pubdate_elem is not None and pubdate_elem.text:
                    try:
                        pub_dt = parsedate_to_datetime(pubdate_elem.text)
                        if pub_dt.tzinfo is None:
                            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                    except Exception:
                        pass

                articles.append({
                    "headline": full_title,
                    "publisher": publisher,
                    "url": link,
                    "published_at": pub_dt,
                    "summary": full_title,
                    "ticker": ticker,
                })
    except Exception as e:
        logger.warning(f"Google RSS fetch error for {ticker}: {e}")

    return articles


def fetch_news_from_yfinance(ticker: str, max_articles: int = 10) -> List[Dict[str, Any]]:
    """Fetches supplementary news via yfinance search."""
    clean_ticker = ticker.strip().upper()
    articles = []
    try:
        s = yf.Search(clean_ticker, news_count=max_articles)
        yf_news = getattr(s, "news", []) or []
        for item in yf_news:
            title = _clean_text(item.get("title", ""))
            link = item.get("link", "")
            publisher = item.get("publisher", "Yahoo Finance")
            provider_time = item.get("providerPublishTime")

            if not title or not link:
                continue

            pub_dt = datetime.fromtimestamp(provider_time, tz=timezone.utc) if provider_time else datetime.now(timezone.utc)

            articles.append({
                "headline": title,
                "publisher": publisher,
                "url": link,
                "published_at": pub_dt,
                "summary": item.get("summary", title),
                "ticker": clean_ticker,
            })
    except Exception as e:
        logger.debug(f"yfinance news error for {clean_ticker}: {e}")

    return articles


def get_and_analyze_news_for_ticker(ticker: str, limit: int = 12) -> List[Dict[str, Any]]:
    """
    Main entry point: Collects news from multiple authentic sources, deduplicates,
    runs AI sentiment analysis, saves to database, and returns processed articles.
    """
    clean_ticker = ticker.strip().upper()
    cache_key = f"analyzed_news_{clean_ticker}_{limit}"
    
    # Check cache
    cached_entry = _NEWS_CACHE.get(cache_key)
    if cached_entry and (time.time() - cached_entry["ts"]) < NEWS_CACHE_TTL:
        return cached_entry["data"]

    # 1. Fetch raw articles from Google RSS & Yahoo Finance
    raw_articles = fetch_news_from_google_rss(clean_ticker, max_articles=limit)
    if len(raw_articles) < 5:
        yf_items = fetch_news_from_yfinance(clean_ticker, max_articles=8)
        raw_articles.extend(yf_items)

    # 2. Deduplicate by URL or normalized headline
    seen_urls = set()
    seen_headlines = set()
    unique_articles = []

    for art in raw_articles:
        url = art.get("url", "")
        h_norm = art.get("headline", "").lower().strip()[:60]
        if not url or url in seen_urls or h_norm in seen_headlines:
            continue
        seen_urls.add(url)
        seen_headlines.add(h_norm)
        unique_articles.append(art)

    processed_list = []

    # 3. For each article, run sentiment analysis and persist
    for art in unique_articles[:limit]:
        headline = art["headline"]
        sentiment_res = analyze_headline_sentiment(headline)

        pub_dt = art["published_at"]
        url = art["url"]
        publisher = art["publisher"]

        # Persist or update in DB
        try:
            db_news, created = FinancialNews.objects.update_or_create(
                url=url,
                defaults={
                    "ticker": clean_ticker,
                    "headline": headline,
                    "summary": art.get("summary", ""),
                    "publisher": publisher,
                    "published_at": pub_dt,
                    "sentiment_label": sentiment_res["label"],
                    "sentiment_score": sentiment_res["score"],
                    "confidence": sentiment_res["confidence"],
                    "positive_prob": sentiment_res["positive_prob"],
                    "neutral_prob": sentiment_res["neutral_prob"],
                    "negative_prob": sentiment_res["negative_prob"],
                    "model_name": sentiment_res["model_name"],
                }
            )
        except Exception as db_err:
            logger.debug(f"DB save error for article: {db_err}")

        # Formulate response object
        time_display = pub_dt.strftime("%b %d, %H:%M UTC") if isinstance(pub_dt, datetime) else str(pub_dt)
        processed_list.append({
            "ticker": clean_ticker,
            "headline": headline,
            "publisher": publisher,
            "url": url,
            "published_at": pub_dt.isoformat() if isinstance(pub_dt, datetime) else str(pub_dt),
            "published_at_display": time_display,
            "sentiment_label": sentiment_res["label"],
            "sentiment_score": sentiment_res["score"],
            "confidence": sentiment_res["confidence"],
            "confidence_pct": round(sentiment_res["confidence"] * 100, 1),
            "positive_prob": sentiment_res["positive_prob"],
            "neutral_prob": sentiment_res["neutral_prob"],
            "negative_prob": sentiment_res["negative_prob"],
            "model_name": sentiment_res["model_name"],
        })

    # If no online articles could be retrieved, retrieve recent stored articles from DB
    if not processed_list:
        db_items = FinancialNews.objects.filter(ticker=clean_ticker).order_by("-published_at")[:limit]
        for db_art in db_items:
            time_display = db_art.published_at.strftime("%b %d, %H:%M UTC") if db_art.published_at else "Recent"
            processed_list.append({
                "ticker": clean_ticker,
                "headline": db_art.headline,
                "publisher": db_art.publisher,
                "url": db_art.url,
                "published_at": db_art.published_at.isoformat() if db_art.published_at else "",
                "published_at_display": time_display,
                "sentiment_label": db_art.sentiment_label,
                "sentiment_score": db_art.sentiment_score,
                "confidence": db_art.confidence,
                "confidence_pct": round(db_art.confidence * 100, 1),
                "positive_prob": db_art.positive_prob,
                "neutral_prob": db_art.neutral_prob,
                "negative_prob": db_art.negative_prob,
                "model_name": db_art.model_name,
            })

    _NEWS_CACHE[cache_key] = {"data": processed_list, "ts": time.time()}
    return processed_list
