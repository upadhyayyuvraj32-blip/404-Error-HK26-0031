"""
TrendPulse AI - Financial Sentiment Analysis Engine
Integrates FinBERT (ProsusAI/finbert) with finance-specific Lexicon fallback.
Provides transparent model labeling, confidence scores, and aggregate metrics.
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Global cached pipeline singleton
_finbert_pipeline = None
_finbert_loaded = False
_finbert_load_attempted = False

# Loughran-McDonald inspired financial lexicon weights for transparent fallback
FINANCIAL_LEXICON = {
    # Strong Positive (+1.0)
    "surge": 1.0, "surges": 1.0, "surged": 1.0, "soar": 1.0, "soars": 1.0, "soared": 1.0,
    "rally": 1.0, "rallies": 1.0, "rallied": 1.0, "skyrocket": 1.0, "outperform": 1.0,
    "outperformed": 1.0, "outperforming": 1.0, "bullish": 1.0, "dividend": 0.8,
    "breakout": 0.9, "profit": 0.85, "profits": 0.85, "profitable": 0.85, "growth": 0.75,
    "upside": 0.9, "upgrade": 0.9, "upgraded": 0.9, "buyback": 0.85, "acquisition": 0.6,
    "record-high": 1.0, "all-time high": 1.0, "milestone": 0.7, "expansion": 0.65,
    "beat": 0.8, "beats": 0.8, "beaten": 0.8, "strong": 0.7, "gain": 0.8, "gains": 0.8,
    "gainers": 0.8, "robust": 0.75, "rebound": 0.85, "optimistic": 0.8, "tailwind": 0.8,

    # Moderate Positive (+0.5)
    "rise": 0.6, "rises": 0.6, "rose": 0.6, "rising": 0.6, "jump": 0.7, "jumps": 0.7,
    "jumped": 0.7, "climb": 0.6, "climbs": 0.6, "positive": 0.6, "partnership": 0.5,
    "deal": 0.5, "deals": 0.5, "order": 0.4, "approved": 0.6, "patent": 0.5,

    # Strong Negative (-1.0)
    "plunge": -1.0, "plunges": -1.0, "plunged": -1.0, "crash": -1.0, "crashes": -1.0,
    "crashed": -1.0, "slump": -1.0, "slumps": -1.0, "slumped": -1.0, "tumble": -0.9,
    "tumbles": -0.9, "tumbled": -0.9, "bearish": -1.0, "loss": -0.85, "losses": -0.85,
    "downgrade": -0.95, "downgraded": -0.95, "fraud": -1.0, "scam": -1.0, "investigation": -0.8,
    "penalty": -0.8, "fined": -0.8, "lawsuit": -0.75, "bankruptcy": -1.0, "default": -1.0,
    "debt": -0.6, "sell-off": -0.9, "dump": -0.8, "underperform": -0.85, "missed": -0.8,
    "misses": -0.8, "drag": -0.65, "drags": -0.65, "headwind": -0.7, "recession": -0.9,

    # Moderate Negative (-0.5)
    "fall": -0.6, "falls": -0.6, "fell": -0.6, "falling": -0.6, "drop": -0.6, "drops": -0.6,
    "dropped": -0.6, "decline": -0.6, "declines": -0.6, "declined": -0.6, "weak": -0.65,
    "weakness": -0.65, "concern": -0.5, "concerns": -0.5, "warning": -0.7, "warns": -0.7,
}


def get_finbert_pipeline():
    """Lazily load FinBERT pipeline singleton."""
    global _finbert_pipeline, _finbert_loaded, _finbert_load_attempted
    if _finbert_load_attempted:
        return _finbert_pipeline

    _finbert_load_attempted = True
    try:
        from transformers import pipeline
        logger.info("Initializing ProsusAI/finbert pipeline...")
        _finbert_pipeline = pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert",
            top_k=None
        )
        _finbert_loaded = True
        logger.info("FinBERT successfully loaded.")
    except Exception as e:
        logger.warning(f"Could not load FinBERT pipeline: {e}. Falling back to Financial Lexicon Engine.")
        _finbert_pipeline = None
        _finbert_loaded = False

    return _finbert_pipeline


def analyze_headline_sentiment(text: str) -> Dict[str, Any]:
    """
    Analyzes sentiment of financial text using FinBERT or Lexicon fallback.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return {
            'label': 'neutral',
            'score': 0.0,
            'confidence': 0.5,
            'positive_prob': 0.2,
            'neutral_prob': 0.6,
            'negative_prob': 0.2,
            'model_name': 'Empty Text Default'
        }

    pipe = get_finbert_pipeline()

    if pipe is not None:
        try:
            # FinBERT inference (truncate to max 512 characters/tokens)
            results = pipe(cleaned[:512])
            
            # Format handling: results can be [[{...}, {...}, {...}]] or [{...}, {...}]
            items_list = results[0] if isinstance(results, list) and len(results) > 0 and isinstance(results[0], list) else results
            
            prob_map = {}
            if isinstance(items_list, list):
                for item in items_list:
                    if isinstance(item, dict) and 'label' in item and 'score' in item:
                        prob_map[item['label'].lower()] = float(item['score'])
            elif isinstance(items_list, dict):
                lbl = items_list.get('label', 'neutral').lower()
                prob_map[lbl] = float(items_list.get('score', 0.8))

            pos = prob_map.get('positive', 0.1)
            neg = prob_map.get('negative', 0.1)
            neu = prob_map.get('neutral', 0.8)

            # Winner label
            if prob_map:
                top = max(prob_map.items(), key=lambda x: x[1])
                winner_label = top[0]
                confidence = top[1]
            else:
                winner_label = 'neutral'
                confidence = 0.7

            # Compound normalized polarity (-1.0 to +1.0)
            compound_score = round(pos - neg, 4)

            return {
                'label': winner_label,
                'score': compound_score,
                'confidence': round(confidence, 4),
                'positive_prob': round(pos, 4),
                'neutral_prob': round(neu, 4),
                'negative_prob': round(neg, 4),
                'model_name': 'FinBERT (HF Neural)',
            }
        except Exception as e:
            logger.error(f"FinBERT inference error: {e}. Executing fallback.")

    # Financial Lexicon Fallback
    return _lexicon_sentiment_analysis(cleaned)


def _lexicon_sentiment_analysis(text: str) -> Dict[str, Any]:
    """Explainable financial sentiment heuristic using Loughran-McDonald weights."""
    words = text.lower().replace(",", " ").replace(".", " ").replace(";", " ").replace("-", " ").split()
    pos_score = 0.0
    neg_score = 0.0
    match_count = 0

    for word in words:
        if word in FINANCIAL_LEXICON:
            val = FINANCIAL_LEXICON[word]
            if val > 0:
                pos_score += val
            else:
                neg_score += abs(val)
            match_count += 1

    total = pos_score + neg_score
    if match_count == 0 or total == 0:
        return {
            'label': 'neutral',
            'score': 0.0,
            'confidence': 0.65,
            'positive_prob': 0.15,
            'neutral_prob': 0.70,
            'negative_prob': 0.15,
            'model_name': 'Financial Lexicon (Loughran-McDonald)',
        }

    raw_diff = pos_score - neg_score
    norm_compound = round(max(min(raw_diff / (total + 0.5), 1.0), -1.0), 4)

    # Probabilities
    pos_prob = round((pos_score + 0.2) / (total + 1.0), 4)
    neg_prob = round((neg_score + 0.2) / (total + 1.0), 4)
    neu_prob = round(max(0.0, 1.0 - (pos_prob + neg_prob)), 4)

    if norm_compound > 0.15:
        label = 'positive'
        conf = pos_prob
    elif norm_compound < -0.15:
        label = 'negative'
        conf = neg_prob
    else:
        label = 'neutral'
        conf = neu_prob

    return {
        'label': label,
        'score': norm_compound,
        'confidence': round(conf, 4),
        'positive_prob': pos_prob,
        'neutral_prob': neu_prob,
        'negative_prob': neg_prob,
        'model_name': 'Financial Lexicon (Loughran-McDonald)',
    }


def aggregate_sentiment_metrics(analyzed_articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes company-level aggregate sentiment metrics from a list of analyzed articles.
    """
    if not analyzed_articles:
        return {
            'total_articles': 0,
            'positive_count': 0,
            'neutral_count': 0,
            'negative_count': 0,
            'positive_pct': 0.0,
            'neutral_pct': 0.0,
            'negative_pct': 0.0,
            'average_score': 0.0,
            'average_confidence': 0.0,
            'sentiment_verdict': 'Neutral / Insufficient Data',
            'bullish_index': 50.0,  # 0 to 100 index for gauges
        }

    total = len(analyzed_articles)
    pos = sum(1 for a in analyzed_articles if a.get('sentiment_label') == 'positive')
    neu = sum(1 for a in analyzed_articles if a.get('sentiment_label') == 'neutral')
    neg = sum(1 for a in analyzed_articles if a.get('sentiment_label') == 'negative')

    avg_score = sum(float(a.get('sentiment_score', 0.0)) for a in analyzed_articles) / total
    avg_conf = sum(float(a.get('confidence', 0.5)) for a in analyzed_articles) / total

    pos_pct = round((pos / total) * 100, 1)
    neu_pct = round((neu / total) * 100, 1)
    neg_pct = round((neg / total) * 100, 1)

    # Convert average score (-1.0 to 1.0) into Bullish Index (0 to 100)
    bullish_index = round(((avg_score + 1.0) / 2.0) * 100, 1)

    if avg_score >= 0.25:
        verdict = 'Bullish' if avg_score < 0.55 else 'Strongly Bullish'
    elif avg_score <= -0.25:
        verdict = 'Bearish' if avg_score > -0.55 else 'Strongly Bearish'
    else:
        verdict = 'Neutral / Balanced'

    return {
        'total_articles': total,
        'positive_count': pos,
        'neutral_count': neu,
        'negative_count': neg,
        'positive_pct': pos_pct,
        'neutral_pct': neu_pct,
        'negative_pct': neg_pct,
        'average_score': round(avg_score, 4),
        'average_confidence': round(avg_conf, 4),
        'sentiment_verdict': verdict,
        'bullish_index': bullish_index,
    }
