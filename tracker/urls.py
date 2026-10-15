from django.urls import path
from . import views

urlpatterns = [
    # Main Dashboard UI
    path('', views.dashboard_view, name='dashboard'),

    # REST APIs
    path('api/market-overview/', views.api_market_overview, name='api_market_overview'),
    path('api/stock/<str:ticker>/', views.api_stock_quote, name='api_stock_quote'),
    path('api/stock/<str:ticker>/history/', views.api_stock_history, name='api_stock_history'),
    path('api/stock/<str:ticker>/news/', views.api_stock_news, name='api_stock_news'),
    path('api/stock/<str:ticker>/sentiment-summary/', views.api_sentiment_summary, name='api_sentiment_summary'),
    path('api/compare/', views.api_company_comparison, name='api_company_comparison'),
    path('api/alerts/', views.api_alerts, name='api_alerts'),
    path('api/search/', views.api_search, name='api_search'),
    path('api/watchlist/', views.api_watchlist, name='api_watchlist'),
]
