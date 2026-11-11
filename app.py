import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="AlphaScope",
    page_icon="📊",
    layout="wide",
)

st.title("AlphaScope — Long/Short Equity Research Platform")
st.write(
    "Build a hypothetical long/short stock portfolio and see its exposure and "
    "simulated profit or loss, or screen a single stock against your own "
    "fair-value estimate. All prices are entered by you, so nothing is "
    "downloaded and the app responds instantly."
)
st.caption(
    "AlphaScope is an educational simulator. It does not use live market data "
    "and does not give investment recommendations."
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

    starting_positions = pd.DataFrame(
        {
            "Ticker": ["MSFT", "AAPL", "TSLA"],
            "Side": ["Long", "Long", "Short"],
            "Weight (%)": [35.0, 35.0, 30.0],
            "Entry price ($)": [400.0, 200.0, 250.0],
            "Current price ($)": [420.0, 210.0, 240.0],
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
