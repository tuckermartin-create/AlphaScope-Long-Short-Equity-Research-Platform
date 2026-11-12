# AlphaScope — Long/Short Equity Research Platform

**Student:** Tucker Martin

## App description

AlphaScope is an educational hedge fund-style portfolio tracker built with
Streamlit. Users enter the stocks they hold, the side (long or short), the
number of shares, and the date each position was opened. The app looks up
market prices automatically, refreshes them every minute, and shows the
portfolio's value, exposure, and profit or loss against the S&P 500. It also
explains whether each stock's price trend and business fundamentals support
the chosen side, measures risk, analyzes pair trades, suggests what to add
next, and shows news on the holdings.

Its signals and suggestions come from simple rules and are for learning, not
verified investment advice.

**Intended users:** College students, student investment clubs, beginner
investors, and aspiring equity research analysts.

## Current features

- **Automatic market data.** Prices, price history, company fundamentals, and
  sectors come from Yahoo Finance. Prices refresh every minute; everything is
  cached so the app stays fast.
- **Positions with shares and entry dates.** Add, remove, or resize positions
  in a table. The entry price is looked up from the entry date. The app starts
  with a 12-position sample portfolio (8 longs, 4 shorts).
- **Save and load.** Save the portfolio so it loads next time, reset to the
  sample, or download and upload it as a CSV file.
- **Overview tab.** Portfolio value against the S&P 500, profit or loss by
  position, and exposure by position.
- **Holdings tab.** Entry price, live price, today's change, value, weight,
  return, and profit or loss for every position.
- **Reasoning tab.** Two signals for each stock, and whether they support or
  conflict with the chosen side:
  - *Trend:* price against its 200-day average, 50-day against 200-day
    average, and six-month change.
  - *Fundamentals:* revenue growth, profit margin, and PEG ratio.
- **Risk & sectors tab.** Portfolio beta, volatility, maximum drawdown,
  exposure by sector with a hedge suggestion when one sector dominates, and
  beta and volatility for each position.
- **Pair trades tab.** Match a long against a short, see how the two have
  moved, their correlation, the pair's profit or loss, and whether the pair is
  in the same sector and balanced in size.
- **Ideas tab.** Rule-based suggestions for what to add next, and a tester
  that shows how a new stock would change exposure and whether its trend,
  fundamentals, or the user's fair-value estimate support it.
- **News tab.** Recent Yahoo Finance headlines for selected holdings.
- **Valuation screen tab.** Compare any stock's live price with the user's
  fair-value estimate to get a long, short, or neutral research flag.

## Planned features

- Record closed trades so realized profit is tracked along with open positions.
- Trading costs and the cost of borrowing shares for short positions.
- Position sizing based on risk, so volatile stocks get smaller weights.
- Alerts when a position hits a price target or a stop-loss level.
- More fundamentals, such as debt levels, cash flow, and analyst estimates.

## Project files

- `app.py` — the Streamlit page: settings, positions, and the dashboard tabs.
- `market_data.py` — downloads prices, fundamentals, sectors, and news.
- `analysis.py` — the long/short signal rules and risk calculations.
- `charts.py` — the charts.

## Run locally

1. Install Python 3.9 or newer.
2. From the project folder, install the dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

3. Start the Streamlit app:

   ```bash
   streamlit run app.py
   ```

4. Open the local URL printed by Streamlit in your browser. An internet
   connection is needed for prices, fundamentals, and news.
