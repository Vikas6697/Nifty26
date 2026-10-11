# Nifty 50 Dashboard + Email Alerts

## Features
- Streamlit dashboard with top-ranked stocks and all scan results
- Rule-based trend/momentum/volume/breakout score
- CSV download
- Optional manual email alert send when you click the button
- Not a broker integration; it does not execute trades

## Run locally
1. Install Python 3.10+
2. In this folder, run: `pip install -r requirements.txt`
3. Run: `streamlit run app.py`
4. Open the local URL Streamlit displays.

## Run on a phone via Streamlit Community Cloud
1. Create a GitHub account and a new repository.
2. Upload `app.py` and `requirements.txt`.
3. Sign in to Streamlit Community Cloud and deploy the repository.
4. Open the deployed dashboard on your Android phone.
   Deployment provider availability and terms may change; check current instructions.

## Email alerts
- Open the Email alerts tab and enter SMTP details only if you understand the security implications.
- Gmail typically requires 2-Step Verification and an App Password. Never enter your normal Google password.
- The current implementation sends an email only when you click “Send qualifying email now.” It does not run 24/7 or send background scheduled alerts.
- For true scheduled alerts, deploy to an always-on service or schedule a job; keep SMTP credentials in platform secrets/environment variables, never in public code.

## Limitations
- Yahoo Finance history may be delayed, incomplete or unavailable.
- The symbol list is manually maintained and can become outdated.
- Intraday selection is not true intraday analysis: the app currently uses daily candles.
- The score is heuristic, not a calibrated probability or proven strategy.
- ATR stop/target values are illustrative only.
- This is not financial advice; paper-test and include costs/slippage before trading.
