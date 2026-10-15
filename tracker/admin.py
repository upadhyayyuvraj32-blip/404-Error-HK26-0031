from django.contrib import admin
from .models import TrackedStock, FinancialNews, SentimentAlert

@admin.register(TrackedStock)
class TrackedStockAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'name', 'exchange', 'currency', 'is_watchlist', 'is_active')
    search_fields = ('ticker', 'name')
    list_filter = ('exchange', 'is_watchlist', 'is_active')

@admin.register(FinancialNews)
class FinancialNewsAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'headline', 'publisher', 'sentiment_label', 'confidence', 'published_at')
    search_fields = ('ticker', 'headline', 'publisher')
    list_filter = ('sentiment_label', 'model_name')

@admin.register(SentimentAlert)
class SentimentAlertAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'alert_type', 'direction', 'previous_score', 'current_score', 'created_at')
    search_fields = ('ticker', 'company_name', 'explanation')
    list_filter = ('alert_type', 'direction', 'is_read')
