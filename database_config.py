import os
from sqlalchemy import create_engine

# ==================================================
# ALPHAQUANT V6.5: SECURE DATABASE CONFIGURATION
# ==================================================

# 🟢 V6.5 Upgrade: Read credentials from environment variables for security.
# The hardcoded values are kept as a fallback for local development.
DB_TYPE = os.getenv("DB_TYPE", "mysql")
DB_USER = os.getenv("DB_USER", "aq_user")
DB_PASS = os.getenv("DB_PASS", "root") # Defaulting to 'root' as per our last fix
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "alphaquant_v5")

def get_db_engine():
    """
    Creates and returns a SQLAlchemy engine based on the configuration.
    """
    if DB_TYPE == "mysql":
        connection_string = f"mysql+mysqldb://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        try:
            engine = create_engine(connection_string)
            with engine.connect() as connection:
                print("[SUCCESS] Connected to MySQL database.")
            return engine
        except Exception as e:
            print(f"[FATAL] Could not connect to MySQL database: {e}")
            print("Please ensure the database exists, credentials are correct, and 'mysqlclient' is installed.")
            exit()
    else:
        print("[INFO] Using local SQLite database.")
        return create_engine("sqlite:///alphaquant_ml_v4.db")