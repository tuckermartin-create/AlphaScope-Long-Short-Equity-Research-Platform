"""The rules AlphaScope uses to judge stocks and measure portfolio risk.

These are simple, explainable rules for learning. They are not verified
investment advice.
"""

import pandas as pd


TRADING_DAYS_PER_YEAR = 252

# A sector fund that could be used to hedge exposure to each sector.
SECTOR_ETFS = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financial Services": "XLF",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Communication Services": "XLC",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Basic Materials": "XLB",
}


# ---------------------------------------------------------------------------
# Long/short signals
# ---------------------------------------------------------------------------
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


def fundamental_signal(info):
    """Classify a company's fundamentals as Long, Short, or Neutral, with reasons.

    Each of three checks scores +1 (good), -1 (bad), or 0 (in between):
    1. Growth: revenue grew more than 10% (good) or shrank (bad).
    2. Profitability: profit margin above 15% (good) or below 5% (bad).
    3. Valuation: PEG ratio below 1.5 (good) or above 3 (bad). The PEG ratio
       is the price-to-earnings ratio divided by expected earnings growth.

    A total of +2 or more is Long, -2 or less is Short, otherwise Neutral.
    """
    score = 0
    reasons = []

    growth = info.get("revenue_growth")
    if growth is not None:
        if growth > 10:
            score += 1
            reasons.append(f"revenue grew {growth:.0f}% (strong)")
        elif growth < 0:
            score -= 1
            reasons.append(f"revenue fell {abs(growth):.0f}% (weak)")
        else:
            reasons.append(f"revenue grew {growth:.0f}% (moderate)")

    # Banks do not report operating income, so fall back to net margin.
    margin = info.get("operating_margin")
    margin_name = "operating margin"
    if margin is None:
        margin = info.get("net_margin")
        margin_name = "net margin"
    if margin is not None:
        if margin > 15:
            score += 1
            reasons.append(f"{margin_name} is {margin:.0f}% (high)")
        elif margin < 5:
            score -= 1
            reasons.append(f"{margin_name} is {margin:.0f}% (low)")
        else:
            reasons.append(f"{margin_name} is {margin:.0f}% (average)")

    peg = info.get("peg")
    if peg is not None and peg > 0:
        if peg < 1.5:
            score += 1
            reasons.append(f"PEG ratio is {peg:.1f} (cheap for its growth)")
        elif peg > 3:
            score -= 1
            reasons.append(f"PEG ratio is {peg:.1f} (expensive for its growth)")
        else:
            reasons.append(f"PEG ratio is {peg:.1f} (fairly priced)")

    if not reasons:
        return "Neutral", "No fundamental data available for this ticker."

    reasoning = "; ".join(reasons) + "."
    reasoning = reasoning[0].upper() + reasoning[1:]
    if score >= 2:
        return "Long", reasoning
    if score <= -2:
        return "Short", reasoning
    return "Neutral", reasoning


def combined_verdict(side, trend, fundamentals):
    """Compare the two signals with the side the user chose."""
    signals = [trend, fundamentals]
    supports = signals.count(side)
    conflicts = sum(1 for signal in signals if signal not in (side, "Neutral"))

    if supports == 2:
        return "🟢 Strongly supports your side"
    if supports == 1 and conflicts == 0:
        return "🟢 Supports your side"
    if conflicts == 2:
        return "🔴 Strongly conflicts with your side"
    if conflicts == 1 and supports == 0:
        return "🔴 Conflicts with your side"
    return "🟡 Mixed evidence"


# ---------------------------------------------------------------------------
# Recommended changes
# ---------------------------------------------------------------------------
ADD_FRACTION = 0.25  # "Add" grows a position by a quarter.
LARGE_POSITION = 15  # Do not add to positions above this % of capital.


def recommended_action(verdict):
    """Turn a verdict into an action for an existing position."""
    if verdict.startswith("🟢 Strongly"):
        return "Add"
    if verdict.startswith("🔴 Strongly"):
        return "Close"
    if verdict.startswith("🔴"):
        return "Trim"
    return "Hold"


def shares_after(action, shares):
    """How many shares the position should have after the action."""
    if action == "Close":
        return 0
    if action == "Trim":
        return max(1, round(shares / 2))
    if action == "Add":
        return -(-shares * (1 + ADD_FRACTION) // 1)  # Round up to whole shares.
    return shares


def trend_change(closes, lookback=10):
    """Report whether the trend turned in the last two weeks of trading.

    Returns ("up" or "down", description), or None if nothing changed.
    """
    if len(closes) < 200 + lookback:
        return None

    average_50 = closes.rolling(50).mean()
    average_200 = closes.rolling(200).mean()
    before = -1 - lookback

    price_above_now = closes.iloc[-1] > average_200.iloc[-1]
    price_above_before = closes.iloc[before] > average_200.iloc[before]
    if price_above_now != price_above_before:
        direction = "up" if price_above_now else "down"
        return direction, (
            f"the price crossed {'above' if price_above_now else 'below'} its "
            "200-day average in the last two weeks"
        )

    average_above_now = average_50.iloc[-1] > average_200.iloc[-1]
    average_above_before = average_50.iloc[before] > average_200.iloc[before]
    if average_above_now != average_above_before:
        direction = "up" if average_above_now else "down"
        return direction, (
            f"the 50-day average crossed {'above' if average_above_now else 'below'} "
            "the 200-day average in the last two weeks"
        )

    return None


# ---------------------------------------------------------------------------
# Risk measures
# ---------------------------------------------------------------------------
def daily_returns(closes, days=TRADING_DAYS_PER_YEAR):
    """Daily percentage price changes over roughly the past year."""
    return closes.pct_change().iloc[-days:]


def beta(stock_returns, market_returns):
    """How much a stock tends to move when the market moves 1%."""
    both = pd.concat([stock_returns, market_returns], axis=1).dropna()
    if len(both) < 30:
        return None
    return both.iloc[:, 0].cov(both.iloc[:, 1]) / both.iloc[:, 1].var()


def annual_volatility(returns):
    """Typical yearly swing, in percent, based on daily returns."""
    return returns.std() * (TRADING_DAYS_PER_YEAR ** 0.5) * 100


def drawdown(values):
    """Percentage fall from the highest value reached so far, for each day."""
    return (values / values.cummax() - 1) * 100
