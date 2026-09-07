import os
import time
import yaml
from typing import Dict, List, Optional
from unified_quant_bot.config.config import (
    ASSETS_YAML_PATH, MAX_RISK_PER_TRADE_PCT, MAX_CONCURRENT_POSITIONS,
    DAILY_DRAWDOWN_LIMIT_PCT, MAX_SPREAD_PCT, MIN_RRR
)

class RiskEngine:
    """
    Deterministic Fail-Closed Risk Management Engine:
    Enforces risk percentage per trade, concentration limits, spread ceilings,
    drawdown circuit breakers, and automated Penalty Box quarantines.
    """

    def __init__(self, config_path: str = ASSETS_YAML_PATH):
        self.config_path = config_path
        self.assets_config = {}
        self.active_positions = set()
        self.daily_peak_equity = None
        self.circuit_breaker_active = False
        self.penalty_box: Dict[str, float] = {
            "HBAR/USDT": time.time() + 86400, # Initial 24h freeze on severe drag asset
            "DOGE/USDT": time.time() + 43200  # Initial 12h freeze on poor performer
        }
        self.asset_recent_results: Dict[str, List[str]] = {}
        self._load_config()

    def record_trade_result(self, symbol: str, is_win: bool):
        """Records trade outcome and automatically triggers penalty box if underperforming."""
        if symbol not in self.asset_recent_results:
            self.asset_recent_results[symbol] = []
        
        res = "WIN" if is_win else "LOSS"
        self.asset_recent_results[symbol].append(res)
        self.asset_recent_results[symbol] = self.asset_recent_results[symbol][-5:] # Keep last 5

        recent = self.asset_recent_results[symbol]
        # Rule 1: 2 consecutive losses -> 4 hour quarantine
        if len(recent) >= 2 and recent[-1] == "LOSS" and recent[-2] == "LOSS":
            self.penalty_box[symbol] = time.time() + 14400 # 4 hours
            print(f"[PENALTY BOX] 🟡 {symbol} quarantined for 4 hours (2 consecutive losses).")
        # Rule 2: Win rate < 35% on >= 4 trades -> 6 hour quarantine
        elif len(recent) >= 4:
            wins = recent.count("WIN")
            if (wins / len(recent)) < 0.35:
                self.penalty_box[symbol] = time.time() + 21600 # 6 hours
                print(f"[PENALTY BOX] 🟡 {symbol} quarantined for 6 hours (Win rate {wins}/{len(recent)} < 35%).")

    def is_in_penalty_box(self, symbol: str) -> bool:
        if symbol in self.penalty_box:
            if time.time() < self.penalty_box[symbol]:
                return True
            else:
                self.penalty_box.pop(symbol, None)
        return False

    def _load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = yaml.safe_load(f)
                    self.assets_config = data.get('assets', {})
            except Exception as e:
                print(f"[RISK] Config load warning: {e}")

    def register_position(self, symbol: str):
        self.active_positions.add(symbol)

    def unregister_position(self, symbol: str):
        self.active_positions.discard(symbol)

    def check_drawdown_limit(self, current_balance: float) -> bool:
        """Evaluates daily drawdown limit from peak equity."""
        if self.daily_peak_equity is None or current_balance > self.daily_peak_equity:
            self.daily_peak_equity = current_balance

        if self.daily_peak_equity > 0:
            dd_pct = ((self.daily_peak_equity - current_balance) / self.daily_peak_equity) * 100.0
            if dd_pct >= DAILY_DRAWDOWN_LIMIT_PCT:
                self.circuit_breaker_active = True
                return False

        self.circuit_breaker_active = False
        return True

    def evaluate_order_proposal(
        self,
        symbol: str,
        direction: str,
        entry: float,
        sl: float,
        tp: float,
        balance: float,
        spread_pct: float = 0.02
    ) -> dict:
        # 0. Check Automated Penalty Box
        if self.is_in_penalty_box(symbol):
            remaining_mins = int((self.penalty_box[symbol] - time.time()) / 60)
            return {
                "eligible": False,
                "reason": f"ASSET_IN_PENALTY_BOX ({remaining_mins}m remaining)",
                "rejection_codes": ["ASSET_IN_PENALTY_BOX"]
            }
        """
        Validates signal against all deterministic risk constraints.
        """
        rejection_reasons = []

        # 1. Circuit Breaker Check
        if self.circuit_breaker_active or not self.check_drawdown_limit(balance):
            return {
                "eligible": False,
                "reason": "CIRCUIT_BREAKER_ACTIVE",
                "rejection_codes": ["DAILY_DRAWDOWN_EXCEEDED"]
            }

        # 2. Maximum Concurrent Positions
        if len(self.active_positions) >= MAX_CONCURRENT_POSITIONS:
            return {
                "eligible": False,
                "reason": "MAX_CONCURRENT_POSITIONS_REACHED",
                "rejection_codes": ["PORTFOLIO_CONCENTRATION_CAP"]
            }

        if symbol in self.active_positions:
            return {
                "eligible": False,
                "reason": "ALREADY_ACTIVE_POSITION",
                "rejection_codes": ["DUPLICATE_ASSET_EXPOSURE"]
            }

        # 3. Spread Ceilings
        if spread_pct > MAX_SPREAD_PCT:
            return {
                "eligible": False,
                "reason": "SPREAD_TOO_HIGH",
                "rejection_codes": [f"SPREAD_{spread_pct:.3f}_EXCEEDS_MAX"]
            }

        # 4. Stop Loss Validation
        sl_dist = abs(entry - sl)
        tp_dist = abs(tp - entry)
        if sl_dist <= 0 or (tp_dist / sl_dist) < (MIN_RRR - 0.05):
            return {
                "eligible": False,
                "reason": f"SUBOPTIMAL_RRR (Found {(tp_dist/sl_dist):.2f}, Expected >= {MIN_RRR:.1f})",
                "rejection_codes": [f"RRR_BELOW_MINIMUM_{MIN_RRR:.1f}"]
            }

        # 5. Asset Sizing & Risk Allocation (Supports Fractional Live Pilot Mode)
        asset_cfg = self.assets_config.get(symbol, {})
        risk_factor = float(asset_cfg.get('risk_factor', 1.0))
        risk_pct = float(os.getenv("LIVE_PILOT_RISK_PCT", str(MAX_RISK_PER_TRADE_PCT)))
        dollar_risk = balance * (risk_pct * 0.01) * risk_factor

        quantity = dollar_risk / sl_dist if sl_dist > 0 else 0.0

        # Step size truncation (safe general rounding)
        if quantity > 1.0:
            quantity = round(quantity, 2)
        else:
            quantity = round(quantity, 4)

        if (quantity * entry) < 5.0: # Binance minimum notional $5
            quantity = round(5.5 / entry, 4)

        return {
            "eligible": True,
            "quantity": quantity,
            "dollar_risk": round(dollar_risk, 2),
            "entry_price": entry,
            "sl_price": sl,
            "tp_price": tp,
            "risk_pct_used": risk_pct,
            "rejection_codes": []
        }

    def validate_meta_labeling(self, meta_result: dict) -> dict:
        """Validates secondary meta-labeling score before order dispatch."""
        if not meta_result.get("passed", True):
            return {
                "eligible": False,
                "reason": f"META_LABELING_FILTERED ({meta_result.get('meta_confidence', 0):.1f}% < 65.0%)",
                "rejection_codes": ["META_CONFIDENCE_BELOW_FLOOR"]
            }
        return {"eligible": True}
