import os
from sqlalchemy import create_engine, text

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
                create_table_query = """
                CREATE TABLE IF NOT EXISTS signal_rejection_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    timestamp BIGINT,
                    asset VARCHAR(20),
                    direction VARCHAR(10),
                    win_prob DOUBLE,
                    threshold DOUBLE,
                    regime VARCHAR(20),
                    rejection_reason VARCHAR(50),
                    bot VARCHAR(15)
                )
                """
                connection.execute(text(create_table_query))
                connection.commit()
                
                # Dynamic migration to add bot column to existing MySQL tables
                try:
                    connection.execute(text("ALTER TABLE signal_rejection_history ADD COLUMN bot VARCHAR(15)"))
                    connection.commit()
                except Exception:
                    pass
            return engine
        except Exception as e:
            print(f"[FATAL] Could not connect to MySQL database: {e}")
            print("Please ensure the database exists, credentials are correct, and 'mysqlclient' is installed.")
            exit()
    else:
        print("[INFO] Using local SQLite database.")
        engine = create_engine("sqlite:///alphaquant_ml_v4.db")
        with engine.connect() as connection:
            create_table_query = """
            CREATE TABLE IF NOT EXISTS signal_rejection_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp BIGINT,
                asset VARCHAR(20),
                direction VARCHAR(10),
                win_prob DOUBLE,
                threshold DOUBLE,
                regime VARCHAR(20),
                rejection_reason VARCHAR(50),
                bot VARCHAR(15)
            )
            """
            connection.execute(text(create_table_query))
            connection.commit()
            
            # Dynamic migration to add bot column to existing SQLite tables
            try:
                connection.execute(text("ALTER TABLE signal_rejection_history ADD COLUMN bot VARCHAR(15)"))
                connection.commit()
            except Exception:
                pass
        return engine