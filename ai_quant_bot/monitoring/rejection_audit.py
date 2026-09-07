import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update
from ai_quant_bot.data.database import AsyncSessionLocal, SignalRejection

async def audit_rejection(
    symbol: str,
    direction: str,
    win_prob: float,
    threshold: float,
    regime: str,
    reason: str,
    entry: float = None,
    sl: float = None,
    tp: float = None
):
    """Logs rejected signal proposals with entry/sl/tp bounds to PostgreSQL database."""
    try:
        async with AsyncSessionLocal() as session:
            rejection = SignalRejection(
                timestamp=datetime.now(timezone.utc),
                symbol=symbol,
                direction=direction,
                win_prob=win_prob,
                threshold=threshold,
                regime=regime,
                reason=reason,
                entry_price=entry,
                sl_price=sl,
                tp_price=tp,
                status="PENDING"
            )
            session.add(rejection)
            await session.commit()
            print(f"[REJECTION AUDIT] Logged setup filtration: {symbol} {direction} (win_prob: {win_prob:.2f}%)")
    except Exception as e:
        print(f"[ERROR] Failed to log signal rejection: {e}")

async def monitor_rejected_signals(current_prices: dict):
    """
    Asynchronously queries all pending signal rejections and updates their outcomes 
    if they touch hypothetical take-profit or stop-loss bounds.
    """
    try:
        async with AsyncSessionLocal() as session:
            # Query all pending rejections
            stmt = select(SignalRejection).where(SignalRejection.status == "PENDING")
            res = await session.execute(stmt)
            pending_list = res.scalars().all()
            
            now_utc = datetime.now(timezone.utc)
            
            for rej in pending_list:
                symbol = rej.symbol
                cur_price = current_prices.get(symbol)
                if cur_price is None or rej.entry_price is None:
                    continue
                
                # Check for expiration after 15 minutes (horizon_bars = 15)
                age_limit = rej.timestamp + timedelta(minutes=15)
                if now_utc > age_limit:
                    rej.status = "EXPIRED"
                    continue
                
                direction = rej.direction
                tp = float(rej.tp_price)
                sl = float(rej.sl_price)
                
                # Evaluate barrier touching
                if direction == "LONG":
                    if cur_price >= tp:
                        rej.status = "HIT_TP"
                    elif cur_price <= sl:
                        rej.status = "HIT_SL"
                else: # SHORT
                    if cur_price <= tp:
                        rej.status = "HIT_TP"
                    elif cur_price >= sl:
                        rej.status = "HIT_SL"
                        
            await session.commit()
    except Exception as e:
        print(f"[ERROR] Failed to monitor rejected signals: {e}")

async def calculate_missed_expected_value(risk_per_trade_usd: float = 5.0) -> dict:
    """
    Computes hourly/daily missed Expected Value (+EV) metrics from resolved 
    rejection barriers to monitor model calibration drift.
    """
    try:
        async with AsyncSessionLocal() as session:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            stmt = select(SignalRejection).where(
                (SignalRejection.status.in_(["HIT_TP", "HIT_SL"])) &
                (SignalRejection.timestamp >= cutoff)
            )
            res = await session.execute(stmt)
            resolved_list = res.scalars().all()
            
            tps = sum(1 for r in resolved_list if r.status == "HIT_TP")
            sls = sum(1 for r in resolved_list if r.status == "HIT_SL")
            total = len(resolved_list)
            
            # EV Formula: (Hit_TP * 1.5 - Hit_SL * 1.0) * Risk_USD
            missed_ev = (tps * 1.5 - sls * 1.0) * risk_per_trade_usd
            
            return {
                'total_resolved_rejections': total,
                'hit_tp_count': tps,
                'hit_sl_count': sls,
                'missed_ev_usd': missed_ev,
                'rejections_win_rate': (tps / total * 100.0) if total > 0 else 0.0
            }
    except Exception as e:
        print(f"[ERROR] Failed to compute missed Expected Value: {e}")
        return {'total_resolved_rejections': 0, 'hit_tp_count': 0, 'hit_sl_count': 0, 'missed_ev_usd': 0.0, 'rejections_win_rate': 0.0}

async def check_calibration_drift(notifier):
    """
    Checks if resolved signal rejections for any asset show an empirical win rate > 60% over 20+ signals.
    Dispatches a warning recommendation to Telegram if drift is identified.
    """
    try:
        async with AsyncSessionLocal() as session:
            # Query resolved rejections (HIT_TP or HIT_SL)
            stmt = select(SignalRejection).where(SignalRejection.status.in_(["HIT_TP", "HIT_SL"]))
            res = await session.execute(stmt)
            all_resolved = res.scalars().all()
            
            # Group by symbol
            symbol_groups = {}
            for r in all_resolved:
                symbol_groups.setdefault(r.symbol, []).append(r)
                
            for symbol, rejs in symbol_groups.items():
                # Take last 30 resolved signals for drift check
                rejs = sorted(rejs, key=lambda x: x.timestamp)[-30:]
                total = len(rejs)
                if total >= 20:
                    tps = sum(1 for r in rejs if r.status == "HIT_TP")
                    win_rate = (tps / total) * 100.0
                    
                    if win_rate > 60.0:
                        msg = (
                            f"⚠️ *[CALIBRATION DRIFT WARNING]*\n"
                            f"• *Asset*: `{symbol}`\n"
                            f"• *Win Rate of Rejected Signals*: `{win_rate:.2f}%`\n"
                            f"• *Sample Size*: `{total}` signals\n\n"
                            f"💡 *Recommendation*: Calibrated win probabilities are under-estimating true outcomes. "
                            f"Recalibrate the baseline model confidence threshold down for `{symbol}`."
                        )
                        await notifier.send_message(msg)
                        print(f"[DRIFT AUDIT] Triggered drift warning alert for {symbol} (Win Rate: {win_rate:.2f}%)")
    except Exception as e:
        print(f"[ERROR] Calibration drift check failed: {e}")
