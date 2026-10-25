# MarketScope --- Real-Time Market Intelligence Dashboard

MarketScope is a Streamlit-based market monitoring dashboard for viewing
cryptocurrency and Indian stock prices, comparing price charts,
inspecting technical indicators, explaining rule-based market signals,
and detecting unusual market activity.

> **Disclaimer:** MarketScope is an educational and analytical project,
> not financial advice. Anomaly thresholds are heuristic and do not
> represent calibrated probabilities or guaranteed predictions.

## Features

-   **Interactive market dashboard** with a responsive,
    black-and-charcoal visual theme.
-   **Line and candlestick charts** with selectable timeframes.
-   **Technical indicators:** SMA20, SMA50, and RSI14.
-   **Market signal explanation** that summarizes the conditions behind
    the current rule-based signal.
-   **Multi-factor anomaly detection** using:
    -   Unusual price movement compared with recent returns.
    -   Volume spikes compared with the preceding candles.
    -   RSI14 extreme readings.
    -   Price deviation from SMA20.
-   **Severity and score display** with triggered factors and
    plain-language explanations.
-   **Alert history and anomaly history** backed by PostgreSQL.
-   **Asset and severity filters** for reviewing saved anomaly events.
-   **INR display support:** Indian stock prices are shown in INR;
    USD/USDT/USDC-quoted crypto prices are converted using the
    configured fixed USD-to-INR rate.

## Technology stack

-   Python
-   Streamlit
-   Pandas and NumPy
-   Plotly
-   Requests
-   Yahoo Finance data via the project's `stock_data.py` module
-   Binance public market-data API
-   PostgreSQL using Psycopg connection pooling
-   `python-dotenv` for local environment configuration

## Project structure

Keep the following files together in the project directory:

``` text
market-visualizer/
├── app.py
├── database.py
├── schema.sql
├── indicators.py
├── stock_data.py
├── anomaly_detection.py
├── requirements.txt
├── .env                 # local only; do not commit
└── .gitignore
```

The `app.py` dashboard imports the other Python modules, and
`database.py` initializes and queries the PostgreSQL schema from
`schema.sql`.

## Run locally

### 1. Create and activate a virtual environment

Windows PowerShell:

``` powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

If the project already has a `requirements.txt` file:

``` powershell
pip install -r requirements.txt
```

If you are preparing the dependency file, make sure it includes the
packages imported by the project, including:

``` text
streamlit
pandas
numpy
plotly
requests
python-dotenv
psycopg[binary,pool]
yfinance
```

Install the dependencies:

``` powershell
pip install -r requirements.txt
```

### 3. Configure PostgreSQL

Create or select a PostgreSQL database that your computer can connect
to. In the project root, create a `.env` file:

``` dotenv
DATABASE_URL=postgresql://USERNAME:PASSWORD@HOST:5432/DATABASE_NAME
```

Replace the example values with your actual database credentials. Do not
share the connection string or commit `.env` to GitHub.

The database module expects `DATABASE_URL`. On startup, the app
initializes the schema using `schema.sql`. Confirm that your PostgreSQL
server is running and reachable before launching the app.

### 4. Launch Streamlit

``` powershell
streamlit run app.py
```

Open the local URL printed by Streamlit, usually:

``` text
http://localhost:8501
```

## Data sources and currency handling

-   **Cryptocurrency:** Binance public market-data endpoint for
    completed OHLCV candles.
-   **Indian equities:** Yahoo Finance data through `stock_data.py`.
-   **Crypto conversion:** The current application defines a fixed
    `USD_TO_INR` rate in `app.py`. This is an approximation, not a live
    foreign-exchange feed. Update it or replace it with a live FX source
    if live conversion is required.
-   **Stocks:** Prices are expected to remain in INR.

Availability and history depend on the source provider, selected symbol,
and timeframe. External APIs may rate-limit requests or temporarily be
unavailable.

## How anomaly scoring works

The detector evaluates a selected asset's recent candle data and checks
four heuristic factors:

  ------------------------------------------------------------------------
  Factor                Current rule in the                          Score
                        detector              
  --------------------- --------------------- ----------------------------
  Price movement        Latest return differs                            2
                        from the recent       
                        return baseline by    
                        more than the larger  
                        of 3 standard         
                        deviations or 0.5     
                        percentage points     

  Volume spike          Latest volume is at                              2
                        least 2× the median   
                        volume of the         
                        preceding candles     

  RSI14 extreme         RSI14 is at least 80                             1
                        or at most 20         

  SMA20 deviation       Absolute price                                   1
                        deviation from SMA20  
                        is at least 3%        
  ------------------------------------------------------------------------

The score ranges from 0 to 6. The current severity mapping is:

-   **NORMAL:** 0 points
-   **LOW:** 1 point
-   **MEDIUM:** 2--3 points
-   **HIGH:** 4 or more points

These are starting thresholds, not statistically calibrated
probabilities. Equal scores across different assets can occur naturally;
the detector should not artificially force different scores. Review the
displayed metrics and explanations to understand each result.

## Deploy online

A common deployment route for this project is GitHub plus Streamlit
Community Cloud and a hosted PostgreSQL database.

1.  Push the project code to a GitHub repository.
2.  Provision a hosted PostgreSQL database that accepts connections from
    the deployment environment.
3.  Add `DATABASE_URL` to the deployment platform's secret settings.
4.  Confirm that the app's database configuration reads the
    secret/environment variable and initializes the schema.
5.  Deploy `app.py` from Streamlit Community Cloud.
6.  Test market data, chart rendering, alerts, and anomaly-history
    persistence on the deployed site.

Before pushing to GitHub, verify `.gitignore` excludes `.env`, virtual
environments, caches, and any local database files containing private or
user data. Never place database passwords or API secrets in source code
or README files.

Useful links:

-   [GitHub](https://github.com/)
-   [Streamlit Community Cloud](https://share.streamlit.io/)
-   [Streamlit documentation](https://docs.streamlit.io/)
-   [PostgreSQL documentation](https://www.postgresql.org/docs/)
-   [Binance market data](https://data-api.binance.vision/)

## Known limitations and deployment checks

-   Anomaly thresholds are heuristic and may need tuning and validation
    against each asset and timeframe.
-   A fixed USD-to-INR conversion rate can make converted crypto prices
    differ from the live INR exchange rate.
-   Public data providers can have delays, outages, rate limits, or
    symbol-format differences.
-   Verify the exact packages in `requirements.txt` against the imports
    in all project modules before deployment.
-   Test PostgreSQL connection, schema initialization, event
    de-duplication, and history loading on the hosted environment.
-   A successful local run or Python syntax check does not by itself
    guarantee a successful cloud deployment.

## Future improvements

-   Use a live FX source for currency conversion.
-   Add automated tests for indicators, scoring thresholds, and database
    operations.
-   Add configuration controls for anomaly thresholds.
-   Add event deduplication and database indexes where appropriate.
-   Add monitoring for provider failures and database availability.
-   Add deployment health checks and a clear connection status
    indicator.

## License

Choose and add a license before publishing this repository for reuse by
others.
