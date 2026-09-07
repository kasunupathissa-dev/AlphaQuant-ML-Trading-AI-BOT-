import re
import ccxt

def verify():
    try:
        service_content = open('/etc/systemd/system/aq-scalper-hunt.service').read()
        
        key_match = re.search(r'Environment=BINANCE_API_KEY=(.*)', service_content)
        secret_match = re.search(r'Environment=BINANCE_API_SECRET=(.*)', service_content)
        
        if not key_match or not secret_match:
            print("[ERROR] API Key or Secret not found in systemd service file!")
            return
            
        key = key_match.group(1).strip()
        secret = secret_match.group(1).strip()
        
        # Test connection
        exchange = ccxt.binance({
            'apiKey': key,
            'secret': secret,
            'options': {'defaultType': 'future'}
        })
        
        balance = exchange.fetch_balance()
        usdt_total = balance.get('total', {}).get('USDT', 0.0)
        print(f"[SUCCESS] Connected to Binance Live Futures API successfully!")
        print(f"[INFO] Live USDT Wallet Balance: {usdt_total:.4f} USDT")
        
    except Exception as e:
        print(f"[ERROR] Failed to connect to Binance Live Futures: {e}")

if __name__ == '__main__':
    verify()
