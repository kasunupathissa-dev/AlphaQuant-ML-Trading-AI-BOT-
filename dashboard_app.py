import http.server
import socketserver
import json
import os
import csv
import sys
from datetime import datetime
import ccxt

# 🟢 V8.5 Upgrade: Import config and zoneinfo for Stockholm timezone handling
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

def format_timestamp_stockholm(ts):
    """Formats a unix timestamp into Stockholm timezone."""
    tz_name = getattr(config, 'TIMEZONE', 'Europe/Stockholm')
    if ZoneInfo is not None:
        try:
            return datetime.fromtimestamp(ts, ZoneInfo(tz_name)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    # Fallback: manually offset to Stockholm summer time (UTC+2)
    from datetime import timezone, timedelta
    utc_dt = datetime.fromtimestamp(ts, timezone.utc).replace(tzinfo=None)
    return (utc_dt + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")

PORT = 8080
if len(sys.argv) > 1:
    try:
        PORT = int(sys.argv[1])
    except ValueError:
        pass

STATE_FILE = "live_engine_state.json"
LOG_FILE = "trading_log_v8.csv"
TEMPLATES_DIR = "templates"

class DashboardHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence default logger to keep terminal output clean
        pass

    def send_json(self, data, status=200):
        try:
            response_bytes = json.dumps(data).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(response_bytes)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response_bytes)
        except Exception as e:
            print(f"[ERROR] Failed to send JSON: {e}")

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # 1. API Endpoint: State
        if path == '/api/state':
            if os.path.exists(STATE_FILE):
                try:
                    with open(STATE_FILE, 'r') as f:
                        state_data = json.load(f)
                    # Check if bot is active (state file modified within last 2 minutes)
                    last_mod = os.path.getmtime(STATE_FILE)
                    is_active = (datetime.now().timestamp() - last_mod) < 120
                    state_data["is_active"] = is_active
                    state_data["last_update"] = format_timestamp_stockholm(last_mod)
                    
                    # 🟢 V8.5 Upgrade: Automatically prune expired assets from penalty box before sending to frontend
                    pb = state_data.get("asset_penalty_box", {})
                    current_time = datetime.now().timestamp()
                    pruned_pb = {k: v for k, v in pb.items() if v > current_time}
                    state_data["asset_penalty_box"] = pruned_pb
                    
                    self.send_json(state_data)
                except Exception as e:
                    self.send_json({"error": f"Failed to load state: {str(e)}"}, 500)
            else:
                self.send_json({
                    "is_active": False,
                    "active_trades": [],
                    "asset_penalty_box": {},
                    "asset_recent_results": {},
                    "error": "State file not found. Bot may not be running."
                })

        # 2. API Endpoint: Trades Log
        elif path == '/api/trades':
            trades = []
            if os.path.exists(LOG_FILE):
                try:
                    with open(LOG_FILE, mode='r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            # Normalize keys to lowercase
                            row = {k.lower(): v for k, v in row.items() if k is not None}
                            # Map aliases
                            if 'ai_prob' in row:
                                row['win_prob'] = row['ai_prob']
                                
                            # Convert numerical fields
                            try:
                                if 'entry' in row and row['entry']: row['entry'] = float(row['entry'])
                                if 'sl' in row and row['sl']: row['sl'] = float(row['sl'])
                                if 'tp' in row and row['tp']: row['tp'] = float(row['tp'])
                                if 'win_prob' in row and row['win_prob']:
                                    prob_str = str(row['win_prob']).replace('%', '').strip()
                                    row['win_prob'] = float(prob_str) if prob_str else 0.0
                                if 'pnl' in row and row['pnl']: row['pnl'] = float(row['pnl'])
                                if 'exit_price' in row and row['exit_price']:
                                    row['exit_price'] = float(row['exit_price'])
                            except ValueError:
                                pass
                            trades.append(row)
                    # Return latest 250 trades
                    self.send_json(trades[::-1][:250])
                except Exception as e:
                    self.send_json({"error": f"Failed to read logs: {str(e)}"}, 500)
            else:
                self.send_json([])

        # 3. API Endpoint: Statistical Report
        elif path == '/api/stats':
            stats = {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "long_win_rate": 0.0,
                "short_win_rate": 0.0,
                "long_trades": 0,
                "short_trades": 0,
                "total_pnl": 0.0,
                "total_fees": 0.0,
                "net_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "sharpe": 0.0,
                "sortino": 0.0,
                "max_drawdown_pct": 0.0,
                "max_drawdown_dollars": 0.0,
                "current_drawdown_pct": 0.0,
                "overall_brier": 0.0,
                "rolling_brier": [],
                "hourly_performance": {},
                "weekly_performance": {},
                "signal_performance": {},
                "asset_breakdown": {}
            }
            
            if os.path.exists(LOG_FILE):
                try:
                    trades_list = []
                    
                    with open(LOG_FILE, mode='r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            row = {k.lower(): v for k, v in row.items() if k is not None}
                            try:
                                pnl = float(row.get('pnl', 0.0))
                                status = row.get('status', 'LOSS').upper()
                                asset = row.get('asset', 'UNKNOWN')
                                entry = float(row.get('entry', 0.0))
                                sl = float(row.get('sl', 0.0))
                                win_prob = float(str(row.get('win_prob', '0')).replace('%', '').strip())
                                sig_type = row.get('signaltype', 'TREND').upper()
                                direction = row.get('direction', 'LONG').upper()
                                timestamp = row.get('timestamp', '')
                                
                                is_win = "PROFIT" in status or "WIN" in status
                                
                                # Estimate position size: risk / SL distance * entry
                                sl_dist = abs(entry - sl)
                                psize = (10.0 / sl_dist) * entry if sl_dist > 1e-6 else 0.0
                                estimated_fee = psize * getattr(config, 'ESTIMATED_FEE_PCT', 0.0008)
                                net_pnl_val = pnl - estimated_fee
                                
                                trades_list.append({
                                    "asset": asset,
                                    "direction": direction,
                                    "pnl": pnl,
                                    "net_pnl": net_pnl_val,
                                    "is_win": is_win,
                                    "win_prob": win_prob,
                                    "position_size": psize,
                                    "fee": estimated_fee,
                                    "signal_type": sig_type,
                                    "timestamp": timestamp
                                })
                            except Exception:
                                continue
                                
                    total_trades = len(trades_list)
                    if total_trades > 0:
                        stats["total_trades"] = total_trades
                        
                        pnl_vals = [t["pnl"] for t in trades_list]
                        net_pnl_vals = [t["net_pnl"] for t in trades_list]
                        wins_list = [t["pnl"] for t in trades_list if t["is_win"]]
                        losses_list = [t["pnl"] for t in trades_list if not t["is_win"]]
                        
                        stats["wins"] = len(wins_list)
                        stats["losses"] = len(losses_list)
                        stats["win_rate"] = round((stats["wins"] / total_trades) * 100, 2)
                        
                        # 🟢 V8.5 Upgrade: Direction-wise Win Rate calculations (LONG vs SHORT split)
                        long_trades = [t for t in trades_list if t["direction"] == "LONG"]
                        short_trades = [t for t in trades_list if t["direction"] == "SHORT"]
                        long_wins = [t for t in long_trades if t["is_win"]]
                        short_wins = [t for t in short_trades if t["is_win"]]
                        
                        stats["long_trades"] = len(long_trades)
                        stats["short_trades"] = len(short_trades)
                        stats["long_win_rate"] = round((len(long_wins) / len(long_trades)) * 100, 2) if long_trades else 0.0
                        stats["short_win_rate"] = round((len(short_wins) / len(short_trades)) * 100, 2) if short_trades else 0.0
                        stats["total_pnl"] = round(sum(pnl_vals), 4)
                        stats["total_fees"] = round(sum(t["fee"] for t in trades_list), 4)
                        stats["net_pnl"] = round(stats["total_pnl"] - stats["total_fees"], 4)
                        
                        if wins_list:
                            stats["avg_win"] = round(sum(wins_list) / len(wins_list), 4)
                        if losses_list:
                            stats["avg_loss"] = round(sum(losses_list) / len(losses_list), 4)
                            
                        sum_wins = sum(wins_list)
                        sum_losses = abs(sum(losses_list))
                        stats["profit_factor"] = round(sum_wins / sum_losses, 2) if sum_losses > 0 else (round(sum_wins, 2) if sum_wins > 0 else 0.0)
                        
                        # 🟢 Sharpe & Sortino computations
                        net_returns = []
                        for t in trades_list:
                            if t["position_size"] > 0:
                                net_returns.append(t["net_pnl"] / t["position_size"])
                            else:
                                net_returns.append(0.0)
                                
                        def std_dev(lst):
                            if len(lst) < 2: return 0.0
                            mean = sum(lst) / len(lst)
                            variance = sum((x - mean) ** 2 for x in lst) / (len(lst) - 1)
                            return variance ** 0.5
                            
                        mean_ret = sum(net_returns) / len(net_returns)
                        std_ret = std_dev(net_returns)
                        stats["sharpe"] = round(mean_ret / std_ret, 4) if std_ret > 0 else 0.0
                        
                        downside_rets = [r for r in net_returns if r < 0]
                        std_downside = std_dev(downside_rets)
                        stats["sortino"] = round(mean_ret / std_downside, 4) if std_downside > 0 else 0.0
                        
                        # 🟢 Drawdown calculations
                        initial_balance = 10000.0
                        current_equity = initial_balance
                        peak = initial_balance
                        max_dd_dollars = 0.0
                        max_dd_pct = 0.0
                        
                        for t in trades_list:
                            current_equity += t["net_pnl"]
                            if current_equity > peak:
                                peak = current_equity
                            dd_dollars = peak - current_equity
                            dd_pct = (dd_dollars / peak) * 100.0
                            if dd_pct > max_dd_pct:
                                max_dd_pct = dd_pct
                                max_dd_dollars = dd_dollars
                                
                        stats["max_drawdown_pct"] = round(max_dd_pct, 2)
                        stats["max_drawdown_dollars"] = round(max_dd_dollars, 2)
                        stats["current_drawdown_pct"] = round(((peak - current_equity) / peak) * 100.0, 2)
                        
                        # 🟢 Calibration & Brier Score
                        sq_errors = []
                        for t in trades_list:
                            label = 1 if t["is_win"] else 0
                            p = t["win_prob"] / 100.0
                            sq_errors.append((p - label) ** 2)
                        stats["overall_brier"] = round(sum(sq_errors) / len(sq_errors), 4) if sq_errors else 0.0
                        
                        # Rolling Brier Score (window = 15)
                        window = 15
                        rolling_brier = []
                        for k in range(len(trades_list)):
                            if k >= window - 1:
                                sub = trades_list[k - window + 1:k + 1]
                                errors = [(t["win_prob"]/100.0 - (1 if t["is_win"] else 0))**2 for t in sub]
                                rolling_brier.append({"trade_index": k + 1, "brier": round(sum(errors)/len(errors), 4)})
                        stats["rolling_brier"] = rolling_brier
                        
                        # 🟢 Time-based analytics
                        hourly_perf = {h: {"trades": 0, "wins": 0, "pnl": 0.0, "win_rate": 0.0} for h in range(24)}
                        weekly_perf = {d: {"trades": 0, "wins": 0, "pnl": 0.0, "win_rate": 0.0} for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}
                        
                        for t in trades_list:
                            try:
                                dt = datetime.strptime(t["timestamp"], "%Y-%m-%d %H:%M:%S")
                                h = dt.hour
                                d = dt.strftime("%A")
                                if h in hourly_perf:
                                    hourly_perf[h]["trades"] += 1
                                    hourly_perf[h]["pnl"] += t["net_pnl"]
                                    if t["is_win"]: hourly_perf[h]["wins"] += 1
                                if d in weekly_perf:
                                    weekly_perf[d]["trades"] += 1
                                    weekly_perf[d]["pnl"] += t["net_pnl"]
                                    if t["is_win"]: weekly_perf[d]["wins"] += 1
                            except Exception:
                                pass
                                
                        for h in hourly_perf:
                            tc = hourly_perf[h]["trades"]
                            hourly_perf[h]["win_rate"] = round((hourly_perf[h]["wins"] / tc) * 100, 2) if tc > 0 else 0.0
                            hourly_perf[h]["pnl"] = round(hourly_perf[h]["pnl"], 4)
                        for d in weekly_perf:
                            tc = weekly_perf[d]["trades"]
                            weekly_perf[d]["win_rate"] = round((weekly_perf[d]["wins"] / tc) * 100, 2) if tc > 0 else 0.0
                            weekly_perf[d]["pnl"] = round(weekly_perf[d]["pnl"], 4)
                            
                        stats["hourly_performance"] = hourly_perf
                        stats["weekly_performance"] = weekly_perf
                        
                        # 🟢 Signal Performance
                        signal_perf = {
                            "TREND": {"trades": 0, "wins": 0, "pnl": 0.0, "win_rate": 0.0},
                            "REVERSION": {"trades": 0, "wins": 0, "pnl": 0.0, "win_rate": 0.0}
                        }
                        for t in trades_list:
                            st = t["signal_type"]
                            if st not in ("TREND", "REVERSION"):
                                st = "TREND"
                            signal_perf[st]["trades"] += 1
                            signal_perf[st]["pnl"] += t["net_pnl"]
                            if t["is_win"]: signal_perf[st]["wins"] += 1
                            
                        for st in signal_perf:
                            tc = signal_perf[st]["trades"]
                            signal_perf[st]["win_rate"] = round((signal_perf[st]["wins"] / tc) * 100, 2) if tc > 0 else 0.0
                            signal_perf[st]["pnl"] = round(signal_perf[st]["pnl"], 4)
                        stats["signal_performance"] = signal_perf
                        
                        # 🟢 Asset breakdown
                        asset_data = {}
                        for t in trades_list:
                            asset = t["asset"]
                            if asset not in asset_data:
                                asset_data[asset] = {"trades": 0, "wins": 0, "pnl": 0.0, "win_rate": 0.0}
                            asset_data[asset]["trades"] += 1
                            asset_data[asset]["pnl"] += t["net_pnl"]
                            if t["is_win"]: asset_data[asset]["wins"] += 1
                            
                        for asset, d in asset_data.items():
                            d["win_rate"] = round((d["wins"] / d["trades"]) * 100, 2) if d["trades"] > 0 else 0.0
                            d["pnl"] = round(d["pnl"], 4)
                        stats["asset_breakdown"] = asset_data
                        
                    self.send_json(stats)
                except Exception as e:
                    self.send_json({"error": f"Failed to compute statistics: {str(e)}"}, 500)
            else:
                self.send_json(stats)

        # 🟢 V8.5 API Endpoint: Calibration reliability curves
        elif path == '/api/calibration':
            if os.path.exists("model_metadata.json"):
                try:
                    with open("model_metadata.json", 'r') as f:
                        meta = json.load(f)
                    self.send_json(meta)
                except Exception as e:
                    self.send_json({"error": f"Failed to load calibration data: {str(e)}"}, 500)
        # 🟢 V8.5 API Endpoint: Export Report
        elif path == '/api/export':
            try:
                query_params = parse_qs(parsed_path.query)
                asset_filter = query_params.get('asset', [None])[0]
                
                if os.path.exists(LOG_FILE):
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/csv')
                    
                    if asset_filter:
                        filename = f"{asset_filter.replace('/', '_')}_log.csv"
                    else:
                        filename = "trading_log_v8.csv"
                        
                    self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    
                    with open(LOG_FILE, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    if asset_filter:
                        lines = content.split('\n')
                        header = lines[0]
                        filtered_lines = [header]
                        for line in lines[1:]:
                            if asset_filter in line:
                                filtered_lines.append(line)
                        self.wfile.write('\n'.join(filtered_lines).encode('utf-8'))
                    else:
                        self.wfile.write(content.encode('utf-8'))
                else:
                    self.send_json({"error": "No log file found."}, 404)
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        # 4. Static Page: index.html
        elif path in ('/', '/index.html'):
            html_path = os.path.join(TEMPLATES_DIR, "index.html")
            if os.path.exists(html_path):
                try:
                    with open(html_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Length', str(len(content.encode('utf-8'))))
                    self.end_headers()
                    self.wfile.write(content.encode('utf-8'))
                except Exception as e:
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(f"Error loading template: {str(e)}".encode('utf-8'))
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Dashboard index.html template not found.")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        if self.path == '/api/config':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                req_data = json.loads(post_data.decode('utf-8'))
                
                # Load existing state
                state_data = {}
                if os.path.exists(STATE_FILE):
                    with open(STATE_FILE, 'r') as f:
                        state_data = json.load(f)
                
                updated = False
                
                # 1. Update trade mode if passed
                if "trade_mode" in req_data:
                    mode = req_data["trade_mode"].upper()
                    if mode in ["BOTH", "LONG_ONLY", "SHORT_ONLY", "OFF"]:
                        state_data["trade_mode"] = mode
                        updated = True
                
                # 2. Release asset from penalty box if passed
                if "unfreeze_asset" in req_data:
                    asset = req_data["unfreeze_asset"]
                    pb = state_data.get("asset_penalty_box", {})
                    if asset in pb:
                        del pb[asset]
                        state_data["asset_penalty_box"] = pb
                        updated = True
                        
                # 3. Force close a specific position if passed
                if "close_trade" in req_data:
                    asset = req_data["close_trade"]
                    send_to_penalty = req_data.get("send_to_penalty", False)
                    trades = state_data.get("active_trades", [])
                    
                    target_trade = next((t for t in trades if t["asset"] == asset), None)
                    if target_trade:
                        # Calculate realized P&L based on last known price
                        live_prices = state_data.get("live_prices", {})
                        current_price = live_prices.get(asset, target_trade.get("entry", 0.0))
                        
                        entry = target_trade.get("entry", 0.0)
                        pos_size = target_trade.get("position_size", 100.0)
                        locked_pnl = target_trade.get("locked_pnl", 0.0)
                        
                        if target_trade.get("direction", "LONG").upper() == "LONG":
                            remaining_pnl = pos_size * ((current_price - entry) / entry) if entry > 0 else 0.0
                        else:
                            remaining_pnl = pos_size * ((entry - current_price) / entry) if entry > 0 else 0.0
                            
                        realized_pnl = locked_pnl + remaining_pnl
                        
                        # Log to CSV file
                        try:
                            file_exists = os.path.isfile(LOG_FILE)
                            with open(LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
                                writer = csv.writer(f)
                                if not file_exists:
                                    writer.writerow(["Timestamp", "Asset", "Direction", "Entry", "TP", "SL", "Status", "AI_Prob", "PNL", "SignalType"])
                                
                                result = "PROFIT" if realized_pnl >= 0 else "LOSS"
                                ai_prob_str = f"{target_trade.get('ai_prob', 50.0):.2f}%"
                                timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                writer.writerow([
                                    timestamp_str,
                                    target_trade["asset"],
                                    target_trade["direction"],
                                    f"{target_trade['entry']:.4f}",
                                    f"{target_trade['tp']:.4f}",
                                    f"{target_trade['sl']:.4f}",
                                    result,
                                    ai_prob_str,
                                    f"{realized_pnl:.2f}",
                                    target_trade.get("signal_type", "SHOTGUN")
                                ])
                            print(f"[API] Manual close log written for {asset}. Realized P&L: ${realized_pnl:.2f}")
                        except Exception as csv_err:
                            print(f"[ERROR] Failed to log manually closed trade to CSV: {csv_err}")
                            
                        # Execute Testnet order on exit (opposite direction) if enabled
                        if getattr(config, 'USE_TESTNET', False) and getattr(config, 'BINANCE_API_KEY', ''):
                            try:
                                exchange = ccxt.binance({
                                    'apiKey': getattr(config, 'BINANCE_API_KEY', ''),
                                    'secret': getattr(config, 'BINANCE_API_SECRET', ''),
                                    'enableRateLimit': True,
                                    'options': {
                                        'defaultType': 'future'
                                    }
                                })
                                exchange.set_sandbox_mode(True)
                                
                                exit_direction = 'SHORT' if target_trade.get('direction', 'LONG').upper() == 'LONG' else 'LONG'
                                side = 'buy' if exit_direction == 'LONG' else 'sell'
                                amount = pos_size / entry if entry > 0 else 0.0
                                
                                if amount > 0:
                                    order = exchange.create_market_order(
                                        symbol=asset,
                                        side=side,
                                        amount=amount
                                    )
                                    print(f"[API TESTNET] Force closed position for {asset} on Testnet. Order ID: {order.get('id')}")
                            except Exception as testnet_err:
                                print(f"[ERROR] Failed to place manual close order on Testnet for {asset}: {testnet_err}")
                    
                    state_data["active_trades"] = [t for t in trades if t["asset"] != asset]
                    
                    # Also freeze the asset in the penalty box for 24h if explicitly requested
                    if send_to_penalty:
                        pb = state_data.get("asset_penalty_box", {})
                        pb[asset] = datetime.now().timestamp() + (24 * 3600)
                        state_data["asset_penalty_box"] = pb
                        
                    updated = True
                    
                # 4. Update configuration settings settings block if passed
                if "settings" in req_data:
                    state_data["settings"] = req_data["settings"]
                    updated = True
                        
                if updated:
                    with open(STATE_FILE, 'w') as f:
                        json.dump(state_data, f, indent=4)
                    print(f"[API] Updated config in state file: {req_data}")
                    
                self.send_json({"status": "success", "state": state_data})
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, 400)
        elif self.path == '/api/retrain':
            try:
                import subprocess
                subprocess.Popen([sys.executable, "model_training_v7.py"])
                self.send_json({"status": "success", "message": "Retraining started in the background."})
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, 500)
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    pass

if __name__ == '__main__':
    # Ensure templates directory exists
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    
    server_address = ('', PORT)
    httpd = ThreadedHTTPServer(server_address, DashboardHTTPRequestHandler)
    print(f"[SUCCESS] AlphaQuant Web Dashboard active on http://localhost:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dashboard server...")
        httpd.shutdown()
        sys.exit(0)
