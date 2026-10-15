from django.db import models
from django.utils import timezone

class TrackedStock(models.Model):
    EXCHANGE_CHOICES = [
        ('NSE', 'National Stock Exchange (India)'),
        ('BSE', 'Bombay Stock Exchange (India)'),
        ('NASDAQ', 'NASDAQ (US)'),
        ('NYSE', 'New York Stock Exchange (US)'),
        ('INDEX', 'Market Index'),
    ]

    ticker = models.CharField(max_length=25, unique=True, db_index=True)
    name = models.CharField(max_length=150)
    exchange = models.CharField(max_length=25, choices=EXCHANGE_CHOICES, default='NSE')
    currency = models.CharField(max_length=10, default='INR')
    sector = models.CharField(max_length=100, blank=True, default='')
    is_watchlist = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ticker']

    def __str__(self):
        return f"{self.ticker} ({self.name})"


class FinancialNews(models.Model):
    SENTIMENT_CHOICES = [
        ('positive', 'Positive'),
        ('neutral', 'Neutral'),
        ('negative', 'Negative'),
    ]

    ticker = models.CharField(max_length=25, db_index=True)
    headline = models.CharField(max_length=600)
    summary = models.TextField(blank=True, default='')
    publisher = models.CharField(max_length=150, blank=True, default='')
    url = models.URLField(max_length=1000, unique=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    sentiment_label = models.CharField(max_length=20, choices=SENTIMENT_CHOICES, default='neutral')
    sentiment_score = models.FloatField(default=0.0)  # normalized compound polarity -1.0 to 1.0
    confidence = models.FloatField(default=0.0)       # model confidence 0.0 to 1.0
    positive_prob = models.FloatField(default=0.0)
    neutral_prob = models.FloatField(default=0.0)
    negative_prob = models.FloatField(default=0.0)
    model_name = models.CharField(max_length=80, default='ProsusAI/finbert')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['ticker', '-published_at']),
        ]

    def __str__(self):
        return f"[{self.ticker}] {self.headline[:60]} ({self.sentiment_label})"


class SentimentAlert(models.Model):
    ALERT_TYPES = [
        ('BULLISH_SURGE', 'Bullish Sentiment Surge'),
        ('BEARISH_PLUNGE', 'Bearish Sentiment Plunge'),
        ('RAPID_REVERSAL', 'Sentiment Trend Reversal'),
        ('HIGH_VOLATILITY', 'Unusual News Volatility'),
    ]

    ticker = models.CharField(max_length=25, db_index=True)
    company_name = models.CharField(max_length=150, blank=True, default='')
    alert_type = models.CharField(max_length=40, choices=ALERT_TYPES, default='BULLISH_SURGE')
    direction = models.CharField(max_length=20, default='BULLISH')  # 'BULLISH', 'BEARISH', 'VOLATILE'
    previous_score = models.FloatField(default=0.0)
    current_score = models.FloatField(default=0.0)
    headline_count = models.IntegerField(default=1)
    explanation = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Alert: {self.ticker} {self.alert_type} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
