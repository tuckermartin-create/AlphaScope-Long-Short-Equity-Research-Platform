from email.utils import parsedate_to_datetime
import urllib.request
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st


@st.cache_data(ttl=900, show_spinner=False)
def fetch_news(ticker):
    """Return recent headlines for one ticker from Yahoo Finance's news feed.

    Results are cached for 15 minutes so the feed is not downloaded again
    every time a widget changes.
    """
    url = (
        "https://feeds.finance.yahoo.com/rss/2.0/headline"
        f"?s={ticker}&region=US&lang=en-US"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
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


st.set_page_config(
    page_title="AlphaScope",
    page_icon="📊",
    layout="wide",
)

st.title("AlphaScope — Long/Short Equity Research Platform")
st.write(
    "Build a hypothetical long/short stock portfolio and see its exposure and "
    "simulated profit or loss, get suggestions for the next position, read "
    "news on your holdings, or screen a single stock against your own "
    "fair-value estimate. All prices are entered by you, so the app responds "
    "instantly."
)
st.caption(
    "AlphaScope is an educational simulator. Prices are not live market data, "
    "and its suggestions are not verified investment advice."
)

portfolio_tab, valuation_tab = st.tabs(["Portfolio builder", "Stock valuation screen"])


# ---------------------------------------------------------------------------
# Tab 1: long/short portfolio builder
# ---------------------------------------------------------------------------
with portfolio_tab:
    st.header("1. Set up the portfolio")

    capital_column, limit_column = st.columns(2)
    with capital_column:
        capital = st.number_input(
            "Portfolio capital ($)",
            min_value=1_000.0,
            value=100_000.0,
            step=1_000.0,
            format="%.2f",
            help="The total amount of money the simulated fund manages.",
        )
    with limit_column:
        gross_limit = st.slider(
            "Maximum gross exposure allowed (%)",
            min_value=50,
            max_value=300,
            value=150,
            step=10,
            help=(
                "Gross exposure is long weight plus short weight. Above 100% "
                "means the portfolio uses leverage. The app warns you if your "
                "positions go over this limit."
            ),
        )

    st.subheader("Positions")
    st.write(
        "Edit the table to change a position. Use the **+** row at the bottom "
        "to add a stock, or select a row and press Delete to remove one."
    )

    # Sample positions with placeholder prices. Replace them with your own.
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
            "Entry price ($)": [
                400.0, 200.0, 120.0, 160.0, 180.0, 210.0, 110.0, 850.0,
                250.0, 30.0, 80.0, 28.0,
            ],
            "Current price ($)": [
                420.0, 210.0, 135.0, 172.0, 174.0, 225.0, 108.0, 900.0,
                240.0, 26.0, 84.0, 27.0,
            ],
        }
    )

    positions = st.data_editor(
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
                min_value=0.0, max_value=300.0, step=1.0, required=True, default=10.0,
                help="Position size as a percentage of portfolio capital.",
            ),
            "Entry price ($)": st.column_config.NumberColumn(
                min_value=0.01, format="%.2f", required=True, default=100.0,
                help="The price at which the position was opened.",
            ),
            "Current price ($)": st.column_config.NumberColumn(
                min_value=0.01, format="%.2f", required=True, default=100.0,
                help="Today's price, entered by you.",
            ),
        },
    )

    # Ignore rows that are still being filled in.
    positions = positions.dropna().copy()
    positions["Ticker"] = positions["Ticker"].str.strip().str.upper()
    positions = positions[positions["Ticker"] != ""]

    st.header("2. Portfolio analysis")

    if positions.empty:
        st.info("Add at least one complete position above to see the analysis.")
    else:
        # A long gains when the price rises; a short gains when it falls.
        direction = positions["Side"].map({"Long": 1, "Short": -1})
        price_change = positions["Current price ($)"] / positions["Entry price ($)"] - 1

        positions["Position size ($)"] = capital * positions["Weight (%)"] / 100
        positions["Return (%)"] = direction * price_change * 100
        positions["Profit / loss ($)"] = (
            positions["Position size ($)"] * positions["Return (%)"] / 100
        )
        positions["Signed weight (%)"] = direction * positions["Weight (%)"]

        long_exposure = positions.loc[positions["Side"] == "Long", "Weight (%)"].sum()
        short_exposure = positions.loc[positions["Side"] == "Short", "Weight (%)"].sum()
        net_exposure = long_exposure - short_exposure
        gross_exposure = long_exposure + short_exposure
        total_pnl = positions["Profit / loss ($)"].sum()
        portfolio_return = total_pnl / capital * 100

        exposure_columns = st.columns(4)
        exposure_columns[0].metric("Long exposure", f"{long_exposure:.1f}%")
        exposure_columns[1].metric("Short exposure", f"{short_exposure:.1f}%")
        exposure_columns[2].metric(
            "Net exposure", f"{net_exposure:+.1f}%", help="Long minus short."
        )
        exposure_columns[3].metric(
            "Gross exposure", f"{gross_exposure:.1f}%", help="Long plus short."
        )

        value_columns = st.columns(2)
        value_columns[0].metric(
            "Simulated portfolio value",
            f"${capital + total_pnl:,.2f}",
            f"{portfolio_return:+.2f}%",
        )
        value_columns[1].metric("Simulated profit / loss", f"${total_pnl:+,.2f}")

        if gross_exposure > gross_limit:
            st.error(
                f"Gross exposure is {gross_exposure:.1f}%, above your "
                f"{gross_limit}% limit. Reduce position weights or raise the limit."
            )
        else:
            st.success(
                f"Gross exposure is {gross_exposure:.1f}%, within your "
                f"{gross_limit}% limit."
            )

        if net_exposure > 20:
            st.write(
                f"**Net long ({net_exposure:+.1f}%).** The portfolio should "
                "generally gain when the overall market rises and lose when it falls."
            )
        elif net_exposure < -20:
            st.write(
                f"**Net short ({net_exposure:+.1f}%).** The portfolio should "
                "generally gain when the overall market falls and lose when it rises."
            )
        else:
            st.write(
                f"**Close to market neutral ({net_exposure:+.1f}%).** Longs and "
                "shorts roughly offset, so results depend more on stock selection "
                "than on the direction of the overall market."
            )

        chart_column, table_column = st.columns(2)
        with chart_column:
            st.subheader("Exposure by position")
            st.caption("Bars above zero are longs; bars below zero are shorts.")
            # Tickers held more than once are combined into one bar.
            st.bar_chart(positions.groupby("Ticker")["Signed weight (%)"].sum())
        with table_column:
            st.subheader("Position results")
            st.dataframe(
                positions[
                    ["Ticker", "Side", "Position size ($)", "Return (%)", "Profit / loss ($)"]
                ],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Position size ($)": st.column_config.NumberColumn(format="$%.2f"),
                    "Return (%)": st.column_config.NumberColumn(format="%.2f%%"),
                    "Profit / loss ($)": st.column_config.NumberColumn(format="$%.2f"),
                },
            )

        # -------------------------------------------------------------------
        # Suggestions based on the current portfolio
        # -------------------------------------------------------------------
        st.header("3. Suggestions for the next position")
        st.write(
            "Choose what you want the portfolio to look like. AlphaScope compares "
            "that goal with your current positions and suggests what kind of "
            "position to add next."
        )

        goals = {
            "Market neutral (net exposure near 0%)": 0,
            "Moderately net long (net exposure near +30%)": 30,
            "Net long (net exposure near +60%)": 60,
        }
        goal = st.selectbox("Portfolio goal", list(goals.keys()), index=1)
        target_net = goals[goal]

        net_gap = target_net - net_exposure
        headroom = gross_limit - gross_exposure
        suggestions = []

        # 1. Which side to add, and how much, to reach the goal.
        if net_gap > 5:
            suggestions.append(
                f"**Add long exposure.** Net exposure is {net_exposure:+.1f}% and "
                f"your goal is {target_net:+d}%. About {net_gap:.0f}% of new long "
                "positions would close the gap."
            )
        elif net_gap < -5:
            suggestions.append(
                f"**Add short exposure.** Net exposure is {net_exposure:+.1f}% and "
                f"your goal is {target_net:+d}%. About {abs(net_gap):.0f}% of new "
                "short positions would close the gap."
            )
        else:
            suggestions.append(
                f"**Keep new positions balanced.** Net exposure of "
                f"{net_exposure:+.1f}% is already close to your {target_net:+d}% "
                "goal, so pair any new long with a short of similar size."
            )

        # 2. Whether there is room to add anything under the gross limit.
        if headroom <= 0:
            suggestions.append(
                "**Trim before adding.** The portfolio is at or above its gross "
                "exposure limit, so an existing position must shrink to make room."
            )
        elif abs(net_gap) > headroom:
            suggestions.append(
                f"**Room is limited.** Only {headroom:.0f}% of gross exposure is "
                "left under your limit, which is less than the gap to your goal. "
                "Reduce a position on the other side instead of only adding."
            )
        else:
            suggestions.append(
                f"**Room available.** You can add up to {headroom:.0f}% of new "
                "positions before reaching your gross exposure limit."
            )

        # 3. Missing hedge.
        if short_exposure == 0:
            suggestions.append(
                "**No hedge.** The portfolio has no short positions, so nothing "
                "offsets a broad market decline."
            )
        elif long_exposure == 0:
            suggestions.append(
                "**No longs.** The portfolio has only short positions, so nothing "
                "offsets a broad market rally."
            )

        # 4. Concentration in a single position.
        largest = positions.loc[positions["Weight (%)"].idxmax()]
        if gross_exposure > 0 and largest["Weight (%)"] / gross_exposure > 0.4:
            suggestions.append(
                f"**Diversify.** {largest['Ticker']} is {largest['Weight (%)']:.0f}% "
                "of capital, more than 40% of total exposure. Prefer a new ticker "
                "over adding to it."
            )

        # 5. Positions that are losing money.
        losers = positions[positions["Return (%)"] <= -10]
        if not losers.empty:
            suggestions.append(
                f"**Review losing positions.** {', '.join(losers['Ticker'])} "
                "is down 10% or more. Decide whether the original reason for the "
                "position still holds before adding new ones."
            )

        for suggestion in suggestions:
            st.markdown(f"- {suggestion}")

        # -------------------------------------------------------------------
        # Test a specific new position against the current portfolio
        # -------------------------------------------------------------------
        st.subheader("Test a new position")
        st.write(
            "Enter a stock you are thinking about adding. AlphaScope shows how it "
            "would change the portfolio and whether it fits your goal."
        )

        idea_columns = st.columns(5)
        new_ticker = idea_columns[0].text_input("New ticker", value="NVDA").strip().upper()
        new_side = idea_columns[1].radio("Side", ["Long", "Short"], horizontal=True)
        new_weight = idea_columns[2].number_input(
            "Weight (%)", min_value=1.0, max_value=100.0, value=10.0, step=1.0
        )
        new_price = idea_columns[3].number_input(
            "Current price ($)", min_value=0.01, value=100.0, step=1.0, format="%.2f",
            key="new_price",
        )
        new_fair_value = idea_columns[4].number_input(
            "Your fair value ($)", min_value=0.01, value=120.0, step=1.0, format="%.2f",
            key="new_fair_value",
            help="What you estimate one share is worth.",
        )

        new_direction = 1 if new_side == "Long" else -1
        new_net = net_exposure + new_direction * new_weight
        new_gross = gross_exposure + new_weight
        new_gap = round((new_fair_value / new_price - 1) * 100, 10)

        # Three checks: stays under the limit, moves toward the goal, and the
        # user's own valuation agrees with the chosen side.
        within_limit = new_gross <= gross_limit
        closer_to_goal = abs(target_net - new_net) < abs(target_net - net_exposure)
        valuation_agrees = new_direction * new_gap >= 10

        after_columns = st.columns(3)
        after_columns[0].metric(
            "Net exposure after", f"{new_net:+.1f}%", f"{new_direction * new_weight:+.1f}%",
            delta_color="off",
        )
        after_columns[1].metric(
            "Gross exposure after", f"{new_gross:.1f}%", f"{new_weight:+.1f}%",
            delta_color="off",
        )
        after_columns[2].metric(
            f"{new_ticker or 'Stock'} upside / (downside)", f"{new_gap:+.1f}%"
        )

        label = f"{new_side} {new_ticker or 'this stock'} at {new_weight:.0f}%"
        if not within_limit:
            st.error(
                f"**Does not fit.** {label} would raise gross exposure to "
                f"{new_gross:.1f}%, above your {gross_limit}% limit."
            )
        elif closer_to_goal and valuation_agrees:
            st.success(
                f"**Good fit.** {label} moves the portfolio closer to your goal "
                "and your fair-value estimate supports the trade."
            )
        elif closer_to_goal:
            st.warning(
                f"**Fits the portfolio, weak valuation case.** {label} moves the "
                f"portfolio closer to your goal, but your estimate shows only "
                f"{new_gap:+.1f}% for a {new_side.lower()} position (10% or more "
                "in your favor is needed)."
            )
        elif valuation_agrees:
            st.warning(
                f"**Good idea, wrong side for this portfolio.** Your fair-value "
                f"estimate supports {label}, but it moves net exposure further "
                "from your goal. Consider a smaller size or an offsetting position."
            )
        else:
            st.error(
                f"**Poor fit.** {label} moves the portfolio away from your goal "
                "and your fair-value estimate does not support the trade."
            )

        if new_ticker in set(positions["Ticker"]):
            st.info(
                f"{new_ticker} is already in the portfolio, so this would change "
                "the size of an existing position rather than add diversification."
            )

        st.caption(
            "These suggestions come from simple rules applied to the numbers you "
            "entered. They are for learning, not verified investment advice."
        )

        # -------------------------------------------------------------------
        # News for the stocks in the portfolio
        # -------------------------------------------------------------------
        st.header("4. Portfolio news")
        st.write(
            "See recent headlines for the stocks you hold. News is the only part "
            "of AlphaScope that uses the internet, so it loads only when you turn "
            "it on."
        )

        show_news = st.toggle("Show news for my portfolio")
        if show_news:
            portfolio_tickers = list(dict.fromkeys(positions["Ticker"]))
            filter_column, count_column = st.columns(2)
            with filter_column:
                news_tickers = st.multiselect(
                    "Stocks to show news for",
                    portfolio_tickers,
                    default=portfolio_tickers,
                )
            with count_column:
                headlines_per_stock = st.slider(
                    "Headlines per stock", min_value=1, max_value=5, value=3
                )

            side_by_ticker = dict(zip(positions["Ticker"], positions["Side"]))
            with st.spinner("Loading headlines..."):
                for news_ticker in news_tickers:
                    st.subheader(f"{news_ticker} ({side_by_ticker[news_ticker]})")
                    try:
                        articles = fetch_news(news_ticker)
                    except Exception:
                        # A slow or unavailable feed should not break the app.
                        st.warning(f"News for {news_ticker} could not be loaded right now.")
                        continue
                    if not articles:
                        st.write("No recent headlines found.")
                    for article in articles[:headlines_per_stock]:
                        st.markdown(
                            f"- [{article['title']}]({article['link']}) "
                            f"· {article['published']}"
                        )
            st.caption("Headlines come from Yahoo Finance and refresh every 15 minutes.")


# ---------------------------------------------------------------------------
# Tab 2: single-stock valuation screen
# ---------------------------------------------------------------------------
with valuation_tab:
    st.header("Stock information")
    st.write(
        "Enter a stock's current price and your estimate of its fair value to "
        "see whether the difference may be worth researching."
    )

    ticker = st.text_input(
        "Stock ticker",
        value="AAPL",
        help="For example: AAPL, MSFT, or NVDA.",
    ).strip().upper()

    price_column, value_column = st.columns(2)
    with price_column:
        current_price = st.number_input(
            "Current stock price ($)",
            min_value=0.01,
            value=100.00,
            step=1.00,
            format="%.2f",
            help="Enter the stock's current price.",
        )
    with value_column:
        fair_value = st.number_input(
            "Estimated fair value ($)",
            min_value=0.01,
            value=115.00,
            step=1.00,
            format="%.2f",
            help="Enter what you estimate one share may be worth.",
        )

    threshold = st.slider(
        "Value gap needed to flag a stock for more research (%)",
        min_value=5,
        max_value=30,
        value=15,
        help=(
            "For example, 15% means your fair-value estimate must be at least 15% "
            "above or below the current price before the app shows a research flag. "
            "It is not a buy or sell instruction."
        ),
    )

    # Rounding avoids a floating-point error when the value gap exactly meets the cutoff.
    valuation_gap = round(((fair_value / current_price) - 1) * 100, 10)

    st.header("Research screen")
    st.metric(
        f"{ticker or 'Stock'} estimated upside / (downside)",
        f"{valuation_gap:+.2f}%",
    )

    if valuation_gap >= threshold:
        st.success("Potential Long Research Candidate.")
        explanation = (
            f"Your fair-value estimate is {valuation_gap:.2f}% above the current price, "
            f"reaching the {threshold}% cutoff for a long research flag."
        )
    elif valuation_gap <= -threshold:
        st.warning("Potential Short Research Candidate.")
        explanation = (
            f"Your fair-value estimate is {abs(valuation_gap):.2f}% below the current "
            f"price, reaching the {threshold}% cutoff for a short research flag."
        )
    else:
        st.info("Neutral — Further Research Needed.")
        explanation = (
            f"The estimated value gap is {abs(valuation_gap):.2f}%, below the "
            f"{threshold}% cutoff needed for a research flag in either direction."
        )

    st.write(explanation)
    st.caption(
        "This is a simplified valuation screen, not a verified investment recommendation. "
        "A valuation gap alone is not enough to justify a trade."
    )
