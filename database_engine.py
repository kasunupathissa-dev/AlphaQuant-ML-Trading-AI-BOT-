import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

# 🟢 V4.0: Local SQLite Database for ML Feature Storage
DB_PATH = "sqlite:///alphaquant_v4.db"

engine = create_engine(DB_PATH, echo=False)
Base = declarative_base()

class TradeFeatureStore(Base):
    """
    This table stores the exact state of all technical and SMC features 
    at the EXACT moment a signal was generated. This is required for XGBoost training.
    """
    __tablename__ = 'trade_feature_store'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    asset = Column(String)
    
    # Target Variable (What the ML model will try to predict)
    # 1 = Hit TP (Win), 0 = Hit SL (Loss), -1 = Pending
    target_result = Column(Integer, default=-1) 
    
    # 🟢 Raw Market Features
    entry_price = Column(Float)
    direction = Column(String)
    regime = Column(String)
    volatility_atr_pct = Column(Float)
    
    # 🟢 Technical Features
    ema_50_dist_pct = Column(Float)
    ema_200_4h_dist_pct = Column(Float)
    vwap_dist_pct = Column(Float)
    
    # 🟢 SMC Features
    fvg_type = Column(String)
    fvg_tap = Column(Boolean)
    
    # 🟢 Order Flow Features
    ob_imbalance_ratio = Column(Float)
    delta_volume = Column(String)
    
    # 🟢 Institutional Features
    funding_rate = Column(Float)
    btc_5m_momentum = Column(String)
    
    # The heuristic score V3.1 used (for baseline comparison)
    legacy_confidence_score = Column(Float)

# Create tables
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def save_features_to_db(feature_dict):
    """Saves a row of features to the DB when a trade opens."""
    session = Session()
    try:
        new_row = TradeFeatureStore(**feature_dict)
        session.add(new_row)
        session.commit()
        return new_row.id
    except Exception as e:
        print(f"[DB ERROR] Failed to save features: {e}")
        session.rollback()
        return None
    finally:
        session.close()

def update_trade_result(trade_id, is_win):
    """Updates the target_result column when a trade closes (for ML training)."""
    session = Session()
    try:
        trade = session.query(TradeFeatureStore).filter_by(id=trade_id).first()
        if trade:
            trade.target_result = 1 if is_win else 0
            session.commit()
    except Exception as e:
        print(f"[DB ERROR] Failed to update result: {e}")
        session.rollback()
    finally:
        session.close()
