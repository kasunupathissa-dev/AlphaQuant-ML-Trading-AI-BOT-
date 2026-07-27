import http.server
import socketserver
import json
import os
import csv
import sys
from datetime import datetime

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
        # 1. API Endpoint: State
        if self.path == '/api/state':
            if os.path.exists(STATE_FILE):
                try:
                    with open(STATE_FILE, 'r') as f:
                        state_data = json.load(f)
                    # Check if bot is active (state file modified within last 2 minutes)
                    last_mod = os.path.getmtime(STATE_FILE)
                    is_active = (datetime.now().timestamp() - last_mod) < 120
                    state_data["is_active"] = is_active
                    state_data["last_update"] = datetime.fromtimestamp(last_mod).strftime("%Y-%m-%d %H:%M:%S")
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
        elif self.path == '/api/trades':
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
        elif self.path == '/api/stats':
            stats = {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "asset_breakdown": {}
            }
            
            if os.path.exists(LOG_FILE):
                try:
                    pnl_list = []
                    wins_list = []
                    losses_list = []
                    asset_data = {}
                    
                    with open(LOG_FILE, mode='r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            row = {k.lower(): v for k, v in row.items() if k is not None}
                            try:
                                pnl = float(row.get('pnl', 0.0))
                                status = row.get('status', 'LOSS').upper()
                                asset = row.get('asset', 'UNKNOWN')
                                
                                stats["total_trades"] += 1
                                stats["total_pnl"] += pnl
                                pnl_list.append(pnl)
                                
                                if "WIN" in status:
                                    stats["wins"] += 1
                                    wins_list.append(pnl)
                                else:
                                    stats["losses"] += 1
                                    losses_list.append(pnl)
                                    
                                # Asset Breakdown
                                if asset not in asset_data:
                                    asset_data[asset] = {"trades": 0, "wins": 0, "pnl": 0.0}
                                asset_data[asset]["trades"] += 1
                                asset_data[asset]["pnl"] += pnl
                                if "WIN" in status:
                                    asset_data[asset]["wins"] += 1
                                    
                            except (ValueError, KeyError):
                                continue
                                
                    if stats["total_trades"] > 0:
                        stats["win_rate"] = round((stats["wins"] / stats["total_trades"]) * 100, 2)
                        
                    if wins_list:
                        stats["avg_win"] = round(sum(wins_list) / len(wins_list), 4)
                    if losses_list:
                        stats["avg_loss"] = round(sum(losses_list) / len(losses_list), 4)
                        
                    sum_wins = sum(wins_list)
                    sum_losses = abs(sum(losses_list))
                    stats["profit_factor"] = round(sum_wins / sum_losses, 2) if sum_losses > 0 else (round(sum_wins, 2) if sum_wins > 0 else 0.0)
                    
                    for asset, d in asset_data.items():
                        d["win_rate"] = round((d["wins"] / d["trades"]) * 100, 2) if d["trades"] > 0 else 0.0
                        d["pnl"] = round(d["pnl"], 4)
                    stats["asset_breakdown"] = asset_data
                    
                    self.send_json(stats)
                except Exception as e:
                    self.send_json({"error": f"Failed to compute statistics: {str(e)}"}, 500)
            else:
                self.send_json(stats)

        # 4. Static Page: index.html
        elif self.path in ('/', '/index.html'):
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
