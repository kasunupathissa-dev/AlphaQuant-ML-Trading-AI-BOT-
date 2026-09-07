import os
import yaml
import numpy as np

class RiskManagementEngine:
    """Production Quantitative Risk Management and Exposure Control Engine."""

    def __init__(self, assets_config_path: str = None, max_active_positions: int = 3):
        self.risk_per_trade_pct = 0.015  # Default 1.5% risk limit per setup
        self.min_rrr = 1.5              # Minimum asymmetric RRR
        self.max_active_positions = max_active_positions
        self.active_assets = set()
        self.risk_multipliers = {}

        if assets_config_path and os.path.exists(assets_config_path):
            try:
                with open(assets_config_path, 'r') as f:
                    config_data = yaml.safe_load(f) or {}
                    for symbol, settings in config_data.items():
                        self.risk_multipliers[symbol] = settings.get('risk_factor', 1.0)
            except Exception as e:
                print(f"[WARNING] RiskManager failed to load assets config: {e}")

    def register_active_trade(self, symbol: str):
        """Registers a symbol as having an active position."""
        self.active_assets.add(symbol.upper().strip())

    def unregister_active_trade(self, symbol: str):
        """Unregisters a symbol when position is closed."""
        self.active_assets.discard(symbol.upper().strip())

    def evaluate_order_proposal(
        self,
        symbol: str,
        direction: str,
        entry: float,
        atr: float,
        balance: float,
        regime: str,
        market_info: dict = None
    ) -> dict:
        """
        Audits order proposal against RRR, duplicate symbols, exposure limits, 
        and calculates normalized position sizing contracts.
        """
        symbol_norm = symbol.upper().strip()
        
        # 1. Zero NaN & Value Validations
        assert entry > 0, "Entry price must be positive."
        assert atr > 0, "ATR value must be positive."
        assert balance > 0, "Account equity balance must be positive."
        assert direction in ("LONG", "SHORT"), "Direction must be LONG or SHORT."

        # 2. Enforce Duplicate Asset & Exposure Limits
        if symbol_norm in self.active_assets:
            return {'eligible': False, 'reason': f"Duplicate active trade detected for {symbol_norm}"}

        if len(self.active_assets) >= self.max_active_positions:
            return {'eligible': False, 'reason': f"Max concurrent position limit ({self.max_active_positions}) reached"}

        # 3. Calculate Stop-Loss & Take-Profit prices using ATR
        sl_mult = 1.0
        tp_mult = 1.5
        
        if direction == "LONG":
            sl = entry - (sl_mult * atr)
            tp = entry + (tp_mult * atr)
        else:
            sl = entry + (sl_mult * atr)
            tp = entry - (tp_mult * atr)

        sl_dist = abs(entry - sl)
        tp_dist = abs(tp - entry)
        
        # 4. Enforce strict Risk-to-Reward Ratio (RRR)
        rrr = tp_dist / sl_dist
        if round(rrr, 4) < self.min_rrr:
            return {'eligible': False, 'reason': f"RRR {rrr:.2f} below minimum requirement {self.min_rrr}"}

        # 5. Position Sizing based on fixed 1.5% account equity loss
        base_risk_usd = balance * self.risk_per_trade_pct
        asset_multiplier = self.risk_multipliers.get(symbol_norm, 1.0)
        target_risk_usd = base_risk_usd * asset_multiplier
        
        # Position Size Formula: Risk_USD / SL_Distance * Entry
        position_notional = (target_risk_usd / sl_dist) * entry
        
        # 6. Regime Scaling: scale down by 50% in CHOPPY market
        if regime == "CHOPPY":
            position_notional *= 0.5
            target_risk_usd *= 0.5

        # 7. Normalize quantity to exchange lot sizes & min notional limit
        raw_qty = position_notional / entry
        normalized_qty = raw_qty
        
        if market_info:
            precision_amount = market_info.get('precision', {}).get('amount')
            limits_amount = market_info.get('limits', {}).get('amount', {})
            limits_cost = market_info.get('limits', {}).get('cost', {})
            
            # Normalize to lot step size
            if precision_amount is not None:
                normalized_qty = np.round(raw_qty / precision_amount) * precision_amount
                
            # Enforce lot limits
            min_qty = limits_amount.get('min')
            max_qty = limits_amount.get('max')
            if min_qty is not None and normalized_qty < min_qty:
                normalized_qty = min_qty
            if max_qty is not None and normalized_qty > max_qty:
                normalized_qty = max_qty
                
            # Enforce minimum cost (notional)
            min_cost = limits_cost.get('min')
            if min_cost is not None and (normalized_qty * entry) < min_cost:
                return {'eligible': False, 'reason': f"Position notional ${(normalized_qty * entry):.2f} below min exchange limit ${min_cost}"}

        # Final calculated size in notional value
        final_notional = normalized_qty * entry
        
        return {
            'eligible': True,
            'sl_price': sl,
            'tp_price': tp,
            'quantity': float(normalized_qty),
            'notional_usd': float(final_notional),
            'risk_usd': float(target_risk_usd),
            'reason': 'Setup passes quantitative risk audit'
        }
