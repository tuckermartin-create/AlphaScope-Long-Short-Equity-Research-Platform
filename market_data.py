"""Downloads prices, company fundamentals, sectors, and news from Yahoo Finance.

Every download is cached so the app stays fast, and every failure is handled
so a slow connection or an unknown ticker does not break the app.
"""

from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
import json
import time
import urllib.request
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st


PRICE_REFRESH_SECONDS = 60
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0"}
BENCHMARK = "SPY"  # An S&P 500 fund, used as "the market".

FUNDAMENTAL_FIELDS = [
    "trailingPeRatio",
    "trailingForwardPeRatio",
    "trailingPegRatio",
    "trailingTotalRevenue",
    "trailingOperatingIncome",
    "trailingNetIncome",
    "annualTotalRevenue",
]


def get_json(url):
    """Download a web address and return its JSON content."""
    request = urllib.request.Request(url, headers=REQUEST_HEADERS)
    with urllib.request.urlopen(request, timeout=6) as response:
        return json.load(response)


def download_in_parallel(download, tickers):
    """Run one download per ticker at the same time. Failed tickers are skipped."""

    def safe_download(ticker):
        try:
            return ticker, download(ticker)
        except Exception:
            return ticker, None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = pool.map(safe_download, tickers)
    return {ticker: data for ticker, data in results if data is not None}


# ---------------------------------------------------------------------------
# Prices
# ---------------------------------------------------------------------------
def download_stock(ticker):
    """Download the latest price and five years of daily closes for one ticker."""
    result = get_json(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        "?range=5y&interval=1d"
    )["chart"]["result"][0]

    closes = pd.Series(
        result["indicators"]["quote"][0]["close"],
        index=pd.to_datetime(result["timestamp"], unit="s").normalize(),
    ).dropna()

    # Make the last point the latest market price so charts match the tables.
    price = result["meta"]["regularMarketPrice"]
    closes.iloc[-1] = price

    return {
        "name": result["meta"].get("longName", ticker),
        "price": price,
        "time": result["meta"].get("regularMarketTime"),
        "closes": closes,
    }


@st.cache_data(ttl=PRICE_REFRESH_SECONDS, show_spinner=False)
def fetch_market_data(tickers):
    """Return price data for each ticker that could be loaded (cached 1 minute)."""
    return download_in_parallel(download_stock, tickers)


# ---------------------------------------------------------------------------
# Company fundamentals and sector
# ---------------------------------------------------------------------------
def download_company_info(ticker):
    """Download a company's sector and its key financial numbers."""
    info = {
        "sector": "Unknown",
        "industry": "Unknown",
        "pe": None,
        "forward_pe": None,
        "peg": None,
        "revenue_growth": None,
        "operating_margin": None,
        "net_margin": None,
    }

    # Sector and industry come from Yahoo's search results.
    try:
        quote = get_json(
            "https://query1.finance.yahoo.com/v1/finance/search"
            f"?q={ticker}&quotesCount=1&newsCount=0"
        )["quotes"][0]
        if quote.get("symbol") == ticker:
            info["sector"] = quote.get("sector") or "Unknown"
            info["industry"] = quote.get("industry") or "Unknown"
    except Exception:
        pass

    # Financial numbers come from Yahoo's fundamentals data.
    try:
        four_years_ago = int(time.time()) - 4 * 365 * 24 * 3600
        results = get_json(
            "https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/"
            f"finance/timeseries/{ticker}?type={','.join(FUNDAMENTAL_FIELDS)}"
            f"&period1={four_years_ago}&period2={int(time.time())}"
        )["timeseries"]["result"]

        # Keep the reported values for each field, oldest first.
        values = {}
        for result in results:
            field = result["meta"]["type"][0]
            values[field] = [
                entry["reportedValue"]["raw"]
                for entry in (result.get(field) or [])
                if entry
            ]

        def latest(field):
            return values[field][-1] if values.get(field) else None

        info["pe"] = latest("trailingPeRatio")
        info["forward_pe"] = latest("trailingForwardPeRatio")
        info["peg"] = latest("trailingPegRatio")

        yearly_revenue = values.get("annualTotalRevenue", [])
        if len(yearly_revenue) >= 2 and yearly_revenue[-2]:
            info["revenue_growth"] = (yearly_revenue[-1] / yearly_revenue[-2] - 1) * 100

        revenue = latest("trailingTotalRevenue")
        if revenue:
            if latest("trailingOperatingIncome") is not None:
                info["operating_margin"] = latest("trailingOperatingIncome") / revenue * 100
            if latest("trailingNetIncome") is not None:
                info["net_margin"] = latest("trailingNetIncome") / revenue * 100
    except Exception:
        pass

    return info


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_company_info(tickers):
    """Return sector and fundamentals for each ticker (cached 1 hour)."""
    return download_in_parallel(download_company_info, tickers)


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------
@st.cache_data(ttl=900, show_spinner=False)
def fetch_news(ticker):
    """Return recent headlines for one ticker (cached 15 minutes)."""
    url = (
        "https://feeds.finance.yahoo.com/rss/2.0/headline"
        f"?s={ticker}&region=US&lang=en-US"
    )
    request = urllib.request.Request(url, headers=REQUEST_HEADERS)
    with urllib.request.urlopen(request, timeout=6) as response:
        feed = ET.fromstring(response.read())

    articles = []
    for item in feed.iter("item"):
        published = item.findtext("pubDate", default="")
        try:
            published = parsedate_to_datetime(published).strftime("%b %d, %Y")
        except (TypeError, ValueError):
            pass
        articles.append(
            {
                "title": item.findtext("title", default="Untitled"),
                "link": item.findtext("link", default=""),
                "published": published,
            }
        )
    return articles
