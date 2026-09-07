import os
import sys
import pandas as pd

# Add the project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_quant_bot.features.feature_library import FeatureEngineering
from ai_quant_bot.features.label_generator import TripleBarrierLabeler
from ai_quant_bot.models.train_pipeline import ModelTrainer

def run_training_for_symbol(symbol: str, raw_ohlcv_csv: str):
    # 1. Load Data
    df = pd.read_csv(raw_ohlcv_csv, parse_dates=['timestamp']).set_index('timestamp')
    
    # 2. Extract Features
    feats = FeatureEngineering.generate_full_feature_vector(df)
    
    # 3. Apply Triple-Barrier Labels (1:1.5 RRR)
    labeled_df = TripleBarrierLabeler.generate_barriers_and_labels(
        pd.concat([df, feats], axis=1),
        tp_mult=1.5,
        sl_mult=1.0,
        horizon_bars=15
    )

    # 4. Clean Missing / Inconclusive Labels (Dropping NaNs)
    feature_cols = feats.columns.tolist()
    
    # Train Long Model
    df_long = labeled_df.dropna(subset=['target_long'])
    trainer = ModelTrainer()
    trainer.train_and_calibrate(df_long[feature_cols], df_long['target_long'], symbol, 'long')

    # Train Short Model
    df_short = labeled_df.dropna(subset=['target_short'])
    trainer.train_and_calibrate(df_short[feature_cols], df_short['target_short'], symbol, 'short')

if __name__ == '__main__':
    # Example usage:
    # run_training_for_symbol('SOL/USDT', 'data/history/SOL_USDT_1m.csv')
    pass
