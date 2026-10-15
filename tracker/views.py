"""
TrendPulse AI - Django Views and REST API Endpoints
Serves the responsive dashboard UI and comprehensive JSON financial/sentiment APIs.
"""

import json
import logging
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .models import TrackedStock, FinancialNews, SentimentAlert
from .stock_service import (
    get_stock_quote,
    get_market_overview,
    get_stock_history,
    search_stocks,
    calculate_investment_analysis,
    POPULAR_STOCKS,
)
from .news_service import get_and_analyze_news_for_ticker
from .sentiment_engine import aggregate_sentiment_metrics
from .alert_engine import get_recent_alerts, evaluate_and_generate_alerts

logger = logging.getLogger(__name__)


def dashboard_view(request: HttpRequest) -> HttpResponse:
    """Renders the main TrendPulse financial analytics dashboard."""
    # Ensure default stocks exist in database
    _seed_initial_stocks()
    context = {
        "page_title": "TrendPulse AI - Stock Market Sentiment Tracker",
        "default_ticker": "RELIANCE.NS",
        "popular_stocks": POPULAR_STOCKS[:8],
    }
    return render(request, "tracker/index.html", context)


def api_market_overview(request: HttpRequest) -> JsonResponse:
    """Returns overview for key indices: NIFTY 50, SENSEX, S&P 500."""
    try:
        overview = get_market_overview()
        return JsonResponse({"status": "success", "data": overview})
    except Exception as e:
        logger.error(f"api_market_overview error: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


def api_stock_quote(request: HttpRequest, ticker: str) -> JsonResponse:
    """Returns real-time/latest quote and metadata for a specific ticker."""
    try:
        clean_ticker = ticker.strip().upper()
        quote = get_stock_quote(clean_ticker)
        
        # Check if in watchlist
        is_watchlist = TrackedStock.objects.filter(ticker=clean_ticker, is_watchlist=True).exists()
        quote["is_watchlist"] = is_watchlist

        return JsonResponse({"status": "success", "data": quote})
    except Exception as e:
        logger.error(f"api_stock_quote error: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


def api_stock_history(request: HttpRequest, ticker: str) -> JsonResponse:
    """Returns OHLCV historical time series for TradingView Lightweight charts."""
    try:
        clean_ticker = ticker.strip().upper()
        time_range = request.GET.get("range", "1M").upper()
        valid_ranges = ["1D", "1W", "1M", "3M", "1Y", "ALL"]
        if time_range not in valid_ranges:
            time_range = "1M"

        history_data = get_stock_history(clean_ticker, time_range=time_range)
        return JsonResponse({"status": "success", "data": history_data})
    except Exception as e:
        logger.error(f"api_stock_history error: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


def api_stock_news(request: HttpRequest, ticker: str) -> JsonResponse:
    """Returns live news with AI sentiment scores and triggers alert evaluation."""
    try:
        clean_ticker = ticker.strip().upper()
        limit = int(request.GET.get("limit", 12))
        limit = min(max(limit, 3), 25)

        news_items = get_and_analyze_news_for_ticker(clean_ticker, limit=limit)
        
        # Evaluate for potential sentiment alerts
        evaluate_and_generate_alerts(clean_ticker, news_items)

        return JsonResponse({
            "status": "success",
            "ticker": clean_ticker,
            "count": len(news_items),
            "data": news_items,
        })
    except Exception as e:
        logger.error(f"api_stock_news error: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


def api_sentiment_summary(request: HttpRequest, ticker: str) -> JsonResponse:
    """Returns aggregated sentiment metrics and sentiment-price correlation."""
    try:
        clean_ticker = ticker.strip().upper()
        news_items = get_and_analyze_news_for_ticker(clean_ticker, limit=15)
        metrics = aggregate_sentiment_metrics(news_items)

        # Get stock quote to compare sentiment vs price movement
        quote = get_stock_quote(clean_ticker)
        pct_change = quote.get("percent_change", 0.0)

        # Determine alignment between AI sentiment and price direction
        avg_score = metrics["average_score"]
        if (avg_score > 0.15 and pct_change > 0) or (avg_score < -0.15 and pct_change < 0):
            alignment = "Aligned (Sentiment and Price moving in same direction)"
            alignment_badge = "aligned"
        elif (avg_score > 0.15 and pct_change < 0) or (avg_score < -0.15 and pct_change > 0):
            alignment = "Divergent (Price defying sentiment trend; watch for correction)"
            alignment_badge = "divergent"
        else:
            alignment = "Neutral / Stable"
            alignment_badge = "neutral"

        # Calculate investment advisory intelligence
        inv_analysis = calculate_investment_analysis(
            clean_ticker,
            sentiment_score=metrics.get("average_score", 0.0),
            bullish_index=metrics.get("bullish_index", 50.0),
        )

        summary = {
            "ticker": clean_ticker,
            "metrics": metrics,
            "price_change_pct": pct_change,
            "price_movement": "Positive" if pct_change >= 0 else "Negative",
            "sentiment_price_alignment": alignment,
            "alignment_badge": alignment_badge,
            "sample_size": len(news_items),
            "investment_analysis": inv_analysis,
            "ai_disclaimer": "AI sentiment analysis represents linguistic polarity of news coverage and is not financial advice or a price prediction.",
        }

        return JsonResponse({"status": "success", "data": summary})
    except Exception as e:
        logger.error(f"api_sentiment_summary error: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


def api_stock_analysis(request: HttpRequest, ticker: str) -> JsonResponse:
    """Dedicated endpoint returning actionable investment analysis, entry zones, and price targets."""
    try:
        clean_ticker = ticker.strip().upper()
        news_items = get_and_analyze_news_for_ticker(clean_ticker, limit=10)
        metrics = aggregate_sentiment_metrics(news_items)
        analysis = calculate_investment_analysis(
            clean_ticker,
            sentiment_score=metrics.get("average_score", 0.0),
            bullish_index=metrics.get("bullish_index", 50.0),
        )
        return JsonResponse({"status": "success", "data": analysis})
    except Exception as e:
        logger.error(f"api_stock_analysis error: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)



def api_company_comparison(request: HttpRequest) -> JsonResponse:
    """
    Feature G: Compares multiple companies by aggregate sentiment,
    distribution, price movement, and news volume.
    """
    try:
        tickers_param = request.GET.get("tickers", "RELIANCE.NS,TCS.NS,AAPL,TATAMOTORS.NS,NVDA")
        ticker_list = [t.strip().upper() for t in tickers_param.split(",") if t.strip()][:8]

        comparison_results = []
        for t in ticker_list:
            quote = get_stock_quote(t)
            # Use cached or quick news analysis
            news_items = get_and_analyze_news_for_ticker(t, limit=8)
            metrics = aggregate_sentiment_metrics(news_items)

            comparison_results.append({
                "ticker": t,
                "name": quote.get("name", t),
                "exchange": quote.get("exchange", "NSE"),
                "currency": quote.get("currency", "INR"),
                "price": quote.get("current_price", 0.0),
                "change_pct": quote.get("percent_change", 0.0),
                "is_positive": quote.get("is_positive", True),
                "sentiment_score": metrics.get("average_score", 0.0),
                "sentiment_verdict": metrics.get("sentiment_verdict", "Neutral"),
                "bullish_index": metrics.get("bullish_index", 50.0),
                "positive_pct": metrics.get("positive_pct", 0.0),
                "neutral_pct": metrics.get("neutral_pct", 0.0),
                "negative_pct": metrics.get("negative_pct", 0.0),
                "article_count": metrics.get("total_articles", 0),
            })

        return JsonResponse({"status": "success", "data": comparison_results})
    except Exception as e:
        logger.error(f"api_company_comparison error: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


def api_alerts(request: HttpRequest) -> JsonResponse:
    """Returns the latest explainable sentiment shift alerts."""
    try:
        limit = int(request.GET.get("limit", 10))
        alerts = get_recent_alerts(limit=limit)
        return JsonResponse({"status": "success", "data": alerts})
    except Exception as e:
        logger.error(f"api_alerts error: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


def api_search(request: HttpRequest) -> JsonResponse:
    """Provides instant stock search suggestions."""
    try:
        q = request.GET.get("q", "").strip()
        results = search_stocks(q)
        return JsonResponse({"status": "success", "data": results})
    except Exception as e:
        logger.error(f"api_search error: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET", "POST", "DELETE"])
def api_watchlist(request: HttpRequest) -> JsonResponse:
    """Manages the user watchlist."""
    try:
        if request.method == "GET":
            stocks = TrackedStock.objects.filter(is_watchlist=True)
            data = []
            for s in stocks:
                quote = get_stock_quote(s.ticker)
                data.append({
                    "ticker": s.ticker,
                    "name": s.name,
                    "exchange": s.exchange,
                    "currency": s.currency,
                    "price": quote.get("current_price", 0.0),
                    "change_pct": quote.get("percent_change", 0.0),
                    "is_positive": quote.get("is_positive", True),
                })
            return JsonResponse({"status": "success", "data": data})

        elif request.method == "POST":
            payload = json.loads(request.body.decode("utf-8")) if request.body else {}
            ticker = payload.get("ticker", "").strip().upper()
            if not ticker:
                return JsonResponse({"status": "error", "message": "Ticker is required"}, status=400)

            stock, created = TrackedStock.objects.get_or_create(
                ticker=ticker,
                defaults={
                    "name": payload.get("name", ticker),
                    "exchange": payload.get("exchange", "NSE"),
                    "currency": payload.get("currency", "INR"),
                    "is_watchlist": True,
                }
            )
            if not created:
                stock.is_watchlist = not stock.is_watchlist
                stock.save()

            return JsonResponse({
                "status": "success",
                "ticker": ticker,
                "is_watchlist": stock.is_watchlist,
                "message": "Watchlist updated",
            })

    except Exception as e:
        logger.error(f"api_watchlist error: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


def _seed_initial_stocks():
    """Ensures popular initial stocks are populated into database."""
    if TrackedStock.objects.count() == 0:
        for s in POPULAR_STOCKS[:8]:
            TrackedStock.objects.create(
                ticker=s["ticker"],
                name=s["name"],
                exchange=s["exchange"],
                currency=s["currency"],
                sector=s["sector"],
                is_watchlist=s["ticker"] in ["RELIANCE.NS", "TCS.NS", "AAPL", "NVDA"],
            )
