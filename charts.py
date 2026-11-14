"""Charts used by the AlphaScope dashboard."""

import altair as alt
import pandas as pd


# Colors from the "Clear ledger" design (see ui.py).
LONG_COLOR = "#0E8A5F"
SHORT_COLOR = "#C8372D"
NEUTRAL_COLOR = "#8A8F98"
ACTION_COLOR = "#1F4FD8"
STEP_COLOR = "#B5661A"
CHART_HEIGHT = 300


def styled(chart):
    """Give a chart the app's font, quiet grid lines, and a clear background."""
    return (
        chart.configure(background="transparent", font="Inter")
        .configure_view(strokeWidth=0)
        # Semi-transparent grey lines read on both light and dark backgrounds;
        # Streamlit colors the labels to match its theme.
        .configure_axis(
            gridColor="rgba(128,128,128,0.25)", domainColor="rgba(128,128,128,0.25)",
            tickColor="rgba(128,128,128,0.25)", labelFontSize=12, titleFontSize=12,
        )
        .configure_legend(labelFontSize=13, symbolStrokeWidth=3)
    )

SIDE_COLORS = alt.Scale(domain=["Long", "Short"], range=[LONG_COLOR, SHORT_COLOR])


def line_chart(data, y_title, colors, value_format="$,.0f"):
    """Line chart of one or more columns over time. `colors` maps column to color."""
    long_form = (
        data.rename_axis("Date").reset_index()
        .melt("Date", var_name="Line", value_name="Value").dropna()
    )
    return styled(
        alt.Chart(long_form)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X("Date:T", title=None),
            y=alt.Y("Value:Q", title=y_title, scale=alt.Scale(zero=False)),
            color=alt.Color(
                "Line:N",
                scale=alt.Scale(domain=list(colors), range=list(colors.values())),
                legend=alt.Legend(orient="top", title=None),
            ),
            tooltip=["Line", alt.Tooltip("Date:T"), alt.Tooltip("Value:Q", format=value_format)],
        )
        .properties(height=CHART_HEIGHT)
    )


def value_chart(history):
    """Portfolio value against the same money invested in the S&P 500."""
    colors = {"Portfolio": ACTION_COLOR, "S&P 500": NEUTRAL_COLOR}
    return line_chart(history, "Value ($)", {k: v for k, v in colors.items() if k in history})


def trend_chart(closes):
    """The past year's price with its 50-day and 200-day averages."""
    data = pd.DataFrame(
        {
            "Price": closes,
            "50-day average": closes.rolling(50).mean(),
            "200-day average": closes.rolling(200).mean(),
        }
    ).iloc[-250:]
    colors = {"Price": ACTION_COLOR, "50-day average": LONG_COLOR, "200-day average": SHORT_COLOR}
    return line_chart(data, "Price ($)", colors, value_format="$,.2f")


def pair_chart(long_closes, short_closes, long_ticker, short_ticker):
    """Both stocks of a pair over the past year, each starting at 100."""
    data = pd.concat([long_closes, short_closes], axis=1).dropna().iloc[-250:]
    data = data / data.iloc[0] * 100
    data.columns = [f"{long_ticker} (long)", f"{short_ticker} (short)"]
    colors = {data.columns[0]: LONG_COLOR, data.columns[1]: SHORT_COLOR}
    return line_chart(data, "Price (start = 100)", colors, value_format=".1f")


def profit_chart(positions):
    """Profit or loss for each position."""
    return styled(
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
    """Position weights: longs above zero, shorts below."""
    return styled(
        alt.Chart(positions)
        .mark_bar()
        .encode(
            x=alt.X("Ticker:N", sort="-y", title=None),
            y=alt.Y("Signed weight (%):Q", title="Weight (% of capital)"),
            color=alt.Color("Side:N", scale=SIDE_COLORS, legend=alt.Legend(orient="top", title=None)),
            tooltip=["Ticker", "Side", alt.Tooltip("Weight (%):Q", format=".1f")],
        )
        .properties(height=CHART_HEIGHT)
    )


def sector_chart(positions):
    """Long and short weight in each sector."""
    return styled(
        alt.Chart(positions)
        .mark_bar()
        .encode(
            x=alt.X("sum(Signed weight (%)):Q", title="Weight (% of capital)"),
            y=alt.Y("Sector:N", title=None, sort="-x", axis=alt.Axis(labelLimit=180)),
            color=alt.Color("Side:N", scale=SIDE_COLORS, legend=alt.Legend(orient="top", title=None)),
            tooltip=["Sector", "Side", alt.Tooltip("sum(Signed weight (%)):Q", format="+.1f", title="Weight (%)")],
        )
        .properties(height=CHART_HEIGHT)
    )


def drawdown_chart(drawdowns):
    """How far the portfolio has been below its highest value."""
    data = drawdowns.rename("Drawdown").rename_axis("Date").reset_index()
    return styled(
        alt.Chart(data)
        .mark_area(color=SHORT_COLOR, opacity=0.5, line={"color": SHORT_COLOR})
        .encode(
            x=alt.X("Date:T", title=None),
            y=alt.Y("Drawdown:Q", title="Below peak (%)"),
            tooltip=[alt.Tooltip("Date:T"), alt.Tooltip("Drawdown:Q", format=".1f")],
        )
        .properties(height=CHART_HEIGHT)
    )


def steps_chart(steps, goal):
    """Daily steps as bars, with a 7-day average and a goal line."""
    data = pd.DataFrame(
        {"Steps": steps, "7-day average": steps.rolling(7, min_periods=1).mean()}
    ).rename_axis("Date").reset_index()
    base = alt.Chart(data).encode(x=alt.X("Date:T", title=None))
    bars = base.mark_bar(color=STEP_COLOR, opacity=0.35).encode(
        y=alt.Y("Steps:Q", title="Steps"),
        tooltip=[alt.Tooltip("Date:T"), alt.Tooltip("Steps:Q", format=",.0f")],
    )
    average = base.mark_line(color=STEP_COLOR, strokeWidth=2.5).encode(y="7-day average:Q")
    goal_line = (
        alt.Chart(pd.DataFrame({"Goal": [goal]}))
        .mark_rule(color=NEUTRAL_COLOR, strokeDash=[5, 3])
        .encode(y="Goal:Q")
    )
    return styled((bars + average + goal_line).properties(height=CHART_HEIGHT))
