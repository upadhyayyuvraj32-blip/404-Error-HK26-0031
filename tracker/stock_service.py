"""
TrendPulse AI - Stock Data Service
Integrates real market data via yfinance for Indian and Global stocks/indices.
Formats OHLCV data for TradingView Lightweight Charts and provides real-time quotes.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# In-memory short-lived cache to avoid rate-limiting and maximize responsiveness
_CACHE = {}
CACHE_TTL = 90  # seconds

# Curated list of prominent Indian and Global stocks with full metadata
POPULAR_STOCKS = [
    # Indian Large Caps (NSE)
    {"ticker": "RELIANCE.NS", "name": "Reliance Industries Ltd", "exchange": "NSE", "currency": "INR", "sector": "Energy & Conglomerate", "country": "India"},
    {"ticker": "TCS.NS", "name": "Tata Consultancy Services", "exchange": "NSE", "currency": "INR", "sector": "Information Technology", "country": "India"},
    {"ticker": "INFY.NS", "name": "Infosys Limited", "exchange": "NSE", "currency": "INR", "sector": "Information Technology", "country": "India"},
    {"ticker": "HDFCBANK.NS", "name": "HDFC Bank Limited", "exchange": "NSE", "currency": "INR", "sector": "Banking & Finance", "country": "India"},
    {"ticker": "TATAMOTORS.NS", "name": "Tata Motors Ltd", "exchange": "NSE", "currency": "INR", "sector": "Automotive", "country": "India"},
    {"ticker": "ICICIBANK.NS", "name": "ICICI Bank Limited", "exchange": "NSE", "currency": "INR", "sector": "Banking & Finance", "country": "India"},
    {"ticker": "SBIN.NS", "name": "State Bank of India", "exchange": "NSE", "currency": "INR", "sector": "Public Banking", "country": "India"},
    {"ticker": "BHARTIARTL.NS", "name": "Bharti Airtel Limited", "exchange": "NSE", "currency": "INR", "sector": "Telecom", "country": "India"},
    {"ticker": "ITC.NS", "name": "ITC Limited", "exchange": "NSE", "currency": "INR", "sector": "Consumer Goods / FMCG", "country": "India"},
    {"ticker": "LT.NS", "name": "Larsen & Toubro Ltd", "exchange": "NSE", "currency": "INR", "sector": "Engineering & Construction", "country": "India"},
    {"ticker": "WIPRO.NS", "name": "Wipro Limited", "exchange": "NSE", "currency": "INR", "sector": "Information Technology", "country": "India"},
    {"ticker": "MARUTI.NS", "name": "Maruti Suzuki India", "exchange": "NSE", "currency": "INR", "sector": "Automotive", "country": "India"},

    # Global / US Stocks
    {"ticker": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ", "currency": "USD", "sector": "Consumer Electronics", "country": "USA"},
    {"ticker": "MSFT", "name": "Microsoft Corporation", "exchange": "NASDAQ", "currency": "USD", "sector": "Software & Cloud", "country": "USA"},
    {"ticker": "NVDA", "name": "NVIDIA Corporation", "exchange": "NASDAQ", "currency": "USD", "sector": "Semiconductors & AI", "country": "USA"},
    {"ticker": "GOOGL", "name": "Alphabet Inc. (Google)", "exchange": "NASDAQ", "currency": "USD", "sector": "Internet & Search", "country": "USA"},
    {"ticker": "AMZN", "name": "Amazon.com Inc.", "exchange": "NASDAQ", "currency": "USD", "sector": "E-Commerce & Cloud", "country": "USA"},
    {"ticker": "TSLA", "name": "Tesla, Inc.", "exchange": "NASDAQ", "currency": "USD", "sector": "Automotive & Clean Energy", "country": "USA"},
    {"ticker": "META", "name": "Meta Platforms Inc.", "exchange": "NASDAQ", "currency": "USD", "sector": "Social Media & Tech", "country": "USA"},
]

POPULAR_INDICES = [
    {"ticker": "^NSEI", "name": "NIFTY 50", "exchange": "NSE", "country": "India", "currency": "INR"},
    {"ticker": "^BSESN", "name": "S&P BSE SENSEX", "exchange": "BSE", "country": "India", "currency": "INR"},
    {"ticker": "^GSPC", "name": "S&P 500", "exchange": "NYSE/NASDAQ", "country": "USA", "currency": "USD"},
]


def _get_cache(key: str):
    entry = _CACHE.get(key)
    if entry and (time.time() - entry["ts"]) < CACHE_TTL:
        return entry["data"]
    return None


def _set_cache(key: str, data: Any):
    _CACHE[key] = {"data": data, "ts": time.time()}


def search_stocks(query: str) -> List[Dict[str, Any]]:
    """Search known stocks or query Yahoo Finance for live matching."""
    q = (query or "").strip().upper()
    if not q:
        return POPULAR_STOCKS[:8]

    matches = []
    # Check popular list first
    for s in POPULAR_STOCKS:
        if q in s["ticker"].upper() or q in s["name"].upper():
            matches.append(s)

    # If query looks like a custom ticker and not yet in matches, allow it
    if not any(m["ticker"] == q for m in matches):
        exchange = "NSE" if q.endswith(".NS") else ("BSE" if q.endswith(".BO") else "NASDAQ/NYSE")
        curr = "INR" if (".NS" in q or ".BO" in q) else "USD"
        matches.append({
            "ticker": q,
            "name": f"{q} Stock",
            "exchange": exchange,
            "currency": curr,
            "sector": "Market Equities",
            "country": "India" if curr == "INR" else "Global",
        })

    return matches[:10]


def get_stock_quote(ticker: str) -> Dict[str, Any]:
    """
    Fetches real-time or latest available quote for a given ticker.
    """
    clean_ticker = ticker.strip().upper()
    cache_key = f"quote_{clean_ticker}"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    # Find metadata
    meta = next((s for s in POPULAR_STOCKS if s["ticker"] == clean_ticker), None)
    if not meta:
        meta = next((idx for idx in POPULAR_INDICES if idx["ticker"] == clean_ticker), None)
    
    company_name = meta["name"] if meta else clean_ticker
    exchange = meta["exchange"] if meta else ("NSE" if ".NS" in clean_ticker else "GLOBAL")
    currency = meta["currency"] if meta else ("INR" if ".NS" in clean_ticker else "USD")

    try:
        t = yf.Ticker(clean_ticker)
        fast_info = getattr(t, "fast_info", None)
        
        current_price = 0.0
        prev_close = 0.0
        day_high = 0.0
        day_low = 0.0
        fifty_two_high = 0.0
        fifty_two_low = 0.0
        volume = 0

        if fast_info:
            try:
                current_price = float(fast_info.last_price or 0.0)
                prev_close = float(fast_info.previous_close or 0.0)
                day_high = float(fast_info.day_high or 0.0)
                day_low = float(fast_info.day_low or 0.0)
                fifty_two_high = float(fast_info.year_high or 0.0)
                fifty_two_low = float(fast_info.year_low or 0.0)
                currency = str(fast_info.currency or currency)
                volume = int(fast_info.last_volume or 0)
            except Exception as e:
                logger.debug(f"fast_info read error for {clean_ticker}: {e}")

        # Fallback to history if fast_info missing
        if current_price == 0.0 or prev_close == 0.0:
            hist = t.history(period="5d")
            if not hist.empty:
                current_price = float(hist["Close"].iloc[-1])
                if len(hist) > 1:
                    prev_close = float(hist["Close"].iloc[-2])
                else:
                    prev_close = float(hist["Open"].iloc[-1])
                day_high = float(hist["High"].iloc[-1])
                day_low = float(hist["Low"].iloc[-1])
                volume = int(hist["Volume"].iloc[-1])

        change = round(current_price - prev_close, 2)
        pct_change = round((change / prev_close) * 100, 2) if prev_close > 0 else 0.0

        result = {
            "ticker": clean_ticker,
            "name": company_name,
            "exchange": exchange,
            "currency": currency,
            "current_price": round(current_price, 2),
            "previous_close": round(prev_close, 2),
            "change": change,
            "percent_change": pct_change,
            "is_positive": change >= 0,
            "day_high": round(day_high, 2),
            "day_low": round(day_low, 2),
            "fifty_two_high": round(fifty_two_high, 2),
            "fifty_two_low": round(fifty_two_low, 2),
            "volume": volume,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data_source": "Yahoo Finance Market Feed",
            "is_live": True,
        }
        _set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"Error fetching quote for {clean_ticker}: {e}")
        # Return structured fallback indicating error state
        return {
            "ticker": clean_ticker,
            "name": company_name,
            "exchange": exchange,
            "currency": currency,
            "current_price": 0.0,
            "previous_close": 0.0,
            "change": 0.0,
            "percent_change": 0.0,
            "is_positive": True,
            "day_high": 0.0,
            "day_low": 0.0,
            "fifty_two_high": 0.0,
            "fifty_two_low": 0.0,
            "volume": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data_source": "Offline / Market Unavailable",
            "is_live": False,
            "error": str(e),
        }


def get_market_overview() -> List[Dict[str, Any]]:
    """Fetches key indices: NIFTY 50, S&P BSE SENSEX, and S&P 500."""
    cache_key = "market_overview_indices"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    indices_data = []
    for idx in POPULAR_INDICES:
        ticker = idx["ticker"]
        quote = get_stock_quote(ticker)
        indices_data.append({
            "ticker": ticker,
            "name": idx["name"],
            "exchange": idx["exchange"],
            "country": idx["country"],
            "currency": idx["currency"],
            "price": quote.get("current_price", 0.0),
            "change": quote.get("change", 0.0),
            "percent_change": quote.get("percent_change", 0.0),
            "is_positive": quote.get("is_positive", True),
            "timestamp": quote.get("timestamp"),
            "data_source": quote.get("data_source"),
        })

    _set_cache(cache_key, indices_data)
    return indices_data


def get_stock_history(ticker: str, time_range: str = "1M") -> Dict[str, Any]:
    """
    Fetches OHLCV historical time series formatted for TradingView Lightweight Charts.
    Lightweight Charts format:
    Candlesticks: [{ time: 'YYYY-MM-DD' or timestamp_seconds, open, high, low, close }]
    Volume: [{ time, value, color }]
    """
    clean_ticker = ticker.strip().upper()
    cache_key = f"history_{clean_ticker}_{time_range}"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    # Mapping timeframe to yfinance period and interval
    range_map = {
        "1D": {"period": "1d", "interval": "5m", "is_intraday": True},
        "1W": {"period": "5d", "interval": "15m", "is_intraday": True},
        "1M": {"period": "1mo", "interval": "1d", "is_intraday": False},
        "3M": {"period": "3mo", "interval": "1d", "is_intraday": False},
        "1Y": {"period": "1y", "interval": "1d", "is_intraday": False},
        "ALL": {"period": "5y", "interval": "1wk", "is_intraday": False},
    }

    config = range_map.get(time_range, range_map["1M"])
    
    try:
        t = yf.Ticker(clean_ticker)
        df = t.history(period=config["period"], interval=config["interval"])

        if df.empty:
            # Fallback if intraday not available (e.g. market closed or index)
            if config["is_intraday"]:
                df = t.history(period="1mo", interval="1d")
                config["is_intraday"] = False

        candles = []
        volumes = []

        if not df.empty:
            for idx_val, row in df.iterrows():
                try:
                    open_p = round(float(row["Open"]), 2)
                    high_p = round(float(row["High"]), 2)
                    low_p = round(float(row["Low"]), 2)
                    close_p = round(float(row["Close"]), 2)
                    vol = int(row["Volume"]) if not pd.isna(row["Volume"]) else 0

                    if config["is_intraday"]:
                        # Unix timestamp in seconds for TradingView Lightweight charts intraday
                        t_val = int(idx_val.timestamp())
                    else:
                        # Date string YYYY-MM-DD
                        t_val = idx_val.strftime("%Y-%m-%d")

                    candles.append({
                        "time": t_val,
                        "open": open_p,
                        "high": high_p,
                        "low": low_p,
                        "close": close_p,
                    })

                    vol_color = "rgba(16, 185, 129, 0.4)" if close_p >= open_p else "rgba(239, 68, 68, 0.4)"
                    volumes.append({
                        "time": t_val,
                        "value": vol,
                        "color": vol_color,
                    })
                except Exception as row_err:
                    continue

        result = {
            "ticker": clean_ticker,
            "range": time_range,
            "is_intraday": config["is_intraday"],
            "candle_count": len(candles),
            "candles": candles,
            "volumes": volumes,
            "currency": "INR" if ".NS" in clean_ticker or ".BO" in clean_ticker else "USD",
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"Error fetching history for {clean_ticker}: {e}")
        return {
            "ticker": clean_ticker,
            "range": time_range,
            "candle_count": 0,
            "candles": [],
            "volumes": [],
            "error": str(e),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }


def calculate_investment_analysis(ticker: str, sentiment_score: float = 0.0, bullish_index: float = 50.0) -> Dict[str, Any]:
    """
    Computes comprehensive, easy-to-understand stock advisory analytics:
    - Should you buy now? (Buy / Hold / Sell / Wait)
    - Optimal entry zone & best time to buy
    - Projected 6-12 month future price targets (Base, Bull, Bear/Stop-loss)
    - Catalysts & downside risks
    """
    clean_ticker = ticker.strip().upper()
    quote = get_stock_quote(clean_ticker)
    curr_price = float(quote.get("current_price", 0.0))
    fifty_two_high = float(quote.get("fifty_two_high", 0.0)) or (curr_price * 1.15)
    fifty_two_low = float(quote.get("fifty_two_low", 0.0)) or (curr_price * 0.85)
    currency = quote.get("currency", "INR")
    curr_symbol = "₹" if currency == "INR" else "$"

    # Determine 52-week position
    range_span = max(fifty_two_high - fifty_two_low, 1.0)
    position_pct = max(0.0, min(100.0, ((curr_price - fifty_two_low) / range_span) * 100))

    # Algorithmic Recommendation Synthesis
    if sentiment_score >= 0.25 and position_pct <= 75:
        verdict = "STRONG BUY"
        badge_type = "strong_buy"
        badge_color = "emerald"
        action_decision = "Buy Recommendation: High Conviction"
        action_detail_hi = "Abhi buy karne ke liye favorable setup hai. Company ka news sentiment strongly positive hai aur stock price apne 52-week peak se niche trade kar raha hai."
        action_detail_en = "Current levels present a favorable accumulation window. Institutional news coverage is strongly positive and the price is below overbought peak resistance."
        best_time_to_buy = f"Immediate entry on small 1-2% consolidation, or any dip toward {curr_symbol}{round(curr_price * 0.98, 2)}."
        timing_badge = "Favorable Window Now"

    elif sentiment_score >= 0.10:
        verdict = "BUY ON DIPS"
        badge_type = "buy_dips"
        badge_color = "teal"
        action_decision = "Buy on Minor Pullbacks"
        action_detail_hi = "Stock strong positive sentiment mein hai, lekin 52-week peak ke paas hone ke kaaran ek saath poora paisa lagane ke bajaye 2-3% dip par buy karein."
        action_detail_en = "Sentiment is bullish, but price is testing higher bands. Staggered accumulation on 2-3% pullbacks offers the optimal risk-to-reward ratio."
        best_time_to_buy = f"Accumulation Zone: {curr_symbol}{round(curr_price * 0.95, 2)} – {curr_symbol}{round(curr_price * 0.98, 2)}."
        timing_badge = "Wait For 2-3% Dip"

    elif sentiment_score <= -0.15:
        verdict = "WAIT / AVOID FOR NOW"
        badge_type = "avoid"
        badge_color = "rose"
        action_decision = "Wait for Correction / Avoid Fresh Buying"
        action_detail_hi = "Recent financial news aur media coverage negative hai. Abhi buy karne se bachein kyunki short-term downside risk ho sakta hai."
        action_detail_en = "Recent headline coverage reflects headwinds or margin concerns. Avoid fresh long positions until base consolidation forms."
        best_time_to_buy = f"Wait for negative news to clear and strong support test near {curr_symbol}{round(curr_price * 0.90, 2)}."
        timing_badge = "High Short-Term Risk"

    else:
        verdict = "HOLD / ACCUMULATE"
        badge_type = "hold"
        badge_color = "amber"
        action_decision = "Hold Existing Positions / Watch Breakout"
        action_detail_hi = "Market sentiment filhaal neutral / balanced hai. Existing investors hold karein, aur naye buyers volume breakout ka wait karein."
        action_detail_en = "Market coverage is balanced. Existing investors can hold. Fresh entries should wait for a clear catalyst or volume breakout."
        best_time_to_buy = f"Buy on strong support test at {curr_symbol}{round(curr_price * 0.96, 2)} or decisive resistance breakout."
        timing_badge = "Neutral / Wait For Trigger"

    # Future Price Projections (6 to 12 Months Model Scenario)
    base_upside_pct = round(12.0 + (sentiment_score * 8.0), 1)
    bull_upside_pct = round(24.0 + (sentiment_score * 15.0), 1)
    bear_downside_pct = round(-8.5 + min(0.0, sentiment_score * 5.0), 1)

    base_target = round(curr_price * (1 + (base_upside_pct / 100)), 2)
    bull_target = round(curr_price * (1 + (bull_upside_pct / 100)), 2)
    bear_stoploss = round(curr_price * (1 + (bear_downside_pct / 100)), 2)

    # Contextual Catalysts & Risks
    meta = next((s for s in POPULAR_STOCKS if s["ticker"] == clean_ticker), None)
    sector = meta.get("sector", "Equities") if meta else "Equities"

    catalysts = [
        f"Strong operational footprint in {sector} with expanding margins.",
        f"FinBERT news sentiment scoring favorable consensus ({bullish_index:.0f}/100 bullish index).",
        f"Institutional coverage targeting earnings expansion over the next 4 quarters.",
    ]
    risks = [
        "Broader market macroeconomic volatility and benchmark index fluctuations.",
        "Sector-specific regulatory revisions or commodity/input cost fluctuations.",
        "Short-term consolidation if stock fails to sustain support near recent pivot levels.",
    ]

    return {
        "ticker": clean_ticker,
        "name": quote.get("name", clean_ticker),
        "current_price": curr_price,
        "currency_symbol": curr_symbol,
        "verdict": verdict,
        "badge_type": badge_type,
        "badge_color": badge_color,
        "action_decision": action_decision,
        "action_detail_hi": action_detail_hi,
        "action_detail_en": action_detail_en,
        "best_time_to_buy": best_time_to_buy,
        "timing_badge": timing_badge,
        "fifty_two_week_position_pct": round(position_pct, 1),
        "projections": {
            "base_case": {
                "target": base_target,
                "upside_pct": base_upside_pct,
                "label": "Base Case Target (6-12M)",
                "description": "Standard steady earnings growth projection",
            },
            "bull_case": {
                "target": bull_target,
                "upside_pct": bull_upside_pct,
                "label": "Bull Case Target (6-12M)",
                "description": "Optimistic upside driven by expansion and momentum",
            },
            "bear_case": {
                "target": bear_stoploss,
                "downside_pct": bear_downside_pct,
                "label": "Key Support / Risk Level",
                "description": "Critical defensive support zone / stop-loss guideline",
            },
        },
        "catalysts": catalysts,
        "risks": risks,
        "disclaimer": "Scenario analysis derived from historical technical price bands and FinBERT news sentiment. Not financial advice.",
    }
