from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import analysis
import charts
import step_tracker
from market_data import (
    BENCHMARK,
    PRICE_REFRESH_SECONDS,
    fetch_company_info,
    fetch_market_data,
    fetch_news,
)


SAVE_FILE = Path(__file__).with_name("my_portfolio.csv")
STEPS_FILE = Path(__file__).with_name("my_steps.csv")
POSITION_COLUMNS = ["Ticker", "Side", "Shares", "Entry date"]

GOALS = {
    "Market neutral (net near 0%)": 0,
    "Moderately net long (net near +30%)": 30,
    "Net long (net near +60%)": 60,
}

# A sample portfolio to start from. Replace it with your own ideas.
SAMPLE_POSITIONS = pd.DataFrame(
    [
        ["MSFT", "Long", 23, date(2026, 2, 2)],
        ["AAPL", "Long", 28, date(2026, 2, 2)],
        ["NVDA", "Long", 58, date(2026, 3, 2)],
        ["GOOGL", "Long", 27, date(2026, 3, 2)],
        ["AMZN", "Long", 30, date(2026, 4, 1)],
        ["JPM", "Long", 20, date(2026, 4, 1)],
        ["XOM", "Long", 30, date(2026, 5, 1)],
        ["COST", "Long", 5, date(2026, 5, 1)],
        ["TSLA", "Short", 26, date(2026, 3, 2)],
        ["INTC", "Short", 112, date(2026, 4, 1)],
        ["NKE", "Short", 183, date(2026, 5, 1)],
        ["PFE", "Short", 204, date(2026, 6, 1)],
    ],
    columns=POSITION_COLUMNS,
)


def read_positions(source):
    """Load positions from a CSV file saved by AlphaScope."""
    positions = pd.read_csv(source)
    positions = positions[POSITION_COLUMNS].copy()
    positions["Entry date"] = pd.to_datetime(positions["Entry date"]).dt.date
    positions["Shares"] = positions["Shares"].astype(float)
    return positions


def load_positions(positions):
    """Show a new set of positions in the editor, clearing earlier edits."""
    st.session_state.base_positions = positions
    st.session_state.editor_version = st.session_state.get("editor_version", 0) + 1


def set_steps(steps):
    """Use a new set of daily step counts and keep them for next time."""
    st.session_state.steps = steps
    if steps is None:
        STEPS_FILE.unlink(missing_ok=True)
    else:
        steps.rename("Steps").rename_axis("Date").to_csv(STEPS_FILE)


def show(value, pattern):
    """Format a number, or show 'n/a' when the data is missing."""
    return "n/a" if value is None or pd.isna(value) else pattern.format(value)


# ---------------------------------------------------------------------------
# Page setup, settings, and positions
# ---------------------------------------------------------------------------
st.set_page_config(page_title="AlphaScope", page_icon="📊", layout="wide")

st.title("AlphaScope — Long/Short Equity Research Platform")
st.caption(
    "Track a long/short stock portfolio with market prices that update "
    "automatically. An educational simulator: its signals and suggestions come "
    "from simple rules and are not verified investment advice."
)

# On first load, use the saved portfolio if there is one, otherwise the sample.
if "base_positions" not in st.session_state:
    try:
        load_positions(read_positions(SAVE_FILE))
    except Exception:
        load_positions(SAMPLE_POSITIONS)

# Step counts from an earlier upload are kept on this computer.
if "steps" not in st.session_state:
    try:
        st.session_state.steps = pd.read_csv(
            STEPS_FILE, index_col="Date", parse_dates=True
        )["Steps"]
    except Exception:
        st.session_state.steps = None

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

with st.expander("✏️ Edit positions (add, remove, or resize stocks)"):
    st.write(
        "Enter each stock, the side, the number of shares, and the date you "
        "opened the position. Prices are looked up automatically. Use the "
        "**+** row at the bottom to add a stock, or select a row and press "
        "Delete to remove one."
    )
    edited_positions = st.data_editor(
        st.session_state.base_positions,
        key=f"positions_editor_{st.session_state.editor_version}",
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "Ticker": st.column_config.TextColumn(required=True),
            "Side": st.column_config.SelectboxColumn(
                options=["Long", "Short"], required=True, default="Long"
            ),
            "Shares": st.column_config.NumberColumn(
                min_value=0.0, step=1.0, required=True, default=10.0
            ),
            "Entry date": st.column_config.DateColumn(
                min_value=date.today() - timedelta(days=5 * 365),
                max_value=date.today(),
                required=True,
                default=date.today(),
                help="The entry price is the closing price on this date.",
            ),
        },
    )

# Ignore rows that are still being filled in.
edited_positions = edited_positions.dropna().copy()
edited_positions["Ticker"] = edited_positions["Ticker"].str.strip().str.upper()
edited_positions["Entry date"] = pd.to_datetime(edited_positions["Entry date"]).dt.date
edited_positions = edited_positions[
    (edited_positions["Ticker"] != "") & (edited_positions["Shares"] > 0)
]

with st.sidebar:
    st.header("Save and load")
    save_column, reset_column = st.columns(2)
    if save_column.button("Save", use_container_width=True, help="Keep these positions for next time."):
        edited_positions.to_csv(SAVE_FILE, index=False)
        load_positions(edited_positions.reset_index(drop=True))
        st.toast("Portfolio saved. It will load automatically next time.")
    if reset_column.button("Reset", use_container_width=True, help="Go back to the sample portfolio."):
        SAVE_FILE.unlink(missing_ok=True)
        load_positions(SAMPLE_POSITIONS)
        st.rerun()

    st.download_button(
        "Download as CSV",
        edited_positions.to_csv(index=False),
        file_name="alphascope_portfolio.csv",
        mime="text/csv",
        use_container_width=True,
    )
    uploaded_file = st.file_uploader("Load a portfolio CSV", type="csv")
    if uploaded_file is not None and st.session_state.get("last_upload") != uploaded_file.file_id:
        st.session_state.last_upload = uploaded_file.file_id
        try:
            load_positions(read_positions(uploaded_file))
            st.rerun()
        except Exception:
            st.error(
                "That file could not be read. It needs the columns Ticker, "
                "Side, Shares, and Entry date."
            )

    st.header("Step fund")
    step_file = st.file_uploader(
        "Upload a health app export",
        type=["zip", "xml", "csv", "json"],
        help=(
            "Apple Health export.zip, a Fitbit or Google Fit export, or any CSV "
            "with a date column and a steps column. See the Step fund tab for "
            "how to export. The file stays on this computer."
        ),
    )
    if step_file is not None and st.session_state.get("last_step_upload") != step_file.file_id:
        st.session_state.last_step_upload = step_file.file_id
        try:
            with st.spinner("Reading your steps..."):
                set_steps(step_tracker.read_step_file(step_file.name, step_file))
            st.rerun()
        except step_tracker.StepFileError as error:
            st.error(str(error))

    sample_column, remove_column = st.columns(2)
    if sample_column.button("Sample", use_container_width=True, help="Try it with made-up steps."):
        set_steps(step_tracker.sample_steps())
        st.rerun()
    if remove_column.button("Remove", use_container_width=True, help="Delete the step data."):
        set_steps(None)
        st.rerun()

    cents_per_step = st.number_input(
        "Cents earned per step", min_value=0.1, max_value=100.0, value=1.0, step=0.5
    )
    add_steps_to_capital = st.toggle(
        "Add step earnings to capital",
        value=True,
        help="Money earned from steps is added to the portfolio's capital.",
    )

    st.caption(f"Prices refresh automatically every {PRICE_REFRESH_SECONDS} seconds.")


# ---------------------------------------------------------------------------
# Main dashboard. It reruns itself every minute to pick up new prices.
# ---------------------------------------------------------------------------
@st.fragment(run_every=PRICE_REFRESH_SECONDS)
def dashboard(
    positions, capital, gross_limit, target_net, steps, cents_per_step, add_steps_to_capital
):
    tickers = sorted(set(positions["Ticker"]))
    market = fetch_market_data(tuple(sorted(set(tickers) | {BENCHMARK})))
    benchmark = market.get(BENCHMARK)

    missing = sorted(set(tickers) - set(market))
    if missing:
        st.warning(
            f"No market data found for {', '.join(missing)}. Check the ticker "
            "symbols or your internet connection. They are left out below."
        )
    positions = positions[positions["Ticker"].isin(market)].copy()
    if positions.empty:
        st.info("Add at least one valid position to see the dashboard.")
        return
    tickers = sorted(set(positions["Ticker"]))
    company = fetch_company_info(tuple(tickers))
    first_entry = pd.Timestamp(min(positions["Entry date"]))

    # --- Step fund: steps since the first position earn money ---------------
    step_earnings = None
    if steps is not None:
        counted_steps = steps[steps.index >= first_entry]
        step_earnings = counted_steps * cents_per_step / 100
        if add_steps_to_capital:
            capital += step_earnings.sum()

    # --- Prices, profit and loss -------------------------------------------
    def entry_price(ticker, entry_date):
        """The closing price on the entry date (or the next trading day)."""
        closes = market[ticker]["closes"]
        on_or_after = closes[closes.index >= pd.Timestamp(entry_date)]
        return on_or_after.iloc[0] if len(on_or_after) else closes.iloc[-1]

    # A long gains when the price rises; a short gains when it falls.
    direction = positions["Side"].map({"Long": 1, "Short": -1})
    positions["Company"] = positions["Ticker"].map(lambda t: market[t]["name"])
    positions["Sector"] = positions["Ticker"].map(
        lambda t: company.get(t, {}).get("sector", "Unknown")
    )
    positions["Live price ($)"] = positions["Ticker"].map(lambda t: market[t]["price"])
    positions["Entry price ($)"] = [
        entry_price(ticker, entry_date)
        for ticker, entry_date in zip(positions["Ticker"], positions["Entry date"])
    ]
    positions["Today (%)"] = positions["Ticker"].map(
        lambda t: (market[t]["price"] / market[t]["closes"].iloc[-2] - 1) * 100
    )
    positions["Value ($)"] = positions["Shares"] * positions["Live price ($)"]
    positions["Weight (%)"] = positions["Value ($)"] / capital * 100
    positions["Signed weight (%)"] = direction * positions["Weight (%)"]
    positions["Return (%)"] = (
        direction * (positions["Live price ($)"] / positions["Entry price ($)"] - 1) * 100
    )
    positions["Profit / loss ($)"] = (
        direction * positions["Shares"]
        * (positions["Live price ($)"] - positions["Entry price ($)"])
    )

    long_exposure = positions.loc[positions["Side"] == "Long", "Weight (%)"].sum()
    short_exposure = positions.loc[positions["Side"] == "Short", "Weight (%)"].sum()
    net_exposure = long_exposure - short_exposure
    gross_exposure = long_exposure + short_exposure
    total_pnl = positions["Profit / loss ($)"].sum()
    portfolio_return = total_pnl / capital * 100

    # --- Portfolio value over time, against the S&P 500 ----------------------
    all_days = (benchmark or market[tickers[0]])["closes"].index
    days = all_days[all_days >= first_entry]
    if len(days) < 2:
        days = all_days[-2:]

    profit_by_day = pd.Series(0.0, index=days)
    for ticker, side, shares, entry_date, entry in zip(
        positions["Ticker"], positions["Side"], positions["Shares"],
        positions["Entry date"], positions["Entry price ($)"],
    ):
        prices = market[ticker]["closes"].reindex(days).ffill()
        sign = 1 if side == "Long" else -1
        held = days >= pd.Timestamp(entry_date)
        profit_by_day += (sign * shares * (prices - entry)).where(held, 0).fillna(0)

    history = pd.DataFrame({"Portfolio": capital + profit_by_day})
    versus_market = None
    if benchmark:
        market_prices = benchmark["closes"].reindex(days).ffill()
        history["S&P 500"] = capital * market_prices / market_prices.iloc[0]
        market_return = (market_prices.iloc[-1] / market_prices.iloc[0] - 1) * 100
        versus_market = portfolio_return - market_return

    # --- Signals --------------------------------------------------------------
    trend = positions["Ticker"].map(lambda t: analysis.trend_signal(market[t]["closes"]))
    fundamentals = positions["Ticker"].map(
        lambda t: analysis.fundamental_signal(company.get(t, {}))
    )
    positions["Trend"] = trend.str[0]
    positions["Trend reasoning"] = trend.str[1]
    positions["Fundamentals"] = fundamentals.str[0]
    positions["Fundamental reasoning"] = fundamentals.str[1]
    positions["Verdict"] = [
        analysis.combined_verdict(side, trend_view, fundamental_view)
        for side, trend_view, fundamental_view in zip(
            positions["Side"], positions["Trend"], positions["Fundamentals"]
        )
    ]
    conflicts = positions[positions["Verdict"].str.startswith("🔴")]

    # --- Risk -------------------------------------------------------------------
    returns = pd.DataFrame(
        {t: analysis.daily_returns(market[t]["closes"]) for t in tickers}
    )
    market_returns = analysis.daily_returns(benchmark["closes"]) if benchmark else None
    betas = {
        t: analysis.beta(returns[t], market_returns) if benchmark else None
        for t in tickers
    }
    positions["Beta"] = positions["Ticker"].map(betas)
    positions["Volatility (%)"] = positions["Ticker"].map(
        lambda t: analysis.annual_volatility(returns[t])
    )
    portfolio_beta = (positions["Signed weight (%)"] / 100 * positions["Beta"]).sum()
    portfolio_daily = sum(
        weight / 100 * returns[ticker].fillna(0)
        for ticker, weight in zip(positions["Ticker"], positions["Signed weight (%)"])
    )
    portfolio_volatility = analysis.annual_volatility(portfolio_daily)
    drawdowns = analysis.drawdown(history["Portfolio"])

    sector_net = positions.groupby("Sector")["Signed weight (%)"].sum()
    biggest_sector = sector_net.abs().idxmax()
    biggest_sector_net = sector_net[biggest_sector]

    # --- Headline numbers stay visible above every tab ------------------------
    headline = st.columns(6)
    headline[0].metric(
        "Portfolio value", f"${capital + total_pnl:,.0f}", f"{portfolio_return:+.2f}%"
    )
    headline[1].metric("Profit / loss", f"${total_pnl:+,.0f}")
    headline[2].metric(
        "vs S&P 500",
        show(versus_market, "{:+.1f} pts"),
        help=(
            "Your return minus the return from putting the same capital in the "
            "S&P 500 since your first position. Positive means you beat the market."
        ),
    )
    headline[3].metric(
        "Net exposure", f"{net_exposure:+.0f}%", help="Long weight minus short weight."
    )
    headline[4].metric(
        f"Gross (limit {gross_limit}%)",
        f"{gross_exposure:.0f}%",
        help="Long weight plus short weight.",
    )
    headline[5].metric(
        "Beta",
        show(portfolio_beta if benchmark else None, "{:.2f}"),
        help="How much the portfolio tends to move when the market moves 1%.",
    )

    latest_trade = max(data["time"] or 0 for data in market.values())
    latest_trade = datetime.fromtimestamp(latest_trade, ZoneInfo("America/New_York"))
    st.caption(
        f"Latest market price: {latest_trade:%b %d, %I:%M %p} New York time. "
        "When the market is closed, the closing price is shown."
    )

    (
        overview, holdings, reasoning, risk, pairs, ideas, step_fund, news, screen
    ) = st.tabs(
        [
            "📈 Overview", "📋 Holdings", "🧠 Reasoning", "⚖️ Risk & sectors",
            "🔗 Pair trades", "💡 Ideas", "👟 Step fund", "📰 News",
            "🔎 Valuation screen",
        ]
    )

    # -----------------------------------------------------------------------
    with overview:
        if gross_exposure > gross_limit:
            st.error(
                f"Gross exposure is {gross_exposure:.0f}%, above your "
                f"{gross_limit}% limit. Reduce position sizes or raise the limit."
            )

        left, middle, right = st.columns(3)
        with left:
            st.subheader("Value vs S&P 500")
            st.altair_chart(charts.value_chart(history), use_container_width=True)
        with middle:
            st.subheader("Profit / loss by position")
            st.altair_chart(charts.profit_chart(positions), use_container_width=True)
        with right:
            st.subheader("Exposure by position")
            st.altair_chart(charts.exposure_chart(positions), use_container_width=True)

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
                    "Ticker", "Company", "Side", "Shares", "Entry date",
                    "Entry price ($)", "Live price ($)", "Today (%)", "Value ($)",
                    "Weight (%)", "Return (%)", "Profit / loss ($)",
                ]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Shares": st.column_config.NumberColumn(format="%.0f"),
                "Entry price ($)": st.column_config.NumberColumn(format="$%.2f"),
                "Live price ($)": st.column_config.NumberColumn(format="$%.2f"),
                "Today (%)": st.column_config.NumberColumn(
                    format="%+.2f%%", help="The stock's price change since the previous close."
                ),
                "Value ($)": st.column_config.NumberColumn(format="$%.0f"),
                "Weight (%)": st.column_config.ProgressColumn(
                    format="%.0f%%", min_value=0, max_value=float(positions["Weight (%)"].max())
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
        with st.expander("How the signals work"):
            st.markdown(
                "**Trend** looks at price: is it above its 200-day average, is "
                "the 50-day average above the 200-day average, and is the stock "
                "up over six months. All three positive is Long, all three "
                "negative is Short.\n\n"
                "**Fundamentals** looks at the business: revenue growth (above "
                "10% is good, shrinking is bad), profit margin (above 15% is "
                "good, below 5% is bad), and the PEG ratio, which is the "
                "price-to-earnings ratio divided by expected growth (below 1.5 "
                "is cheap, above 3 is expensive). Two or more good marks is "
                "Long, two or more bad marks is Short.\n\n"
                "The **verdict** compares both signals with the side you chose. "
                "These rules are simplified and are not investment advice."
            )

        table_column, detail_column = st.columns([3, 2])
        with table_column:
            fundamentals_table = positions[["Ticker", "Side", "Trend", "Fundamentals", "Verdict"]].copy()
            fundamentals_table["P/E"] = positions["Ticker"].map(lambda t: company.get(t, {}).get("pe"))
            fundamentals_table["PEG"] = positions["Ticker"].map(lambda t: company.get(t, {}).get("peg"))
            fundamentals_table["Revenue growth"] = positions["Ticker"].map(
                lambda t: company.get(t, {}).get("revenue_growth")
            )
            st.dataframe(
                fundamentals_table,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Side": st.column_config.TextColumn("Your side"),
                    "P/E": st.column_config.NumberColumn(format="%.1f", help="Price-to-earnings ratio."),
                    "PEG": st.column_config.NumberColumn(format="%.1f", help="P/E divided by expected growth."),
                    "Revenue growth": st.column_config.NumberColumn(format="%+.0f%%"),
                },
            )
            if conflicts.empty:
                st.success("No position conflicts with its signals.")
            else:
                st.warning(
                    f"{', '.join(conflicts['Ticker'])} "
                    f"{'conflicts' if len(conflicts) == 1 else 'conflict'} with "
                    "the signals. Select one on the right to see why."
                )

        with detail_column:
            chosen = st.selectbox("Explain a position", list(dict.fromkeys(positions["Ticker"])))
            row = positions[positions["Ticker"] == chosen].iloc[0]
            details = company.get(chosen, {})
            st.markdown(f"**{row['Company']}** · {row['Sector']} · your side: {row['Side']}")
            st.markdown(f"{row['Verdict']}")
            st.markdown(f"**Trend: {row['Trend']}.** {row['Trend reasoning']}")
            st.markdown(f"**Fundamentals: {row['Fundamentals']}.** {row['Fundamental reasoning']}")
            st.caption(
                f"P/E {show(details.get('pe'), '{:.1f}')} · "
                f"forward P/E {show(details.get('forward_pe'), '{:.1f}')} · "
                f"PEG {show(details.get('peg'), '{:.1f}')} · "
                f"net margin {show(details.get('net_margin'), '{:.0f}%')}"
            )
            st.altair_chart(
                charts.trend_chart(market[chosen]["closes"]), use_container_width=True
            )

    # -----------------------------------------------------------------------
    with risk:
        risk_metrics = st.columns(4)
        risk_metrics[0].metric(
            "Portfolio beta",
            show(portfolio_beta if benchmark else None, "{:.2f}"),
            help=(
                "A beta of 0.5 means the portfolio tends to move 0.5% when the "
                "market moves 1%. A market-neutral fund aims for a beta near 0."
            ),
        )
        risk_metrics[1].metric(
            "Volatility (yearly)",
            f"{portfolio_volatility:.1f}%",
            help="The typical yearly swing in portfolio value, based on the past year.",
        )
        risk_metrics[2].metric(
            "Maximum drawdown",
            f"{drawdowns.min():.1f}%",
            help="The largest fall from a peak in portfolio value since your first position.",
        )
        risk_metrics[3].metric(
            "Largest sector bet",
            f"{biggest_sector_net:+.0f}%",
            biggest_sector,
            delta_color="off",
            help="The sector with the largest net exposure.",
        )

        if benchmark and abs(portfolio_beta - net_exposure / 100) > 0.15:
            st.info(
                f"Net exposure is {net_exposure:+.0f}%, but beta is "
                f"{portfolio_beta:.2f}. Your positions move "
                f"{'more' if abs(portfolio_beta) > abs(net_exposure / 100) else 'less'} "
                "with the market than their dollar weights suggest."
            )
        if abs(biggest_sector_net) > 25:
            hedge = analysis.SECTOR_ETFS.get(biggest_sector)
            hedge_side = "short" if biggest_sector_net > 0 else "long"
            st.warning(
                f"**Sector concentration.** {biggest_sector} is "
                f"{biggest_sector_net:+.0f}% net, so the portfolio is largely a "
                f"bet on that sector."
                + (
                    f" A {hedge_side} position in its sector fund ({hedge}), or in "
                    f"a weaker {biggest_sector} stock, would hedge it."
                    if hedge else ""
                )
            )

        sector_column, drawdown_column, table_column = st.columns(3)
        with sector_column:
            st.subheader("Exposure by sector")
            st.altair_chart(charts.sector_chart(positions), use_container_width=True)
        with drawdown_column:
            st.subheader("Drawdown")
            st.altair_chart(charts.drawdown_chart(drawdowns), use_container_width=True)
        with table_column:
            st.subheader("Risk by position")
            st.dataframe(
                positions[["Ticker", "Side", "Beta", "Volatility (%)"]],
                use_container_width=True,
                hide_index=True,
                height=charts.CHART_HEIGHT,
                column_config={
                    "Beta": st.column_config.NumberColumn(format="%.2f"),
                    "Volatility (%)": st.column_config.NumberColumn(format="%.0f%%"),
                },
            )

    # -----------------------------------------------------------------------
    with pairs:
        longs = list(dict.fromkeys(positions.loc[positions["Side"] == "Long", "Ticker"]))
        shorts = list(dict.fromkeys(positions.loc[positions["Side"] == "Short", "Ticker"]))

        if not longs or not shorts:
            st.info("A pair trade needs at least one long and one short position.")
        else:
            st.write(
                "A pair trade matches a long with a short in a similar business, "
                "so the result depends on which company does better rather than "
                "on the direction of the market."
            )
            sector_of = dict(zip(positions["Ticker"], positions["Sector"]))
            same_sector = [
                (long_ticker, short_ticker)
                for long_ticker in longs
                for short_ticker in shorts
                if sector_of[long_ticker] == sector_of[short_ticker]
                and sector_of[long_ticker] != "Unknown"
            ]
            default_long, default_short = same_sector[0] if same_sector else (longs[0], shorts[0])

            pick_column, chart_column = st.columns([2, 3])
            with pick_column:
                if same_sector:
                    st.caption(
                        "Same-sector pairs in your portfolio: "
                        + ", ".join(f"{a} / {b}" for a, b in same_sector)
                    )
                long_ticker = st.selectbox("Long side", longs, index=longs.index(default_long))
                short_ticker = st.selectbox("Short side", shorts, index=shorts.index(default_short))

                long_rows = positions[positions["Ticker"] == long_ticker]
                short_rows = positions[positions["Ticker"] == short_ticker]
                long_value = long_rows["Value ($)"].sum()
                short_value = short_rows["Value ($)"].sum()
                pair_pnl = long_rows["Profit / loss ($)"].sum() + short_rows["Profit / loss ($)"].sum()
                correlation = returns[long_ticker].corr(returns[short_ticker])

                pair_metrics = st.columns(2)
                pair_metrics[0].metric("Pair profit / loss", f"${pair_pnl:+,.0f}")
                pair_metrics[1].metric(
                    "Correlation",
                    f"{correlation:.2f}",
                    help=(
                        "How closely the two stocks move together day to day, "
                        "from -1 to 1. Higher means a better hedge."
                    ),
                )

                checks = []
                if sector_of[long_ticker] == sector_of[short_ticker]:
                    checks.append(f"🟢 Same sector ({sector_of[long_ticker]}).")
                else:
                    checks.append(
                        f"🟡 Different sectors ({sector_of[long_ticker]} and "
                        f"{sector_of[short_ticker]}), so sector moves are not hedged."
                    )
                if correlation >= 0.5:
                    checks.append("🟢 The stocks move together closely, so the short hedges the long.")
                elif correlation >= 0.25:
                    checks.append("🟡 The stocks move together only loosely.")
                else:
                    checks.append("🔴 The stocks barely move together, so this is two separate bets.")
                smaller, larger = sorted([long_value, short_value])
                if larger and smaller / larger >= 0.75:
                    checks.append(
                        f"🟢 Sizes are balanced (${long_value:,.0f} long, ${short_value:,.0f} short)."
                    )
                else:
                    checks.append(
                        f"🟡 Sizes are unbalanced (${long_value:,.0f} long, "
                        f"${short_value:,.0f} short), so the pair is not market neutral."
                    )
                for check in checks:
                    st.markdown(f"- {check}")

            with chart_column:
                st.subheader(f"{long_ticker} vs {short_ticker} over the past year")
                st.altair_chart(
                    charts.pair_chart(
                        market[long_ticker]["closes"], market[short_ticker]["closes"],
                        long_ticker, short_ticker,
                    ),
                    use_container_width=True,
                )
                st.caption(
                    "The pair makes money when the long line rises faster than, "
                    "or falls slower than, the short line."
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

            # 4. Concentration in one position or one sector.
            largest = positions.loc[positions["Weight (%)"].idxmax()]
            if gross_exposure > 0 and largest["Weight (%)"] / gross_exposure > 0.4:
                suggestions.append(
                    f"**Diversify.** {largest['Ticker']} is "
                    f"{largest['Weight (%)']:.0f}% of capital, more than 40% of "
                    "total exposure. Prefer a new ticker over adding to it."
                )
            if abs(biggest_sector_net) > 25:
                suggestions.append(
                    f"**Hedge your sector bet.** {biggest_sector} is "
                    f"{biggest_sector_net:+.0f}% net. Look for a "
                    f"{'short' if biggest_sector_net > 0 else 'long'} in that "
                    "sector (see the Risk & sectors tab)."
                )

            # 5. Positions that are losing money or conflict with the signals.
            losers = positions[positions["Return (%)"] <= -10]
            if not losers.empty:
                suggestions.append(
                    f"**Review losing positions.** {', '.join(losers['Ticker'])} "
                    "lost 10% or more. Check whether the original reason for "
                    "the position still holds."
                )
            if not conflicts.empty:
                suggestions.append(
                    f"**Review positions against the signals.** "
                    f"{', '.join(conflicts['Ticker'])} conflict with their trend "
                    "or fundamentals (see the Reasoning tab)."
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
                "Size (% of capital)", min_value=1.0, max_value=100.0, value=10.0, step=1.0
            )

            new_stock = fetch_market_data((new_ticker,)).get(new_ticker) if new_ticker else None
            if new_stock is None:
                st.warning("Enter a valid ticker symbol to test a new position.")
            else:
                new_company = fetch_company_info((new_ticker,)).get(new_ticker, {})
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
                new_trend, new_trend_reasoning = analysis.trend_signal(new_stock["closes"])
                new_fundamentals, new_fundamental_reasoning = analysis.fundamental_signal(new_company)

                # Checks: stays under the limit, moves toward the goal, and has
                # a reason behind the side (trend, fundamentals, or valuation).
                within_limit = new_gross <= gross_limit
                closer_to_goal = abs(target_net - new_net) < abs(target_net - net_exposure)
                reasons = []
                if new_trend == new_side:
                    reasons.append("the price trend supports it")
                if new_fundamentals == new_side:
                    reasons.append("the fundamentals support it")
                if new_direction * new_gap >= 10:
                    reasons.append(f"your fair value implies {new_gap:+.0f}%")
                reason_text = ", and ".join(reasons)

                after = st.columns(4)
                after[0].metric("Live price", f"${new_price:,.2f}")
                after[1].metric("Trend / fundamentals", f"{new_trend} / {new_fundamentals}")
                after[2].metric(
                    "Net after", f"{new_net:+.0f}%",
                    f"{new_direction * new_weight:+.0f}%", delta_color="off",
                )
                after[3].metric(
                    "Gross after", f"{new_gross:.0f}%", f"{new_weight:+.0f}%",
                    delta_color="off",
                )

                label = f"{new_side} {new_ticker} at {new_weight:.0f}%"
                if not within_limit:
                    st.error(
                        f"**Does not fit.** {label} would raise gross exposure "
                        f"to {new_gross:.0f}%, above your {gross_limit}% limit."
                    )
                elif closer_to_goal and reasons:
                    st.success(
                        f"**Good fit.** {label} moves the portfolio closer to "
                        f"your goal, and {reason_text}."
                    )
                elif closer_to_goal:
                    st.warning(
                        f"**Fits the portfolio, but no clear reason for the "
                        f"trade.** {label} moves the portfolio closer to your "
                        "goal, but neither the trend, the fundamentals, nor your "
                        "fair value supports that side."
                    )
                elif reasons:
                    st.warning(
                        f"**Good idea, wrong side for this portfolio.** For "
                        f"{label}, {reason_text}, but it moves net exposure "
                        "further from your goal. Consider a smaller size or an "
                        "offsetting position."
                    )
                else:
                    st.error(
                        f"**Poor fit.** {label} moves the portfolio away from "
                        "your goal, and neither the trend, the fundamentals, nor "
                        "your fair value supports that side."
                    )

                st.caption(
                    f"Trend: {new_trend_reasoning} Fundamentals: {new_fundamental_reasoning} "
                    f"Sector: {new_company.get('sector', 'Unknown')}."
                )
                if new_ticker in set(positions["Ticker"]):
                    st.info(
                        f"{new_ticker} is already in the portfolio, so this would "
                        "resize an existing position rather than add diversification."
                    )

    # -----------------------------------------------------------------------
    with step_fund:
        if steps is None:
            st.write(
                "Turn your steps into money to invest. Every step earns a set "
                "number of cents, which is added to the portfolio's capital. "
                "Upload a health app export in the sidebar, or press "
                "**Sample** there to try it with made-up steps."
            )
            apple, fitbit, google, other = st.columns(4)
            apple.markdown(
                "**Apple Health**\n\nOpen the Health app, tap your picture, then "
                "**Export All Health Data**. Upload the `export.zip` it creates."
            )
            fitbit.markdown(
                "**Fitbit**\n\nGo to takeout.google.com, choose **Fitbit**, and "
                "create the export. Upload the zip, or a `steps-...json` file "
                "from inside it."
            )
            google.markdown(
                "**Google Fit**\n\nGo to takeout.google.com, choose **Fit**, and "
                "create the export. Upload the zip or its "
                "`Daily activity metrics.csv`."
            )
            other.markdown(
                "**Any other app**\n\nUpload a CSV file that has a date column "
                "and a steps column, for example `Date` and `Steps`."
            )
            st.caption(
                "Your health data stays on this computer. It is not uploaded "
                "anywhere and is not included in the GitHub repository."
            )
        elif step_earnings.empty:
            st.info(
                f"Your step data ends before your first position was opened "
                f"({first_entry:%b %d, %Y}). The Step fund counts steps from "
                "that date, so upload a newer export or use an earlier entry date."
            )
        else:
            total_earned = step_earnings.sum()
            goal_steps = 10_000
            days_at_goal = int((counted_steps >= goal_steps).sum())

            # What the money would be worth if each day's earnings had gone
            # into the S&P 500 on the day they were earned.
            growth = pd.DataFrame({"Earned from steps": step_earnings.cumsum()})
            invested_value = None
            if benchmark:
                market_price = (
                    benchmark["closes"].reindex(step_earnings.index, method="ffill").bfill()
                )
                growth["If invested in the S&P 500"] = (
                    market_price * (step_earnings / market_price).cumsum()
                )
                invested_value = growth["If invested in the S&P 500"].iloc[-1]

            step_metrics = st.columns(5)
            step_metrics[0].metric("Steps counted", f"{counted_steps.sum():,.0f}")
            step_metrics[1].metric(
                "Earned from steps",
                f"${total_earned:,.0f}",
                f"{cents_per_step:g}¢ per step",
                delta_color="off",
            )
            step_metrics[2].metric(
                "If invested in the S&P 500",
                show(invested_value, "${:,.0f}"),
                show(
                    None if invested_value is None else invested_value - total_earned,
                    "{:+,.0f} market gain",
                ),
                help="Each day's step money put into the S&P 500 on the day it was earned.",
            )
            step_metrics[3].metric("Daily average", f"{counted_steps.mean():,.0f} steps")
            step_metrics[4].metric(
                f"Days at {goal_steps:,}+ steps", f"{days_at_goal} of {len(counted_steps)}"
            )

            steps_column, growth_column = st.columns(2)
            with steps_column:
                st.subheader("Daily steps")
                st.altair_chart(
                    charts.steps_chart(counted_steps, goal_steps), use_container_width=True
                )
            with growth_column:
                st.subheader("Step money over time")
                st.altair_chart(
                    charts.line_chart(
                        growth,
                        "Value ($)",
                        {
                            "Earned from steps": charts.NEUTRAL_COLOR,
                            "If invested in the S&P 500": charts.LONG_COLOR,
                        },
                    ),
                    use_container_width=True,
                )

            st.caption(
                f"Counting steps from {first_entry:%b %d, %Y}, when your first "
                f"position was opened, to {counted_steps.index[-1]:%b %d, %Y}. "
                + (
                    f"The ${total_earned:,.0f} earned is included in portfolio capital."
                    if add_steps_to_capital
                    else "Step earnings are not being added to portfolio capital."
                )
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

                screen_trend, screen_trend_reasoning = analysis.trend_signal(stock["closes"])
                screen_fundamentals, screen_fundamental_reasoning = analysis.fundamental_signal(
                    fetch_company_info((ticker,)).get(ticker, {})
                )
                st.markdown(f"**Trend: {screen_trend}.** {screen_trend_reasoning}")
                st.markdown(
                    f"**Fundamentals: {screen_fundamentals}.** {screen_fundamental_reasoning}"
                )

        st.caption(
            "This is a simplified valuation screen, not a verified investment "
            "recommendation. A valuation gap alone is not enough to justify a trade."
        )


if edited_positions.empty:
    st.info("Open **Edit positions** above and add at least one stock.")
else:
    dashboard(
        edited_positions, capital, gross_limit, GOALS[goal],
        st.session_state.steps, cents_per_step, add_steps_to_capital,
    )
