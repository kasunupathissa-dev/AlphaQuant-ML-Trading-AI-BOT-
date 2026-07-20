import subprocess
import sys

def install_requirements():
    print("==================================================")
    print("  ALPHAQUANT V4.0: INSTALLING DEPENDENCIES        ")
    print("==================================================")
    
    # Removed strict version pinning for pandas and numpy to allow 
    # pip to fetch pre-compiled Windows wheels instead of trying to compile from source.
    requirements = [
        "ccxt",
        "ccxt[qa]",
        "pandas",
        "requests",
        "numpy",
        "pandas-ta",
        "xgboost",
        "scikit-learn",
        "sqlalchemy",
        "asyncio",
        "aiohttp"
    ]
    
    for req in requirements:
        print(f"Installing {req}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", req, "--upgrade"])
        except Exception as e:
            print(f"[WARNING] Failed to install {req}: {e}")
            print(f"-> Attempting installation without strict upgrades...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", req])
            except Exception as inner_e:
                 print(f"[FATAL] Could not install {req}.")
        
    print("==================================================")
    print("  [SUCCESS] Dependency installation finished.     ")
    print("==================================================")

if __name__ == "__main__":
    install_requirements()