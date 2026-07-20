import sqlite3
import os

DB_NAME = "alphaquant_ml_v4.db"

def init_db():
    print("==================================================")
    print("  ALPHAQUANT V4.0: DATABASE INITIALIZATION        ")
    print("==================================================")
    
    # Check if DB already exists
    if os.path.exists(DB_NAME):
        print(f"[INFO] Database '{DB_NAME}' already exists. Connecting...")
    else:
        print(f"[INFO] Creating new database '{DB_NAME}'...")

    # Connect to SQLite (this creates the file if it doesn't exist)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 🟢 Table 1: Raw OHLCV Data
    # We store the raw candles so we can recalculate features anytime without re-downloading
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS market_data_1h (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset TEXT NOT NULL,
        timestamp INTEGER NOT NULL,
        datetime TEXT NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume REAL,
        UNIQUE(asset, timestamp) -- Prevents duplicate candles
    )
    ''')
    print("[SUCCESS] Table 'market_data_1h' verified.")

    # 🟢 Table 2: The Feature Store
    # This holds the mathematical numbers the ML model will actually read
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS feature_store (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset TEXT NOT NULL,
        timestamp INTEGER NOT NULL,
        
        -- Trend Features (Normalized distances, not strings)
        dist_ema_50 REAL,
        dist_ema_200 REAL,
        dist_vwap REAL,
        
        -- Volatility Features
        atr_pct REAL,
        market_regime_vol REAL, -- BTC volatility reference
        
        -- SMC / Microstructure Features
        fvg_proximity REAL,     -- Distance to nearest unmitigated FVG
        volume_delta_ratio REAL,
        funding_rate REAL,
        
        -- The ML Label (What we are trying to predict)
        -- 1 = Hit 2% TP before 1% SL. 0 = Hit SL. NULL = Not yet resolved.
        target_label INTEGER,   
        
        UNIQUE(asset, timestamp),
        FOREIGN KEY(asset, timestamp) REFERENCES market_data_1h(asset, timestamp)
    )
    ''')
    print("[SUCCESS] Table 'feature_store' verified.")

    # Create indexes for faster querying during ML training
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_time ON market_data_1h(asset, timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_feature_asset_time ON feature_store(asset, timestamp)')

    conn.commit()
    conn.close()
    print("[SUCCESS] Database Initialization Complete.")

if __name__ == "__main__":
    init_db()