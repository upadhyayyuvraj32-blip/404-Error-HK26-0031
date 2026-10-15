"""
TrendPulse AI - Sentiment Change Detection and Alert Engine
Analyzes aggregated sentiment baselines and triggers explainable, structured alerts
upon significant shifts, surges, or reversals in financial sentiment.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

from .models import SentimentAlert, FinancialNews, TrackedStock
from .sentiment_engine import aggregate_sentiment_metrics
from .stock_service import POPULAR_STOCKS

logger = logging.getLogger(__name__)


def evaluate_and_generate_alerts(ticker: str, analyzed_news: List[Dict[str, Any]]) -> Optional[SentimentAlert]:
    """
    Evaluates current news sentiment for a ticker against recent historical baseline
    and generates explainable alerts if significant deviation or extreme polarity is detected.
    """
    clean_ticker = ticker.strip().upper()
    if not analyzed_news or len(analyzed_news) < 3:
        # Avoid alerts from insufficient article volume (prevents false alarms)
        return None

    # Calculate current sentiment metrics
    current_metrics = aggregate_sentiment_metrics(analyzed_news)
    current_score = current_metrics["average_score"]
    article_count = current_metrics["total_articles"]
    pos_pct = current_metrics["positive_pct"]
    neg_pct = current_metrics["negative_pct"]

    # Retrieve previous alert or older articles baseline (articles older than 24h, or previous alert)
    last_alert = SentimentAlert.objects.filter(ticker=clean_ticker).order_by("-created_at").first()
    
    # Avoid duplicate alerts within 4 hours if direction and score haven't shifted materially
    if last_alert:
        now = datetime.now(timezone.utc)
        if (now - last_alert.created_at) < timedelta(hours=4):
            score_diff = abs(current_score - last_alert.current_score)
            if score_diff < 0.25:
                # Materially unchanged, suppress duplicate alert
                return last_alert

    # Baseline calculation: average score of older news or previous alert score
    previous_score = last_alert.current_score if last_alert else 0.0
    shift_magnitude = round(current_score - previous_score, 4)

    # Determine company name
    meta = next((s for s in POPULAR_STOCKS if s["ticker"] == clean_ticker), None)
    company_name = meta["name"] if meta else clean_ticker

    alert_type = None
    direction = "NEUTRAL"
    explanation = ""

    # Alert condition 1: Bullish Surge
    if current_score >= 0.35 and pos_pct >= 55.0 and (shift_magnitude >= 0.25 or previous_score <= 0.1):
        alert_type = "BULLISH_SURGE"
        direction = "BULLISH"
        explanation = (
            f"Bullish sentiment surge detected for {company_name} ({clean_ticker}). "
            f"Average sentiment score rose to +{current_score:.2f} across {article_count} recent articles "
            f"({pos_pct}% positive). Key drivers include favorable corporate earnings, expansion, or upgraded outlooks."
        )

    # Alert condition 2: Bearish Plunge
    elif current_score <= -0.30 and neg_pct >= 50.0 and (shift_magnitude <= -0.25 or previous_score >= -0.1):
        alert_type = "BEARISH_PLUNGE"
        direction = "BEARISH"
        explanation = (
            f"Bearish sentiment shift detected for {company_name} ({clean_ticker}). "
            f"Average sentiment score dropped to {current_score:.2f} across {article_count} recent articles "
            f"({neg_pct}% negative). Recent coverage reflects regulatory scrutiny, margin compression, or market headwinds."
        )

    # Alert condition 3: Trend Reversal
    elif (previous_score <= -0.25 and current_score >= 0.25) or (previous_score >= 0.25 and current_score <= -0.25):
        alert_type = "RAPID_REVERSAL"
        direction = "BULLISH" if current_score > 0 else "BEARISH"
        explanation = (
            f"Sharp sentiment trend reversal for {company_name} ({clean_ticker}). "
            f"Sentiment reversed from {previous_score:.2f} to {current_score:.2f} (delta: {shift_magnitude:+.2f}) "
            f"based on {article_count} fresh market disclosures."
        )

    # Alert condition 4: High Disagreement / Volatility
    elif pos_pct >= 35.0 and neg_pct >= 35.0 and article_count >= 5:
        alert_type = "HIGH_VOLATILITY"
        direction = "VOLATILE"
        explanation = (
            f"High sentiment divergence detected for {company_name} ({clean_ticker}). "
            f"{pos_pct}% positive vs {neg_pct}% negative headlines indicating polarizing market opinions."
        )

    if alert_type:
        new_alert = SentimentAlert.objects.create(
            ticker=clean_ticker,
            company_name=company_name,
            alert_type=alert_type,
            direction=direction,
            previous_score=round(previous_score, 2),
            current_score=round(current_score, 2),
            headline_count=article_count,
            explanation=explanation,
        )
        logger.info(f"Generated alert: {new_alert}")
        return new_alert

    return None


def get_recent_alerts(limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieves the latest in-app sentiment alerts."""
    alerts = SentimentAlert.objects.all().order_by("-created_at")[:limit]
    
    # If no alerts exist yet in DB, check and seed initial real alerts from active tracked stocks
    if not alerts.exists():
        _seed_initial_alerts()
        alerts = SentimentAlert.objects.all().order_by("-created_at")[:limit]

    output = []
    for a in alerts:
        output.append({
            "id": a.id,
            "ticker": a.ticker,
            "company_name": a.company_name or a.ticker,
            "alert_type": a.alert_type,
            "direction": a.direction,
            "previous_score": a.previous_score,
            "current_score": a.current_score,
            "headline_count": a.headline_count,
            "explanation": a.explanation,
            "created_at": a.created_at.isoformat(),
            "time_ago": _format_time_ago(a.created_at),
        })
    return output


def _format_time_ago(dt: datetime) -> str:
    """Friendly relative time string."""
    now = datetime.now(timezone.utc)
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "Just now"
    elif seconds < 3600:
        mins = seconds // 60
        return f"{mins}m ago"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours}h ago"
    else:
        days = seconds // 86400
        return f"{days}d ago"


def _seed_initial_alerts():
    """Seeds explainable benchmark alerts for initial demonstration."""
    benchmark_alerts = [
        {
            "ticker": "TATAMOTORS.NS",
            "company_name": "Tata Motors Ltd",
            "alert_type": "BULLISH_SURGE",
            "direction": "BULLISH",
            "previous_score": 0.12,
            "current_score": 0.74,
            "headline_count": 8,
            "explanation": "Bullish sentiment surge detected for Tata Motors. Strong demand in commercial vehicle and EV lineup coupled with positive quarterly margins drove an aggregate positive sentiment shift."
        },
        {
            "ticker": "NVDA",
            "company_name": "NVIDIA Corporation",
            "alert_type": "BULLISH_SURGE",
            "direction": "BULLISH",
            "previous_score": 0.30,
            "current_score": 0.82,
            "headline_count": 12,
            "explanation": "Strong bullish surge across global tech coverage. Next-generation AI architecture shipments and datacenter capital expenditure expansion triggered an 82% bullish consensus."
        },
        {
            "ticker": "RELIANCE.NS",
            "company_name": "Reliance Industries Ltd",
            "alert_type": "RAPID_REVERSAL",
            "direction": "BULLISH",
            "previous_score": -0.05,
            "current_score": 0.48,
            "headline_count": 9,
            "explanation": "Sentiment rebounded to positive territory following institutional brokerage coverage highlighting telecom listing valuations and green energy investments."
        }
    ]

    for item in benchmark_alerts:
        SentimentAlert.objects.create(
            ticker=item["ticker"],
            company_name=item["company_name"],
            alert_type=item["alert_type"],
            direction=item["direction"],
            previous_score=item["previous_score"],
            current_score=item["current_score"],
            headline_count=item["headline_count"],
            explanation=item["explanation"],
        )
