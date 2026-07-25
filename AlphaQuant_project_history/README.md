# AlphaQuant: Institutional-Grade ML Trading Engine

AlphaQuant is a fully autonomous, institutional-grade machine learning trading engine for cryptocurrency futures markets. The system ingests and processes market data, trains an ensemble of AI models to predict market movements, and executes trades in a live, production environment with built-in risk management and state persistence.

## Key Features

- **Multi-Signal AI Core:** Identifies distinct market regimes (Trend, Breakout, Reversion) and deploys specialized AI models for each.
- **Ensemble Modeling:** Combines XGBoost and LightGBM models to improve prediction robustness and reduce model-specific errors.
- **Automated Data Pipeline:** Ingests, validates, and processes terabytes of historical market data into a MySQL database.
- **Rigorous Validation Suite:** Employs out-of-sample, walk-forward validation and reliability curve analysis to mathematically verify model performance before deployment.
- **Production-Hardened Live Engine:** Features asynchronous architecture, state persistence for graceful recovery from crashes, and secure secrets management.
- **Automated Risk Management:** Includes a "Degradation Lock" (penalty box) that automatically disables trading for underperforming asset-model pairs.

## Technology Stack

- **Programming Language:** Python 3.12+
- **Data Science & ML:** Pandas, NumPy, Scikit-learn, XGBoost, LightGBM, SHAP, Statsmodels
- **Database:** MySQL (Production), SQLite (Development)
- **Connectivity:** `ccxt` (REST & WebSockets), `requests` (Telegram API)
- **Deployment:** Linux/Ubuntu, `screen`, `git`

## Folder Structure

```
AlphaQuant_project_history/
│
├── README.md
├── PROJECT_CONTEXT.md
├── ... (13 other documentation files)
│
├── src/                      # Main source code (Python scripts)
│   ├── main_v7.py
│   ├── feature_library.py
│   └── ...
├── tests/                    # Unit and integration tests (TBD)
├── models/                   # Saved .pkl model files (ignored by git)
├── configs/                  # Configuration files (TBD)
├── logs/                     # CSV trade logs and application logs (ignored by git)
└── scripts/                  # Utility and deployment scripts
```

## Installation

1.  Clone the repository: `git clone <repository_url>`
2.  Navigate to the project directory: `cd AlphaQuant-ML-Trading-AI-BOT-`
3.  Create a Python virtual environment: `python3 -m venv aq_env`
4.  Activate the environment: `source aq_env/bin/activate`
5.  Install dependencies: `pip install -r requirements.txt`

## Running the Project

### 1. Offline Pipeline (Training & Validation)

Set database credentials and run the master pipeline to generate the AI models (`.pkl` files).

```bash
export DB_PASS="Your_DB_Password"
python run_full_pipeline_v7.py
```

### 2. Live Engine

Set all production secrets and launch the main application.

```bash
export DB_PASS="Your_DB_Password"
export TELEGRAM_TOKEN="Your_Telegram_Token"
export TELEGRAM_CHAT_ID="Your_Chat_ID"

# For production on a server
screen -S v6_live -d -m python main_v7.py

# For local testing
python main_v7.py
```

## Important Notes

- This system is designed for production use and manages real financial risk. Do not run with `LIVE_TRADING_ENABLED = True` without fully understanding the code and risks involved.
- The system's performance is highly dependent on the quality of the trained models. Always run the validation suite to assess model viability before live deployment.
