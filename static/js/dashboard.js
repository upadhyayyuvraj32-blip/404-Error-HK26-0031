/**
 * TrendPulse AI - Main Frontend Dashboard Controller
 * Vanilla JavaScript implementation integrating:
 * - TradingView Lightweight Charts
 * - Chart.js Sentiment Visualizations
 * - Real-time Django REST API Endpoints
 */

// Application State
let currentTicker = typeof DEFAULT_TICKER !== 'undefined' ? DEFAULT_TICKER : 'RELIANCE.NS';
let currentTimeRange = '1M';
let currentChartType = 'candles';
let currentMarketFilter = 'IN';

let tvChart = null;
let candleSeries = null;
let volumeSeries = null;
let areaSeries = null;
let sentimentDonutChart = null;
let searchDebounceTimer = null;

// Preset tickers for peer comparison
const COMPARISON_TICKERS = ['RELIANCE.NS', 'TCS.NS', 'TATAMOTORS.NS', 'AAPL', 'NVDA'];

const POPULAR_TICKERS = [
    { ticker: 'RELIANCE.NS', name: 'Reliance' },
    { ticker: 'TCS.NS', name: 'TCS' },
    { ticker: 'TATAMOTORS.NS', name: 'Tata Motors' },
    { ticker: 'INFY.NS', name: 'Infosys' },
    { ticker: 'HDFCBANK.NS', name: 'HDFC Bank' },
    { ticker: 'AAPL', name: 'Apple' },
    { ticker: 'NVDA', name: 'NVIDIA' },
    { ticker: 'TSLA', name: 'Tesla' }
];

// Document Ready Initialization
document.addEventListener('DOMContentLoaded', () => {
    initChart();
    initSearch();
    renderPopularChips();
    setupTimeframeButtons();

    // Initial Data Loads
    refreshMarketOverview();
    loadStockData(currentTicker);
    loadAlerts();
    loadCompanyComparison();
    updateWatchlistCount();

    // Periodic live refresh: Indices every 60s
    setInterval(refreshMarketOverview, 60000);
});

/* -------------------------------------------------------------
 * 1. Market Overview Indices (Feature A)
 * ------------------------------------------------------------- */
async function refreshMarketOverview() {
    const timeElem = document.getElementById('indices-timestamp');
    if (timeElem) timeElem.textContent = 'Updating quotes...';

    try {
        const res = await fetch('/api/market-overview/');
        const data = await res.json();

        if (data.status === 'success' && data.data) {
            data.data.forEach(idx => {
                const isPos = idx.is_positive;
                const sign = isPos ? '+' : '';
                const changeClass = isPos ? 'text-emerald-400' : 'text-rose-400';
                const badgeBg = isPos ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' : 'bg-rose-500/15 text-rose-300 border-rose-500/30';

                if (idx.ticker === '^NSEI') {
                    setElemText('nifty-price', formatNumber(idx.price));
                    setElemText('nifty-change', `${sign}${formatNumber(idx.change)} (${sign}${idx.percent_change}%)`);
                    setElemClass('nifty-change', `text-xs mono-num font-semibold ${changeClass}`);
                    setElemText('nifty-badge', `${sign}${idx.percent_change}%`);
                    setElemClass('nifty-badge', `px-2 py-0.5 text-xs font-semibold rounded border ${badgeBg}`);
                } else if (idx.ticker === '^BSESN') {
                    setElemText('sensex-price', formatNumber(idx.price));
                    setElemText('sensex-change', `${sign}${formatNumber(idx.change)} (${sign}${idx.percent_change}%)`);
                    setElemClass('sensex-change', `text-xs mono-num font-semibold ${changeClass}`);
                    setElemText('sensex-badge', `${sign}${idx.percent_change}%`);
                    setElemClass('sensex-badge', `px-2 py-0.5 text-xs font-semibold rounded border ${badgeBg}`);
                } else if (idx.ticker === '^GSPC') {
                    setElemText('sp500-price', formatNumber(idx.price));
                    setElemText('sp500-change', `${sign}${formatNumber(idx.change)} (${sign}${idx.percent_change}%)`);
                    setElemClass('sp500-change', `text-xs mono-num font-semibold ${changeClass}`);
                    setElemText('sp500-badge', `${sign}${idx.percent_change}%`);
                    setElemClass('sp500-badge', `px-2 py-0.5 text-xs font-semibold rounded border ${badgeBg}`);
                }
            });

            if (timeElem) {
                const now = new Date();
                timeElem.textContent = `Updated: ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
            }
        }
    } catch (err) {
        console.error('Error fetching market overview:', err);
        if (timeElem) timeElem.textContent = 'Data delayed';
    }
}

/* -------------------------------------------------------------
 * 2. Stock Selection & Loading (Feature B)
 * ------------------------------------------------------------- */
async function selectStock(ticker) {
    if (!ticker) return;
    currentTicker = ticker.toUpperCase();

    // Close any search dropdowns
    hideSearchDropdowns();

    // Trigger full updates
    await loadStockData(currentTicker);
}

async function loadStockData(ticker) {
    // 1. Fetch Quote
    await loadStockQuote(ticker);

    // 2. Fetch Chart Series
    await loadStockHistory(ticker, currentTimeRange);

    // 3. Fetch Sentiment Consensus
    await loadSentimentSummary(ticker);

    // 4. Fetch News Feed
    await loadStockNews(ticker);
}

async function loadStockQuote(ticker) {
    try {
        const res = await fetch(`/api/stock/${encodeURIComponent(ticker)}/`);
        const json = await res.json();

        if (json.status === 'success' && json.data) {
            const q = json.data;
            const currencySymbol = q.currency === 'INR' ? '₹' : (q.currency === 'USD' ? '$' : q.currency + ' ');
            const isPos = q.is_positive;
            const sign = isPos ? '+' : '';

            setElemText('stock-name', q.name);
            setElemText('stock-ticker-badge', q.ticker);
            setElemText('stock-exchange-badge', q.exchange);
            setElemText('stock-currency', q.currency);
            setElemText('stock-current-price', `${currencySymbol}${formatNumber(q.current_price)}`);
            setElemText('stock-price-change', `${sign}${formatNumber(q.change)} (${sign}${q.percent_change}%)`);

            const changeElem = document.getElementById('stock-price-change');
            if (changeElem) {
                changeElem.className = isPos 
                    ? 'text-xs sm:text-sm mono-num font-bold px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                    : 'text-xs sm:text-sm mono-num font-bold px-2 py-0.5 rounded bg-rose-500/15 text-rose-400 border border-rose-500/30';
            }

            setElemText('stock-day-range', `${currencySymbol}${formatNumber(q.day_low)} - ${currencySymbol}${formatNumber(q.day_high)}`);
            setElemText('stock-52w-range', `${currencySymbol}${formatNumber(q.fifty_two_low)} - ${currencySymbol}${formatNumber(q.fifty_two_high)}`);

            // Watchlist button status
            updateWatchlistBtnState(q.is_watchlist);
        }
    } catch (err) {
        console.error('Error fetching stock quote:', err);
    }
}

/* -------------------------------------------------------------
 * 3. TradingView Lightweight Chart (Feature E)
 * ------------------------------------------------------------- */
function initChart() {
    const container = document.getElementById('tv-chart-container');
    if (!container || !window.LightweightCharts) return;

    // Reset container contents
    container.innerHTML = '<div id="chart-loader" class="hidden absolute inset-0 bg-dark-900/80 backdrop-blur-sm flex flex-col items-center justify-center z-10"><i class="ph ph-spinner animate-spin text-3xl text-accent mb-2"></i><span class="text-xs text-slate-300 font-medium">Loading candles...</span></div>';

    tvChart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: container.clientHeight,
        layout: {
            background: { type: 'solid', color: '#070a12' },
            textColor: '#94a3b8',
            fontSize: 12,
            fontFamily: 'Inter, sans-serif',
        },
        grid: {
            vertLines: { color: '#131d33', style: 1 },
            horzLines: { color: '#131d33', style: 1 },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: {
                color: '#38bdf8',
                width: 1,
                style: 3,
                labelBackgroundColor: '#1e293b',
            },
            horzLine: {
                color: '#38bdf8',
                width: 1,
                style: 3,
                labelBackgroundColor: '#1e293b',
            },
        },
        rightPriceScale: {
            borderColor: '#1e2c4a',
            autoScale: true,
        },
        timeScale: {
            borderColor: '#1e2c4a',
            timeVisible: true,
            secondsVisible: false,
        },
    });

    // Volume Series
    volumeSeries = tvChart.addHistogramSeries({
        color: '#26a69a',
        priceFormat: { type: 'volume' },
        priceScaleId: '', // overlay
    });
    volumeSeries.priceScale().applyOptions({
        scaleMargins: {
            top: 0.8,
            bottom: 0,
        },
    });

    // Candlestick Series
    candleSeries = tvChart.addCandlestickSeries({
        upColor: '#10b981',
        downColor: '#f43f5e',
        borderUpColor: '#10b981',
        borderDownColor: '#f43f5e',
        wickUpColor: '#10b981',
        wickDownColor: '#f43f5e',
    });

    // Area Series (hidden initially)
    areaSeries = tvChart.addAreaSeries({
        topColor: 'rgba(56, 189, 248, 0.4)',
        bottomColor: 'rgba(56, 189, 248, 0.0)',
        lineColor: '#38bdf8',
        lineWidth: 2,
        visible: false,
    });

    // Responsive window resize
    window.addEventListener('resize', () => {
        if (tvChart && container) {
            tvChart.applyOptions({
                width: container.clientWidth,
                height: container.clientHeight,
            });
        }
    });
}

async function loadStockHistory(ticker, range) {
    showChartLoader(true);
    try {
        const res = await fetch(`/api/stock/${encodeURIComponent(ticker)}/history/?range=${range}`);
        const json = await res.json();

        if (json.status === 'success' && json.data) {
            const data = json.data;
            const candles = data.candles || [];
            const volumes = data.volumes || [];

            if (candleSeries && candles.length > 0) {
                candleSeries.setData(candles);
                volumeSeries.setData(volumes);

                // Format for area chart as well
                const areaData = candles.map(c => ({ time: c.time, value: c.close }));
                areaSeries.setData(areaData);

                tvChart.timeScale().fitContent();
            }

            const tsElem = document.getElementById('chart-data-timestamp');
            if (tsElem) {
                tsElem.textContent = `Range: ${range} • ${candles.length} Data Points • Currency: ${data.currency}`;
            }
        }
    } catch (err) {
        console.error('Error fetching stock history:', err);
    } finally {
        showChartLoader(false);
    }
}

function toggleChartType(type) {
    currentChartType = type;
    const btnCandles = document.getElementById('chart-type-candles');
    const btnArea = document.getElementById('chart-type-area');

    if (type === 'candles') {
        candleSeries.applyOptions({ visible: true });
        volumeSeries.applyOptions({ visible: true });
        areaSeries.applyOptions({ visible: false });

        btnCandles.className = 'px-2 py-1 rounded bg-dark-700 text-accent font-medium';
        btnArea.className = 'px-2 py-1 rounded text-slate-400 hover:text-white';
    } else {
        candleSeries.applyOptions({ visible: false });
        volumeSeries.applyOptions({ visible: false });
        areaSeries.applyOptions({ visible: true });

        btnArea.className = 'px-2 py-1 rounded bg-dark-700 text-accent font-medium';
        btnCandles.className = 'px-2 py-1 rounded text-slate-400 hover:text-white';
    }
}

function setupTimeframeButtons() {
    const buttons = document.querySelectorAll('.timeframe-btn');
    buttons.forEach(btn => {
        btn.addEventListener('click', () => {
            buttons.forEach(b => {
                b.className = 'timeframe-btn px-2.5 py-1 rounded hover:bg-dark-700 transition text-slate-300';
            });
            btn.className = 'timeframe-btn px-2.5 py-1 rounded bg-accent text-dark-900 font-bold shadow transition';

            currentTimeRange = btn.getAttribute('data-range');
            loadStockHistory(currentTicker, currentTimeRange);
        });
    });
}

function showChartLoader(show) {
    const loader = document.getElementById('chart-loader');
    if (loader) {
        loader.className = show
            ? 'absolute inset-0 bg-dark-900/80 backdrop-blur-sm flex flex-col items-center justify-center z-10'
            : 'hidden';
    }
}

/* -------------------------------------------------------------
 * 4. AI Sentiment Intelligence & Chart.js Donut (Feature D)
 * ------------------------------------------------------------- */
async function loadSentimentSummary(ticker) {
    try {
        const res = await fetch(`/api/stock/${encodeURIComponent(ticker)}/sentiment-summary/`);
        const json = await res.json();

        if (json.status === 'success' && json.data) {
            const data = json.data;
            const m = data.metrics;

            // Update Bullish Index (0 to 100)
            setElemText('bullish-index-val', m.bullish_index);
            const gaugeBar = document.getElementById('bullish-gauge-bar');
            if (gaugeBar) {
                gaugeBar.style.width = `${Math.min(Math.max(m.bullish_index, 5), 100)}%`;
            }

            // Verdict Chip
            const verdictElem = document.getElementById('sentiment-verdict-badge');
            if (verdictElem) {
                verdictElem.textContent = m.sentiment_verdict;
                if (m.sentiment_verdict.includes('Bullish')) {
                    verdictElem.className = 'inline-flex items-center gap-1 px-3 py-1 text-xs font-bold rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30';
                } else if (m.sentiment_verdict.includes('Bearish')) {
                    verdictElem.className = 'inline-flex items-center gap-1 px-3 py-1 text-xs font-bold rounded-full bg-rose-500/15 text-rose-300 border border-rose-500/30';
                } else {
                    verdictElem.className = 'inline-flex items-center gap-1 px-3 py-1 text-xs font-bold rounded-full bg-dark-700 text-slate-200 border border-dark-600';
                }
            }

            // Polarity & Confidence
            const sign = m.average_score > 0 ? '+' : '';
            setElemText('compound-polarity-val', `${sign}${m.average_score}`);
            setElemText('avg-confidence-val', `${Math.round(m.average_confidence * 100)}%`);
            setElemText('news-sample-count', `${m.total_articles} articles analyzed`);

            // Distribution percentages
            setElemText('pct-positive', `${m.positive_pct}%`);
            setElemText('pct-neutral', `${m.neutral_pct}%`);
            setElemText('pct-negative', `${m.negative_pct}%`);

            // Sentiment vs Price Alignment Text
            const alignElem = document.getElementById('sentiment-alignment-text');
            if (alignElem) {
                const badge = data.alignment_badge;
                let badgeColor = badge === 'aligned' ? 'text-emerald-400' : (badge === 'divergent' ? 'text-amber-400' : 'text-slate-300');
                alignElem.innerHTML = `<span class="font-bold ${badgeColor}">${data.sentiment_price_alignment}</span>. In the last observation window, the stock price change is <span class="font-mono font-semibold">${data.price_change_pct}%</span> while aggregate news polarity is <span class="font-mono font-semibold">${m.average_score}</span>.`;
            }

            // Render Donut Chart
            updateSentimentDonut(m.positive_pct, m.neutral_pct, m.negative_pct);
        }
    } catch (err) {
        console.error('Error fetching sentiment summary:', err);
    }
}

function updateSentimentDonut(pos, neu, neg) {
    const canvas = document.getElementById('sentiment-donut-chart');
    if (!canvas || !window.Chart) return;

    if (sentimentDonutChart) {
        sentimentDonutChart.destroy();
    }

    const ctx = canvas.getContext('2d');
    sentimentDonutChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Positive', 'Neutral', 'Negative'],
            datasets: [{
                data: [pos, neu, neg],
                backgroundColor: [
                    '#10b981', // emerald
                    '#64748b', // slate
                    '#f43f5e', // rose
                ],
                borderWidth: 2,
                borderColor: '#0e1526',
                hoverOffset: 4,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '75%',
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => ` ${ctx.label}: ${ctx.raw}%`
                    }
                }
            }
        }
    });
}

/* -------------------------------------------------------------
 * 5. Real-time News Collection Feed (Feature C)
 * ------------------------------------------------------------- */
async function loadStockNews(ticker) {
    const container = document.getElementById('news-feed-container');
    if (!container) return;

    // Show skeletons
    container.innerHTML = `
        <div class="terminal-card p-4 skeleton h-36"></div>
        <div class="terminal-card p-4 skeleton h-36"></div>
        <div class="terminal-card p-4 skeleton h-36"></div>
    `;

    try {
        const res = await fetch(`/api/stock/${encodeURIComponent(ticker)}/news/?limit=9`);
        const json = await res.json();

        if (json.status === 'success' && json.data && json.data.length > 0) {
            container.innerHTML = '';
            json.data.forEach(item => {
                const label = item.sentiment_label.toLowerCase();
                let badgeClass = 'bg-slate-500/15 text-slate-300 border-slate-500/30';
                let iconClass = 'ph-minus text-slate-400';

                if (label === 'positive') {
                    badgeClass = 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
                    iconClass = 'ph-arrow-up-right text-emerald-400';
                } else if (label === 'negative') {
                    badgeClass = 'bg-rose-500/15 text-rose-300 border-rose-500/30';
                    iconClass = 'ph-arrow-down-right text-rose-400';
                }

                const card = document.createElement('div');
                card.className = 'terminal-card p-4 flex flex-col justify-between hover:border-dark-500 transition';
                card.innerHTML = `
                    <div>
                        <div class="flex items-center justify-between gap-2 mb-2">
                            <span class="text-[11px] font-semibold text-slate-400 flex items-center gap-1">
                                <i class="ph ph-newspaper"></i> ${escapeHtml(item.publisher || 'Financial Press')}
                            </span>
                            <span class="px-2 py-0.5 text-[10px] font-bold uppercase rounded border flex items-center gap-1 ${badgeClass}">
                                <i class="ph-bold ${iconClass}"></i> ${item.sentiment_label} (${item.confidence_pct}%)
                            </span>
                        </div>
                        <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer" class="text-xs sm:text-sm font-semibold text-white hover:text-accent line-clamp-2 leading-snug transition">
                            ${escapeHtml(item.headline)}
                        </a>
                    </div>
                    <div class="mt-4 pt-2 border-t border-dark-600 flex items-center justify-between text-[10px] text-slate-500">
                        <span>${item.published_at_display}</span>
                        <span class="text-accent hover:underline flex items-center gap-0.5">
                            Source Link <i class="ph ph-arrow-square-out"></i>
                        </span>
                    </div>
                `;
                container.appendChild(card);
            });
        } else {
            container.innerHTML = `
                <div class="col-span-full p-8 text-center terminal-card">
                    <i class="ph ph-newspaper-clipping text-3xl text-slate-500 mb-2 inline-block"></i>
                    <p class="text-xs text-slate-400">No recent articles found for this ticker. Monitoring financial feeds...</p>
                </div>
            `;
        }
    } catch (err) {
        console.error('Error fetching news:', err);
        container.innerHTML = `
            <div class="col-span-full p-6 text-center terminal-card text-rose-400 text-xs">
                Unable to load financial news feed. Please verify network connectivity.
            </div>
        `;
    }
}

/* -------------------------------------------------------------
 * 6. Sentiment Change Alerts (Feature F)
 * ------------------------------------------------------------- */
async function loadAlerts() {
    const container = document.getElementById('alerts-feed-container');
    const badge = document.getElementById('alerts-count-chip');
    if (!container) return;

    try {
        const res = await fetch('/api/alerts/?limit=6');
        const json = await res.json();

        if (json.status === 'success' && json.data) {
            const alerts = json.data;
            if (badge) badge.textContent = `${alerts.length} Alerts`;

            if (alerts.length === 0) {
                container.innerHTML = `
                    <div class="p-4 text-center text-slate-500 text-xs">
                        No unusual sentiment spikes detected in recent coverage.
                    </div>
                `;
                return;
            }

            container.innerHTML = '';
            alerts.forEach(a => {
                const dir = a.direction;
                const isBull = dir === 'BULLISH';
                const pillBg = isBull ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' : 'bg-rose-500/15 text-rose-300 border-rose-500/30';
                const pillIcon = isBull ? 'ph-trend-up' : 'ph-trend-down';

                const alertDiv = document.createElement('div');
                alertDiv.className = 'p-3 rounded-lg bg-dark-800 border border-dark-600 hover:border-dark-500 transition cursor-pointer';
                alertDiv.onclick = () => selectStock(a.ticker);
                alertDiv.innerHTML = `
                    <div class="flex items-center justify-between gap-2 mb-1.5">
                        <div class="flex items-center gap-1.5">
                            <span class="font-bold text-xs text-white">${escapeHtml(a.company_name)}</span>
                            <span class="text-[10px] text-slate-400 font-mono">(${a.ticker})</span>
                        </div>
                        <span class="px-1.5 py-0.5 text-[10px] font-bold rounded border uppercase flex items-center gap-1 ${pillBg}">
                            <i class="ph-bold ${pillIcon}"></i> ${a.alert_type.replace('_', ' ')}
                        </span>
                    </div>
                    <p class="text-[11px] text-slate-300 leading-relaxed mb-2">${escapeHtml(a.explanation)}</p>
                    <div class="flex items-center justify-between text-[10px] text-slate-500 border-t border-dark-700/60 pt-1.5">
                        <span>Score Shift: <b class="font-mono text-slate-300">${a.previous_score} → ${a.current_score}</b></span>
                        <span>${a.time_ago}</span>
                    </div>
                `;
                container.appendChild(alertDiv);
            });
        }
    } catch (err) {
        console.error('Error fetching alerts:', err);
    }
}

/* -------------------------------------------------------------
 * 7. Peer Company Comparison Matrix (Feature G)
 * ------------------------------------------------------------- */
async function loadCompanyComparison() {
    const tbody = document.getElementById('comparison-tbody');
    if (!tbody) return;

    try {
        const tickers = COMPARISON_TICKERS.join(',');
        const res = await fetch(`/api/compare/?tickers=${tickers}`);
        const json = await res.json();

        if (json.status === 'success' && json.data) {
            tbody.innerHTML = '';
            json.data.forEach(item => {
                const isPos = item.is_positive;
                const sign = isPos ? '+' : '';
                const changeColor = isPos ? 'text-emerald-400' : 'text-rose-400';
                const currSymbol = item.currency === 'INR' ? '₹' : '$';

                const tr = document.createElement('tr');
                tr.className = 'hover:bg-dark-800/60 transition';
                tr.innerHTML = `
                    <td class="py-2.5 px-3">
                        <div class="font-bold text-white text-xs">${escapeHtml(item.name)}</div>
                        <div class="text-[10px] text-slate-400 font-mono">${item.ticker} • ${item.exchange}</div>
                    </td>
                    <td class="py-2.5 px-3 text-right font-mono font-semibold text-white">
                        ${currSymbol}${formatNumber(item.price)}
                    </td>
                    <td class="py-2.5 px-3 text-right font-mono font-bold ${changeColor}">
                        ${sign}${item.change_pct}%
                    </td>
                    <td class="py-2.5 px-3 text-center">
                        <span class="px-2 py-0.5 rounded text-[10px] font-bold ${item.sentiment_verdict.includes('Bullish') ? 'bg-emerald-500/15 text-emerald-300' : (item.sentiment_verdict.includes('Bearish') ? 'bg-rose-500/15 text-rose-300' : 'bg-dark-700 text-slate-300')}">
                            ${item.sentiment_verdict}
                        </span>
                    </td>
                    <td class="py-2.5 px-3 text-center">
                        <div class="w-28 mx-auto bg-dark-700 rounded-full h-1.5 flex overflow-hidden">
                            <div class="bg-emerald-400 h-1.5" style="width: ${item.positive_pct}%"></div>
                            <div class="bg-slate-400 h-1.5" style="width: ${item.neutral_pct}%"></div>
                            <div class="bg-rose-500 h-1.5" style="width: ${item.negative_pct}%"></div>
                        </div>
                        <span class="text-[9px] text-slate-400 mt-1 block">${item.positive_pct}% / ${item.neutral_pct}% / ${item.negative_pct}%</span>
                    </td>
                    <td class="py-2.5 px-3 text-center font-mono text-slate-300">
                        ${item.article_count}
                    </td>
                    <td class="py-2.5 px-3 text-center">
                        <button onclick="selectStock('${item.ticker}')" class="px-2.5 py-1 text-[11px] font-semibold bg-dark-700 hover:bg-accent hover:text-dark-900 text-slate-200 rounded transition">
                            Analyze
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (err) {
        console.error('Error fetching comparison matrix:', err);
    }
}

/* -------------------------------------------------------------
 * 8. Search and Autocomplete (Feature B)
 * ------------------------------------------------------------- */
function initSearch() {
    const desktopInput = document.getElementById('global-search-input');
    const mobileInput = document.getElementById('mobile-search-input');

    if (desktopInput) {
        desktopInput.addEventListener('input', (e) => handleSearchInput(e.target.value, 'search-dropdown'));
        desktopInput.addEventListener('focus', (e) => handleSearchInput(e.target.value, 'search-dropdown'));
    }

    if (mobileInput) {
        mobileInput.addEventListener('input', (e) => handleSearchInput(e.target.value, 'mobile-search-dropdown'));
    }

    // Close on outside click
    document.addEventListener('click', (e) => {
        if (!e.target.closest('#global-search-input') && !e.target.closest('#search-dropdown')) {
            hideSearchDropdowns();
        }
    });
}

function handleSearchInput(val, dropdownId) {
    clearTimeout(searchDebounceTimer);
    const dropdown = document.getElementById(dropdownId);
    if (!dropdown) return;

    searchDebounceTimer = setTimeout(async () => {
        try {
            const res = await fetch(`/api/search/?q=${encodeURIComponent(val.trim())}`);
            const json = await res.json();

            if (json.status === 'success' && json.data && json.data.length > 0) {
                dropdown.innerHTML = '';
                json.data.forEach(item => {
                    const div = document.createElement('div');
                    div.className = 'px-4 py-2.5 hover:bg-dark-700 cursor-pointer flex items-center justify-between border-b border-dark-600/40 text-xs transition';
                    div.onclick = () => selectStock(item.ticker);
                    div.innerHTML = `
                        <div>
                            <span class="font-bold text-white">${escapeHtml(item.name)}</span>
                            <span class="ml-2 text-accent font-mono text-[11px]">${item.ticker}</span>
                        </div>
                        <span class="text-[10px] text-slate-400 bg-dark-900 px-1.5 py-0.5 rounded">${item.exchange}</span>
                    `;
                    dropdown.appendChild(div);
                });
                dropdown.classList.remove('hidden');
            } else {
                dropdown.innerHTML = '<div class="p-3 text-xs text-slate-400 text-center">No matching tickers found. Press Enter to lookup anyway.</div>';
                dropdown.classList.remove('hidden');
            }
        } catch (err) {
            console.error('Search error:', err);
        }
    }, 200);
}

function hideSearchDropdowns() {
    const d1 = document.getElementById('search-dropdown');
    const d2 = document.getElementById('mobile-search-dropdown');
    if (d1) d1.classList.add('hidden');
    if (d2) d2.classList.add('hidden');
}

/* -------------------------------------------------------------
 * 9. Watchlist Management
 * ------------------------------------------------------------- */
async function toggleCurrentWatchlist() {
    try {
        const res = await fetch('/api/watchlist/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticker: currentTicker })
        });
        const json = await res.json();
        if (json.status === 'success') {
            updateWatchlistBtnState(json.is_watchlist);
            updateWatchlistCount();
        }
    } catch (err) {
        console.error('Watchlist toggle error:', err);
    }
}

function updateWatchlistBtnState(isWatchlist) {
    const btnText = document.getElementById('watchlist-btn-text');
    const starIcon = document.getElementById('watchlist-star-icon');
    if (btnText && starIcon) {
        if (isWatchlist) {
            btnText.textContent = 'In Watchlist';
            starIcon.className = 'ph-fill ph-star text-amber-400';
        } else {
            btnText.textContent = 'Add to Watchlist';
            starIcon.className = 'ph ph-star text-amber-400';
        }
    }
}

async function updateWatchlistCount() {
    try {
        const res = await fetch('/api/watchlist/');
        const json = await res.json();
        if (json.status === 'success' && json.data) {
            setElemText('watchlist-count-badge', json.data.length);
        }
    } catch (err) {
        console.error(err);
    }
}

async function openWatchlistModal() {
    const modal = document.getElementById('watchlist-modal');
    const container = document.getElementById('watchlist-modal-content');
    if (!modal || !container) return;

    container.innerHTML = '<div class="text-center p-4 text-xs text-slate-400">Loading watchlist...</div>';
    modal.classList.remove('hidden');

    try {
        const res = await fetch('/api/watchlist/');
        const json = await res.json();

        if (json.status === 'success' && json.data && json.data.length > 0) {
            container.innerHTML = '';
            json.data.forEach(item => {
                const div = document.createElement('div');
                div.className = 'flex items-center justify-between p-2.5 rounded-lg bg-dark-900 border border-dark-600 hover:border-dark-500 transition';
                div.innerHTML = `
                    <div class="cursor-pointer" onclick="selectStock('${item.ticker}'); closeWatchlistModal();">
                        <div class="font-bold text-white text-xs">${escapeHtml(item.name)}</div>
                        <div class="text-[10px] text-accent font-mono">${item.ticker} (${item.exchange})</div>
                    </div>
                    <div class="flex items-center gap-3">
                        <span class="font-mono text-xs font-bold text-white">${formatNumber(item.price)}</span>
                        <button onclick="removeFromWatchlist('${item.ticker}')" title="Remove" class="text-rose-400 hover:text-rose-300 p-1">
                            <i class="ph ph-trash"></i>
                        </button>
                    </div>
                `;
                container.appendChild(div);
            });
        } else {
            container.innerHTML = '<div class="text-center p-6 text-xs text-slate-400">Your watchlist is currently empty. Click "Add to Watchlist" on any stock to track it here.</div>';
        }
    } catch (err) {
        container.innerHTML = '<div class="text-center p-4 text-xs text-rose-400">Error loading watchlist.</div>';
    }
}

function closeWatchlistModal() {
    const modal = document.getElementById('watchlist-modal');
    if (modal) modal.classList.add('hidden');
}

async function removeFromWatchlist(ticker) {
    await toggleCurrentWatchlist();
    openWatchlistModal();
}

/* -------------------------------------------------------------
 * 10. UI Helpers
 * ------------------------------------------------------------- */
function renderPopularChips() {
    const container = document.getElementById('popular-chips-container');
    if (!container) return;

    container.innerHTML = '';
    POPULAR_TICKERS.forEach(item => {
        const chip = document.createElement('button');
        chip.className = 'px-2.5 py-1 rounded bg-dark-800 hover:bg-dark-700 border border-dark-600 text-slate-300 whitespace-nowrap text-[11px] font-medium transition';
        chip.textContent = `${item.name} (${item.ticker.replace('.NS', '')})`;
        chip.onclick = () => selectStock(item.ticker);
        container.appendChild(chip);
    });
}

function switchMarketFilter(market) {
    currentMarketFilter = market;
    const btnIn = document.getElementById('btn-market-in');
    const btnUs = document.getElementById('btn-market-us');

    if (market === 'IN') {
        btnIn.className = 'px-2.5 py-1 rounded bg-dark-700 text-accent font-semibold transition';
        btnUs.className = 'px-2.5 py-1 rounded text-slate-400 hover:text-slate-200 transition';
        selectStock('RELIANCE.NS');
    } else {
        btnUs.className = 'px-2.5 py-1 rounded bg-dark-700 text-accent font-semibold transition';
        btnIn.className = 'px-2.5 py-1 rounded text-slate-400 hover:text-slate-200 transition';
        selectStock('AAPL');
    }
}

function formatNumber(num) {
    if (num === null || num === undefined || isNaN(num)) return '--';
    return Number(num).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function setElemText(id, text) {
    const elem = document.getElementById(id);
    if (elem) elem.textContent = text;
}

function setElemClass(id, className) {
    const elem = document.getElementById(id);
    if (elem) elem.className = className;
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
