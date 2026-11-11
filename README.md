# AlphaScope — Long/Short Equity Research Platform

**Student:** Tucker Martin

## App description

AlphaScope is an educational hedge fund-style portfolio simulator and stock
research screener built with Streamlit. Users build a hypothetical long/short
stock portfolio, and the app calculates its long, short, net, and gross
exposure and its simulated profit or loss. A second tab screens a single stock
by comparing its price with the user's own fair-value estimate.

All prices are entered by the user, so the app works instantly without
downloading market data. It is a learning tool, not an investment
recommendation.

**Intended users:** College students, student investment clubs, beginner
investors, and aspiring equity research analysts.

## Current features

**Portfolio builder**

- Set the portfolio's starting capital.
- Add, edit, and remove positions in a table: ticker, long or short, weight,
  entry price, and current price.
- See long, short, net, and gross exposure update as positions change.
- See the simulated portfolio value and profit or loss, in total and per position.
- Set a maximum gross exposure and get a warning when the portfolio exceeds it.
- Read a plain-language summary of whether the portfolio is net long, net
  short, or close to market neutral.
- View a bar chart of exposure by position.
- Choose a portfolio goal (market neutral, moderately net long, or net long)
  and get rule-based suggestions for what kind of position to add next.
- Test a specific new stock: see net and gross exposure after adding it and
  whether it fits the goal, the exposure limit, and your fair-value estimate.

**Stock valuation screen**

- Enter a ticker, current share price, and estimated fair value.
- Adjust the percentage gap needed to show a research flag.
- See the estimated upside or downside and a potential long, short, or neutral
  research classification with an explanation.

## Planned features

- Optional on-demand market data for the stocks in the portfolio, with caching
  and clear handling of slow or unavailable data sources.
- Historical price and portfolio performance charts.
- Financial ratio analysis and company comparisons.
- Sector exposure and hedge suggestions, such as pair trades and sector ETFs.
- Saved watchlists and portfolios.

## Run locally

1. Install Python 3.
2. From the project folder, install the dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

3. Start the Streamlit app:

   ```bash
   streamlit run app.py
   ```

4. Open the local URL printed by Streamlit in your browser.
