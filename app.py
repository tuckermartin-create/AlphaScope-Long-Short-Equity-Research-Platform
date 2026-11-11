from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from email.utils import parsedate_to_datetime
import json
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import streamlit as st


REFRESH_SECONDS = 60
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0"}

# How far back to measure performance, in trading days.
PERIODS = {"1 month": 21, "3 months": 63, "6 months": 126, "1 year": 250}

GOALS = {
    "Market neutral (net near 0%)": 0,
    "Moderately net long (net near +30%)": 30,
    "Net long (net near +60%)": 60,
}

LONG_COLOR = "#2a9d8f"
SHORT_COLOR = "#e76f51"
CHART_HEIGHT = 280


# ---------------------------------------------------------------------------
# Market data
# ---------------------------------------------------------------------------
def download_stock(ticker):
    """Download the latest price and two years of daily closes for one ticker."""
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        "?range=2y&interval=1d"
    )
    request = urllib.request.Request(url, headers=REQUEST_HEADERS)
    with urllib.request.urlopen(request, timeout=5) as response:
        result = json.load(response)["chart"]["result"][0]

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


@st.cache_data(ttl=REFRESH_SECONDS, show_spinner=False)
def fetch_market_data(tickers):
    """Return market data for each ticker that could be loaded.

    Tickers are downloaded at the same time and the result is cached for one
    minute, so the app stays fast while prices keep updating.
    """

    def safe_download(ticker):
        try:
            return ticker, download_stock(ticker)
        except Exception:
            # An unknown ticker or a slow connection should not break the app.
            return ticker, None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = pool.map(safe_download, tickers)
    return {ticker: data for ticker, data in results if data is not None}


@st.cache_data(ttl=900, show_spinner=False)
def fetch_news(ticker):
    """Return recent headlines for one ticker from Yahoo Finance's news feed."""
    url = (
        "https://feeds.finance.yahoo.com/rss/2.0/headline"
        f"?s={ticker}&region=US&lang=en-US"
    )
    request = urllib.request.Request(url, headers=REQUEST_HEADERS)
    with urllib.request.urlopen(request, timeout=5) as response:
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


def trend_signal(closes):
    """Classify a stock's price trend as Long, Short, or Neutral, with reasons.

    Three checks are used. All three must agree for a Long or Short signal:
    1. Is the price above its 200-day average?
    2. Is the 50-day average above the 200-day average?
    3. Is the price higher than it was six months ago?
    """
    if len(closes) < 200:
        return "Neutral", "Not enough price history to judge the trend."

    price = closes.iloc[-1]
    average_50 = closes.iloc[-50:].mean()
    average_200 = closes.iloc[-200:].mean()
    gap_to_200 = (price / average_200 - 1) * 100
    six_month_change = (price / closes.iloc[-127] - 1) * 100

    checks = [price > average_200, average_50 > average_200, six_month_change > 0]
    reasoning = (
        f"Price is {abs(gap_to_200):.0f}% "
        f"{'above' if checks[0] else 'below'} its 200-day average; the 50-day "
        f"average is {'above' if checks[1] else 'below'} the 200-day average; "
        f"the stock is {'up' if checks[2] else 'down'} "
        f"{abs(six_month_change):.0f}% over six months."
    )

    if all(checks):
        return "Long", reasoning
    if not any(checks):
        return "Short", reasoning
    return "Neutral", reasoning


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def value_chart(history):
    """Line chart of portfolio value over time."""
    data = history.rename("Value").rename_axis("Date").reset_index()
    return (
        alt.Chart(data)
        .mark_line(color=LONG_COLOR, strokeWidth=2.5)
        .encode(
            x=alt.X("Date:T", title=None),
            y=alt.Y("Value:Q", title="Portfolio value ($)", scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("Date:T"), alt.Tooltip("Value:Q", format="$,.0f")],
        )
        .properties(height=CHART_HEIGHT)
    )


def profit_chart(positions):
    """Bar chart of profit or loss for each position."""
    return (
        alt.Chart(positions)
        .mark_bar()
        .encode(
            x=alt.X("Profit / loss ($):Q", title="Profit / loss ($)"),
            y=alt.Y("Ticker:N", sort="-x", title=None, axis=alt.Axis(labelOverlap=False)),
            color=alt.condition(
                alt.datum["Profit / loss ($)"] >= 0,
                alt.value(LONG_COLOR),
                alt.value(SHORT_COLOR),
            ),
            tooltip=[
                "Ticker", "Side",
                alt.Tooltip("Return (%):Q", format="+.1f"),
                alt.Tooltip("Profit / loss ($):Q", format="$,.0f"),
            ],
        )
        .properties(height=CHART_HEIGHT)
    )


def exposure_chart(positions):
    """Bar chart of position weights: longs above zero, shorts below."""
    return (
        alt.Chart(positions)
        .mark_bar()
        .encode(
            x=alt.X("Ticker:N", sort="-y", title=None),
            y=alt.Y("Signed weight (%):Q", title="Weight (% of capital)"),
            color=alt.Color(
                "Side:N",
                scale=alt.Scale(domain=["Long", "Short"], range=[LONG_COLOR, SHORT_COLOR]),
                legend=alt.Legend(orient="top", title=None),
            ),
            tooltip=["Ticker", "Side", alt.Tooltip("Weight (%):Q", format=".1f")],
        )
        .properties(height=CHART_HEIGHT)
    )


def trend_chart(closes):
    """Line chart of the past year's price with 50-day and 200-day averages."""
    data = pd.DataFrame(
        {
            "Price": closes,
            "50-day average": closes.rolling(50).mean(),
            "200-day average": closes.rolling(200).mean(),
        }
    ).iloc[-250:].rename_axis("Date").reset_index()
    data = data.melt("Date", var_name="Line", value_name="Value").dropna()
    return (
        alt.Chart(data)
        .mark_line()
        .encode(
            x=alt.X("Date:T", title=None),
            y=alt.Y("Value:Q", title="Price ($)", scale=alt.Scale(zero=False)),
            color=alt.Color(
                "Line:N",
                scale=alt.Scale(
                    domain=["Price", "50-day average", "200-day average"],
                    range=["#264653", LONG_COLOR, SHORT_COLOR],
                ),
                legend=alt.Legend(orient="top", title=None),
            ),
            strokeDash=alt.condition(
                alt.datum.Line == "Price", alt.value([1, 0]), alt.value([5, 3])
            ),
            tooltip=["Line", alt.Tooltip("Date:T"), alt.Tooltip("Value:Q", format="$,.2f")],
        )
        .properties(height=CHART_HEIGHT)
    )


# ---------------------------------------------------------------------------
# Page setup and sidebar
# ---------------------------------------------------------------------------
st.set_page_config(page_title="AlphaScope", page_icon="📊", layout="wide")

st.title("AlphaScope — Long/Short Equity Research Platform")
st.caption(
    "Track a long/short stock portfolio with market prices that update "
    "automatically. An educational simulator: its signals and suggestions come "
    "from simple rules and are not verified investment advice."
)

with st.sidebar:
    st.header("Portfolio settings")
    capital = st.number_input(
        "Portfolio capital ($)",
        min_value=1_000.0,
        value=100_000.0,
        step=1_000.0,
        format="%.2f",
        help="The total amount of money the simulated fund manages.",
    )
    period = st.selectbox(
        "Positions were opened",
        list(PERIODS.keys()),
        index=1,
        format_func=lambda label: f"{label} ago",
        help=(
            "AlphaScope looks up each stock's price from this long ago and uses "
            "it as the entry price, so you do not need to type prices."
        ),
    )
    gross_limit = st.slider(
        "Maximum gross exposure (%)",
        min_value=50,
        max_value=300,
        value=150,
        step=10,
        help=(
            "Gross exposure is long weight plus short weight. Above 100% means "
            "the portfolio uses leverage."
        ),
    )
    goal = st.selectbox(
        "Portfolio goal",
        list(GOALS.keys()),
        index=1,
        help="Used on the Ideas tab to suggest what kind of position to add next.",
    )
    st.caption(f"Prices refresh automatically every {REFRESH_SECONDS} seconds.")

# A sample portfolio to start from. Replace it with your own ideas.
starting_positions = pd.DataFrame(
    {
        "Ticker": [
            "MSFT", "AAPL", "NVDA", "GOOGL", "AMZN", "JPM", "XOM", "COST",
            "TSLA", "INTC", "NKE", "PFE",
        ],
        "Side": [
            "Long", "Long", "Long", "Long", "Long", "Long", "Long", "Long",
            "Short", "Short", "Short", "Short",
        ],
        "Weight (%)": [12.0, 10.0, 10.0, 8.0, 8.0, 7.0, 5.0, 5.0, 10.0, 7.0, 7.0, 6.0],
    }
)

with st.expander("✏️ Edit positions (add, remove, or resize stocks)"):
    st.write(
        "Choose the stocks, the side, and the size. Prices are looked up "
        "automatically. Use the **+** row at the bottom to add a stock, or "
        "select a row and press Delete to remove one."
    )
    edited_positions = st.data_editor(
        starting_positions,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "Ticker": st.column_config.TextColumn(required=True),
            "Side": st.column_config.SelectboxColumn(
                options=["Long", "Short"], required=True, default="Long"
            ),
            "Weight (%)": st.column_config.NumberColumn(
                min_value=0.0, max_value=300.0, step=1.0, required=True, default=5.0,
                help="Position size as a percentage of portfolio capital.",
            ),
        },
    )

# Ignore rows that are still being filled in.
edited_positions = edited_positions.dropna().copy()
edited_positions["Ticker"] = edited_positions["Ticker"].str.strip().str.upper()
edited_positions = edited_positions[edited_positions["Ticker"] != ""]


# ---------------------------------------------------------------------------
# Main dashboard. It reruns itself every minute to pick up new prices.
# ---------------------------------------------------------------------------
@st.fragment(run_every=REFRESH_SECONDS)
def dashboard(positions, capital, gross_limit, period, target_net):
    market = fetch_market_data(tuple(sorted(set(positions["Ticker"]))))

    missing = sorted(set(positions["Ticker"]) - set(market))
    if missing:
        st.warning(
            f"No market data found for {', '.join(missing)}. Check the ticker "
            "symbols or your internet connection. They are left out below."
        )
    positions = positions[positions["Ticker"].isin(market)].copy()
    if positions.empty:
        st.info("Add at least one valid position to see the dashboard.")
        return

    days = PERIODS[period]

    # The entry price is the closing price at the start of the chosen period.
    def entry_price(ticker):
        closes = market[ticker]["closes"]
        return closes.iloc[max(len(closes) - 1 - days, 0)]

    # A long gains when the price rises; a short gains when it falls.
    direction = positions["Side"].map({"Long": 1, "Short": -1})
    positions["Company"] = positions["Ticker"].map(lambda t: market[t]["name"])
    positions["Live price ($)"] = positions["Ticker"].map(lambda t: market[t]["price"])
    positions["Entry price ($)"] = positions["Ticker"].map(entry_price)
    positions["Today (%)"] = positions["Ticker"].map(
        lambda t: (market[t]["price"] / market[t]["closes"].iloc[-2] - 1) * 100
    )
    positions["Position size ($)"] = capital * positions["Weight (%)"] / 100
    positions["Return (%)"] = (
        direction * (positions["Live price ($)"] / positions["Entry price ($)"] - 1) * 100
    )
    positions["Profit / loss ($)"] = (
        positions["Position size ($)"] * positions["Return (%)"] / 100
    )
    positions["Signed weight (%)"] = direction * positions["Weight (%)"]

    signals = positions["Ticker"].map(lambda t: trend_signal(market[t]["closes"]))
    positions["Trend signal"] = signals.str[0]
    positions["Reasoning"] = signals.str[1]

    def verdict(row):
        if row["Trend signal"] == "Neutral":
            return "🟡 Mixed evidence"
        if row["Trend signal"] == row["Side"]:
            return "🟢 Supports your side"
        return "🔴 Conflicts with your side"

    positions["Verdict"] = positions.apply(verdict, axis=1)
    conflicts = positions[positions["Verdict"].str.startswith("🔴")]

    long_exposure = positions.loc[positions["Side"] == "Long", "Weight (%)"].sum()
    short_exposure = positions.loc[positions["Side"] == "Short", "Weight (%)"].sum()
    net_exposure = long_exposure - short_exposure
    gross_exposure = long_exposure + short_exposure
    total_pnl = positions["Profit / loss ($)"].sum()
    portfolio_return = total_pnl / capital * 100

    # Headline numbers stay visible above every tab.
    headline = st.columns(5)
    headline[0].metric(
        "Portfolio value", f"${capital + total_pnl:,.0f}", f"{portfolio_return:+.2f}%"
    )
    headline[1].metric(f"Profit / loss ({period})", f"${total_pnl:+,.0f}")
    headline[2].metric(
        "Net exposure", f"{net_exposure:+.0f}%", help="Long weight minus short weight."
    )
    headline[3].metric(
        f"Gross exposure (limit {gross_limit}%)",
        f"{gross_exposure:.0f}%",
        help="Long weight plus short weight.",
    )
    headline[4].metric(
        "Against the trend",
        f"{len(conflicts)} of {len(positions)}",
        help="Positions whose side conflicts with the stock's price trend.",
    )

    latest_trade = max(data["time"] or 0 for data in market.values())
    latest_trade = datetime.fromtimestamp(latest_trade, ZoneInfo("America/New_York"))
    st.caption(
        f"Latest market price: {latest_trade:%b %d, %I:%M %p} New York time. "
        "When the market is closed, the closing price is shown."
    )

    overview, holdings, reasoning, ideas, news, screen = st.tabs(
        [
            "📈 Overview", "📋 Holdings", "🧠 Long/short reasoning",
            "💡 Ideas", "📰 News", "🔎 Valuation screen",
        ]
    )

    # -----------------------------------------------------------------------
    with overview:
        if gross_exposure > gross_limit:
            st.error(
                f"Gross exposure is {gross_exposure:.0f}%, above your "
                f"{gross_limit}% limit. Reduce position weights or raise the limit."
            )

        left, middle, right = st.columns(3)
        with left:
            st.subheader(f"Value over {period}")
            # Add up each position's gain or loss on every day of the period.
            gains = []
            for ticker, side, weight in zip(
                positions["Ticker"], positions["Side"], positions["Weight (%)"]
            ):
                closes = market[ticker]["closes"].iloc[-(days + 1):]
                sign = 1 if side == "Long" else -1
                gains.append(sign * (closes / closes.iloc[0] - 1) * weight / 100)
            history = capital * (1 + pd.concat(gains, axis=1).ffill().fillna(0).sum(axis=1))
            st.altair_chart(value_chart(history), use_container_width=True)
        with middle:
            st.subheader("Profit / loss by position")
            st.altair_chart(profit_chart(positions), use_container_width=True)
        with right:
            st.subheader("Exposure by position")
            st.altair_chart(exposure_chart(positions), use_container_width=True)

        st.progress(
            min(gross_exposure / gross_limit, 1.0),
            text=(
                f"Using {gross_exposure:.0f}% of your {gross_limit}% gross exposure "
                f"limit — {long_exposure:.0f}% long, {short_exposure:.0f}% short."
            ),
        )

    # -----------------------------------------------------------------------
    with holdings:
        st.dataframe(
            positions[
                [
                    "Ticker", "Company", "Side", "Weight (%)", "Entry price ($)",
                    "Live price ($)", "Today (%)", "Return (%)", "Profit / loss ($)",
                ]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Weight (%)": st.column_config.ProgressColumn(
                    format="%.0f%%", min_value=0, max_value=float(positions["Weight (%)"].max())
                ),
                "Entry price ($)": st.column_config.NumberColumn(
                    format="$%.2f", help=f"Closing price {period} ago."
                ),
                "Live price ($)": st.column_config.NumberColumn(format="$%.2f"),
                "Today (%)": st.column_config.NumberColumn(
                    format="%+.2f%%", help="The stock's price change since the previous close."
                ),
                "Return (%)": st.column_config.NumberColumn(
                    format="%+.2f%%",
                    help="Your return on the position. Shorts gain when the price falls.",
                ),
                "Profit / loss ($)": st.column_config.NumberColumn(format="$%.2f"),
            },
        )

    # -----------------------------------------------------------------------
    with reasoning:
        st.write(
            "AlphaScope checks each stock's price trend with three rules: is the "
            "price above its 200-day average, is the 50-day average above the "
            "200-day average, and is the stock up over six months. All three "
            "positive gives a **Long** signal, all three negative gives "
            "**Short**, and anything else is **Neutral**."
        )

        table_column, chart_column = st.columns([3, 2])
        with table_column:
            st.dataframe(
                positions[["Ticker", "Side", "Trend signal", "Verdict", "Reasoning"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Side": st.column_config.TextColumn("Your side"),
                    "Reasoning": st.column_config.TextColumn(width="large"),
                },
            )
        with chart_column:
            chart_ticker = st.selectbox(
                "Show the trend for", list(dict.fromkeys(positions["Ticker"]))
            )
            st.altair_chart(
                trend_chart(market[chart_ticker]["closes"]), use_container_width=True
            )

        if conflicts.empty:
            st.success("No position goes against its price trend.")
        else:
            st.warning(
                f"{', '.join(conflicts['Ticker'])} "
                f"{'goes' if len(conflicts) == 1 else 'go'} against the price "
                "trend. That can be a deliberate bet on a reversal, but it needs "
                "a reason beyond the trend, such as valuation or company news."
            )
        st.caption(
            "The trend signal looks only at past prices. It does not consider "
            "earnings, valuation, or news, and past trends do not guarantee "
            "future results."
        )

    # -----------------------------------------------------------------------
    with ideas:
        suggestion_column, test_column = st.columns(2)

        with suggestion_column:
            st.subheader("What to add next")
            net_gap = target_net - net_exposure
            headroom = gross_limit - gross_exposure
            suggestions = []

            # 1. Which side to add, and how much, to reach the goal.
            if net_gap > 5:
                suggestions.append(
                    f"**Add long exposure.** Net exposure is {net_exposure:+.0f}% "
                    f"and your goal is {target_net:+d}%. About {net_gap:.0f}% of "
                    "new long positions would close the gap."
                )
            elif net_gap < -5:
                suggestions.append(
                    f"**Add short exposure.** Net exposure is {net_exposure:+.0f}% "
                    f"and your goal is {target_net:+d}%. About {abs(net_gap):.0f}% "
                    "of new short positions would close the gap."
                )
            else:
                suggestions.append(
                    f"**Keep new positions balanced.** Net exposure of "
                    f"{net_exposure:+.0f}% is already close to your {target_net:+d}% "
                    "goal, so pair any new long with a short of similar size."
                )

            # 2. Whether there is room to add anything under the gross limit.
            if headroom <= 0:
                suggestions.append(
                    "**Trim before adding.** The portfolio is at or above its "
                    "gross exposure limit, so an existing position must shrink."
                )
            elif abs(net_gap) > headroom:
                suggestions.append(
                    f"**Room is limited.** Only {headroom:.0f}% of gross exposure "
                    "is left under your limit, less than the gap to your goal. "
                    "Reduce a position on the other side instead of only adding."
                )
            else:
                suggestions.append(
                    f"**Room available.** You can add up to {headroom:.0f}% of "
                    "new positions before reaching your gross exposure limit."
                )

            # 3. Missing hedge.
            if short_exposure == 0:
                suggestions.append(
                    "**No hedge.** The portfolio has no short positions, so "
                    "nothing offsets a broad market decline."
                )
            elif long_exposure == 0:
                suggestions.append(
                    "**No longs.** The portfolio has only short positions, so "
                    "nothing offsets a broad market rally."
                )

            # 4. Concentration in a single position.
            largest = positions.loc[positions["Weight (%)"].idxmax()]
            if gross_exposure > 0 and largest["Weight (%)"] / gross_exposure > 0.4:
                suggestions.append(
                    f"**Diversify.** {largest['Ticker']} is "
                    f"{largest['Weight (%)']:.0f}% of capital, more than 40% of "
                    "total exposure. Prefer a new ticker over adding to it."
                )

            # 5. Positions that are losing money or fighting the trend.
            losers = positions[positions["Return (%)"] <= -10]
            if not losers.empty:
                suggestions.append(
                    f"**Review losing positions.** {', '.join(losers['Ticker'])} "
                    f"lost 10% or more over {period}. Check whether the original "
                    "reason for the position still holds."
                )
            if not conflicts.empty:
                suggestions.append(
                    f"**Review positions against the trend.** "
                    f"{', '.join(conflicts['Ticker'])} conflict with their trend "
                    "signal (see the Long/short reasoning tab)."
                )

            for suggestion in suggestions:
                st.markdown(f"- {suggestion}")
            st.caption("Change the portfolio goal in the sidebar.")

        with test_column:
            st.subheader("Test a new position")
            idea_columns = st.columns(3)
            new_ticker = idea_columns[0].text_input("New ticker", value="META").strip().upper()
            new_side = idea_columns[1].radio("Side", ["Long", "Short"], horizontal=True)
            new_weight = idea_columns[2].number_input(
                "Weight (%)", min_value=1.0, max_value=100.0, value=10.0, step=1.0
            )

            new_stock = fetch_market_data((new_ticker,)).get(new_ticker) if new_ticker else None
            if new_stock is None:
                st.warning("Enter a valid ticker symbol to test a new position.")
            else:
                new_price = new_stock["price"]
                new_fair_value = st.number_input(
                    f"Your fair value for {new_ticker} ($) — optional",
                    min_value=0.01,
                    value=float(round(new_price)),
                    step=1.0,
                    format="%.2f",
                    key=f"fair_value_{new_ticker}",
                    help="What you estimate one share is worth. Starts at the live price.",
                )

                new_direction = 1 if new_side == "Long" else -1
                new_net = net_exposure + new_direction * new_weight
                new_gross = gross_exposure + new_weight
                new_gap = round((new_fair_value / new_price - 1) * 100, 10)
                new_trend, new_reasoning = trend_signal(new_stock["closes"])

                # Checks: stays under the limit, moves toward the goal, and has
                # a reason behind the side (price trend or your own valuation).
                within_limit = new_gross <= gross_limit
                closer_to_goal = abs(target_net - new_net) < abs(target_net - net_exposure)
                valuation_agrees = new_direction * new_gap >= 10
                trend_agrees = new_trend == new_side
                has_reason = valuation_agrees or trend_agrees

                after = st.columns(4)
                after[0].metric("Live price", f"${new_price:,.2f}")
                after[1].metric("Trend signal", new_trend)
                after[2].metric(
                    "Net after", f"{new_net:+.0f}%",
                    f"{new_direction * new_weight:+.0f}%", delta_color="off",
                )
                after[3].metric(
                    "Gross after", f"{new_gross:.0f}%", f"{new_weight:+.0f}%",
                    delta_color="off",
                )

                reasons = []
                if trend_agrees:
                    reasons.append("the price trend supports it")
                if valuation_agrees:
                    reasons.append(f"your fair value implies {new_gap:+.0f}%")
                reason_text = " and ".join(reasons)

                label = f"{new_side} {new_ticker} at {new_weight:.0f}%"
                if not within_limit:
                    st.error(
                        f"**Does not fit.** {label} would raise gross exposure "
                        f"to {new_gross:.0f}%, above your {gross_limit}% limit."
                    )
                elif closer_to_goal and has_reason:
                    st.success(
                        f"**Good fit.** {label} moves the portfolio closer to "
                        f"your goal, and {reason_text}."
                    )
                elif closer_to_goal:
                    st.warning(
                        f"**Fits the portfolio, but no clear reason for the "
                        f"trade.** {label} moves the portfolio closer to your "
                        f"goal, but the trend signal is {new_trend} and your fair "
                        "value is not at least 10% in your favor."
                    )
                elif has_reason:
                    st.warning(
                        f"**Good idea, wrong side for this portfolio.** For "
                        f"{label}, {reason_text}, but it moves net exposure "
                        "further from your goal. Consider a smaller size or an "
                        "offsetting position."
                    )
                else:
                    st.error(
                        f"**Poor fit.** {label} moves the portfolio away from "
                        f"your goal, the trend signal is {new_trend}, and your "
                        "fair value does not support the trade."
                    )

                st.caption(f"{new_ticker} trend: {new_reasoning}")
                if new_ticker in set(positions["Ticker"]):
                    st.info(
                        f"{new_ticker} is already in the portfolio, so this would "
                        "resize an existing position rather than add diversification."
                    )

    # -----------------------------------------------------------------------
    with news:
        portfolio_tickers = list(dict.fromkeys(positions["Ticker"]))
        largest_holdings = list(
            dict.fromkeys(positions.sort_values("Weight (%)", ascending=False)["Ticker"])
        )[:4]

        filter_column, count_column = st.columns([3, 1])
        news_tickers = filter_column.multiselect(
            "Stocks to show news for",
            portfolio_tickers,
            default=largest_holdings,
            help="Starts with your four largest positions.",
        )
        headlines_per_stock = count_column.slider(
            "Headlines per stock", min_value=1, max_value=5, value=3
        )

        side_by_ticker = dict(zip(positions["Ticker"], positions["Side"]))
        news_columns = st.columns(2)
        for index, news_ticker in enumerate(news_tickers):
            with news_columns[index % 2].container(border=True):
                st.markdown(f"**{news_ticker}** · {side_by_ticker[news_ticker]}")
                try:
                    articles = fetch_news(news_ticker)
                except Exception:
                    # A slow or unavailable feed should not break the app.
                    st.warning("News could not be loaded right now.")
                    continue
                if not articles:
                    st.write("No recent headlines found.")
                for article in articles[:headlines_per_stock]:
                    st.markdown(
                        f"- [{article['title']}]({article['link']}) "
                        f"· {article['published']}"
                    )
        st.caption("Headlines come from Yahoo Finance and refresh every 15 minutes.")

    # -----------------------------------------------------------------------
    with screen:
        st.write(
            "Enter any ticker and your estimate of its fair value. AlphaScope "
            "looks up the live price and shows whether the gap may be worth "
            "researching."
        )

        input_column, result_column = st.columns(2)
        with input_column:
            ticker = st.text_input(
                "Stock ticker", value="AAPL", help="For example: AAPL, MSFT, or NVDA."
            ).strip().upper()
            stock = fetch_market_data((ticker,)).get(ticker) if ticker else None

            if stock is None:
                st.warning("Enter a valid ticker symbol to run the valuation screen.")
            else:
                current_price = stock["price"]
                fair_value = st.number_input(
                    "Estimated fair value ($)",
                    min_value=0.01,
                    value=float(round(current_price * 1.15)),
                    step=1.00,
                    format="%.2f",
                    key=f"screen_fair_value_{ticker}",
                    help="Enter what you estimate one share may be worth.",
                )
                threshold = st.slider(
                    "Value gap needed to flag a stock (%)",
                    min_value=5,
                    max_value=30,
                    value=15,
                    help=(
                        "For example, 15% means your fair-value estimate must be "
                        "at least 15% above or below the live price before the "
                        "app shows a research flag. It is not a buy or sell "
                        "instruction."
                    ),
                )

        if stock is not None:
            with result_column:
                # Rounding avoids a floating-point error at the exact cutoff.
                valuation_gap = round(((fair_value / current_price) - 1) * 100, 10)

                result_metrics = st.columns(2)
                result_metrics[0].metric(
                    f"{stock['name']} live price", f"${current_price:,.2f}"
                )
                result_metrics[1].metric(
                    "Estimated upside / (downside)", f"{valuation_gap:+.2f}%"
                )

                if valuation_gap >= threshold:
                    st.success(
                        f"**Potential Long Research Candidate.** Your fair-value "
                        f"estimate is {valuation_gap:.1f}% above the live price, "
                        f"reaching the {threshold}% cutoff."
                    )
                elif valuation_gap <= -threshold:
                    st.warning(
                        f"**Potential Short Research Candidate.** Your fair-value "
                        f"estimate is {abs(valuation_gap):.1f}% below the live "
                        f"price, reaching the {threshold}% cutoff."
                    )
                else:
                    st.info(
                        f"**Neutral — Further Research Needed.** The value gap of "
                        f"{abs(valuation_gap):.1f}% is below the {threshold}% cutoff."
                    )

                trend, trend_reasoning = trend_signal(stock["closes"])
                st.write(f"**Price trend signal: {trend}.** {trend_reasoning}")

        st.caption(
            "This is a simplified valuation screen, not a verified investment "
            "recommendation. A valuation gap alone is not enough to justify a trade."
        )


if edited_positions.empty:
    st.info("Open **Edit positions** above and add at least one stock.")
else:
    dashboard(edited_positions, capital, gross_limit, period, GOALS[goal])
