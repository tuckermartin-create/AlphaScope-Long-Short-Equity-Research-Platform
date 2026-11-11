# AlphaScope — Long/Short Equity Research Platform

**Student:** Tucker Martin

## App description

AlphaScope is an educational hedge fund-style portfolio tracker built with
Streamlit. Users choose stocks, a side (long or short), and a size for each
position. The app looks up market prices automatically, refreshes them every
minute, and shows the portfolio's value, exposure, and profit or loss. It also
explains whether each stock's price trend supports the chosen side, suggests
what kind of position to add next, and shows news on the holdings.

Its signals and suggestions come from simple rules and are for learning, not
verified investment advice.

**Intended users:** College students, student investment clubs, beginner
investors, and aspiring equity research analysts.

## Current features

- **Automatic market prices.** Prices and price history come from Yahoo
  Finance, are cached for one minute, and refresh on their own. Entry prices
  are looked up from the date the positions were opened, so no prices need to
  be typed in.
- **Sidebar settings.** Portfolio capital, how long ago positions were opened,
  maximum gross exposure, and a portfolio goal.
- **Editable positions.** Add, remove, or resize stocks in a table. The app
  starts with a 12-position sample portfolio (8 longs, 4 shorts).
- **Overview tab.** Portfolio value over time, profit or loss by position, and
  exposure by position as charts, with headline numbers always visible.
- **Holdings tab.** Entry price, live price, today's change, return, and profit
  or loss for every position.
- **Long/short reasoning tab.** A trend signal for each stock based on three
  rules (price against its 200-day average, 50-day against 200-day average,
  and six-month change), whether it supports or conflicts with the chosen
  side, and a price chart with both averages.
- **Ideas tab.** Rule-based suggestions for what to add next, and a tester
  that shows how a new stock would change exposure and whether it fits the
  goal, the exposure limit, its price trend, and the user's fair-value estimate.
- **News tab.** Recent Yahoo Finance headlines for selected holdings.
- **Valuation screen tab.** Compare any stock's live price with the user's
  fair-value estimate to get a long, short, or neutral research flag.

## Planned features

- Company fundamentals such as P/E ratio, revenue growth, and margins, used in
  the long/short reasoning alongside the price trend.
- Sector exposure and hedge suggestions, such as pair trades and sector ETFs.
- Risk measures such as volatility, beta, and drawdown.
- Saved portfolios and watchlists.
- Exact entry dates and share counts for each position.

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
   connection is needed for prices and news.
