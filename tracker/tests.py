from django.test import TestCase, Client
from django.urls import reverse
from tracker.models import TrackedStock, FinancialNews, SentimentAlert
from tracker.sentiment_engine import (
    analyze_headline_sentiment,
    aggregate_sentiment_metrics,
    _lexicon_sentiment_analysis,
)
from tracker.stock_service import get_stock_quote, get_stock_history, search_stocks
from tracker.alert_engine import evaluate_and_generate_alerts


class SentimentEngineTests(TestCase):
    def test_positive_headline_lexicon(self):
        res = _lexicon_sentiment_analysis("Company reports record profit and massive revenue growth")
        self.assertEqual(res["label"], "positive")
        self.assertGreater(res["score"], 0)
        self.assertGreaterEqual(res["confidence"], 0.5)

    def test_negative_headline_lexicon(self):
        res = _lexicon_sentiment_analysis("Shares plunge 12% amid fraud investigation and severe quarterly loss")
        self.assertEqual(res["label"], "negative")
        self.assertLess(res["score"], 0)
        self.assertGreaterEqual(res["confidence"], 0.5)

    def test_neutral_headline_lexicon(self):
        res = _lexicon_sentiment_analysis("Board of directors scheduled routine quarterly review meeting")
        self.assertEqual(res["label"], "neutral")

    def test_analyze_headline_sentiment(self):
        res = analyze_headline_sentiment("Tata Motors quarterly profit jumps 45%")
        self.assertIn(res["label"], ["positive", "neutral", "negative"])
        self.assertIn("score", res)
        self.assertIn("confidence", res)
        self.assertIn("model_name", res)

    def test_aggregate_sentiment_metrics(self):
        mock_articles = [
            {"sentiment_label": "positive", "sentiment_score": 0.8, "confidence": 0.9},
            {"sentiment_label": "positive", "sentiment_score": 0.6, "confidence": 0.85},
            {"sentiment_label": "negative", "sentiment_score": -0.4, "confidence": 0.75},
            {"sentiment_label": "neutral", "sentiment_score": 0.0, "confidence": 0.8},
        ]
        metrics = aggregate_sentiment_metrics(mock_articles)
        self.assertEqual(metrics["total_articles"], 4)
        self.assertEqual(metrics["positive_count"], 2)
        self.assertEqual(metrics["negative_count"], 1)
        self.assertEqual(metrics["neutral_count"], 1)
        self.assertEqual(metrics["positive_pct"], 50.0)
        self.assertEqual(metrics["negative_pct"], 25.0)
        self.assertEqual(metrics["neutral_pct"], 25.0)
        self.assertGreater(metrics["bullish_index"], 50.0)


class StockServiceTests(TestCase):
    def test_search_stocks(self):
        results = search_stocks("RELIANCE")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["ticker"], "RELIANCE.NS")

    def test_get_stock_quote_format(self):
        quote = get_stock_quote("RELIANCE.NS")
        self.assertIn("ticker", quote)
        self.assertIn("current_price", quote)
        self.assertIn("change", quote)
        self.assertIn("percent_change", quote)
        self.assertIn("exchange", quote)
        self.assertIn("currency", quote)

    def test_get_stock_history_format(self):
        hist = get_stock_history("RELIANCE.NS", "1M")
        self.assertIn("candles", hist)
        self.assertIn("volumes", hist)
        self.assertIn("range", hist)


class AlertEngineTests(TestCase):
    def test_alert_generation_on_bullish_surge(self):
        mock_news = [
            {"sentiment_label": "positive", "sentiment_score": 0.85, "confidence": 0.9},
            {"sentiment_label": "positive", "sentiment_score": 0.75, "confidence": 0.88},
            {"sentiment_label": "positive", "sentiment_score": 0.65, "confidence": 0.82},
            {"sentiment_label": "neutral", "sentiment_score": 0.0, "confidence": 0.7},
        ]
        alert = evaluate_and_generate_alerts("TEST_STOCK.NS", mock_news)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.direction, "BULLISH")
        self.assertEqual(alert.alert_type, "BULLISH_SURGE")


class APITests(TestCase):
    def setUp(self):
        self.client = Client()
        TrackedStock.objects.create(
            ticker="RELIANCE.NS",
            name="Reliance Industries Ltd",
            exchange="NSE",
            currency="INR",
            is_watchlist=True,
        )

    def test_dashboard_view(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TrendPulse")

    def test_api_market_overview(self):
        response = self.client.get(reverse("api_market_overview"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(len(data["data"]) >= 3)

    def test_api_stock_quote(self):
        response = self.client.get(reverse("api_stock_quote", kwargs={"ticker": "RELIANCE.NS"}))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["data"]["ticker"], "RELIANCE.NS")

    def test_api_stock_history(self):
        response = self.client.get(reverse("api_stock_history", kwargs={"ticker": "RELIANCE.NS"}) + "?range=1M")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("candles", data["data"])

    def test_api_stock_news(self):
        response = self.client.get(reverse("api_stock_news", kwargs={"ticker": "RELIANCE.NS"}) + "?limit=5")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

    def test_api_sentiment_summary(self):
        response = self.client.get(reverse("api_sentiment_summary", kwargs={"ticker": "RELIANCE.NS"}))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("metrics", data["data"])
        self.assertIn("ai_disclaimer", data["data"])

    def test_api_compare(self):
        response = self.client.get(reverse("api_company_comparison") + "?tickers=RELIANCE.NS,TCS.NS")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["data"]), 2)

    def test_api_alerts(self):
        response = self.client.get(reverse("api_alerts"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

    def test_api_search(self):
        response = self.client.get(reverse("api_search") + "?q=TCS")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(len(data["data"]) > 0)

    def test_api_watchlist(self):
        # GET watchlist
        response = self.client.get(reverse("api_watchlist"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(len(data["data"]) >= 1)

        # POST toggle
        post_response = self.client.post(
            reverse("api_watchlist"),
            data='{"ticker": "TCS.NS"}',
            content_type="application/json"
        )
        self.assertEqual(post_response.status_code, 200)
        post_data = post_response.json()
        self.assertEqual(post_data["status"], "success")
