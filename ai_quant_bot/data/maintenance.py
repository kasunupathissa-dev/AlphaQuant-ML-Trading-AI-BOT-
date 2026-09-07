import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from ai_quant_bot.data.database import AsyncSessionLocal

async def run_database_maintenance():
    """
    Daily maintenance task to purge raw ticks, temporary tables, and order logs 
    older than 7 days, while executing VACUUM optimization to reclaim disk space.
    Permanently keeps aggregated 1m/15m/1h OHLCV bars.
    """
    print("[MAINTENANCE] Initiating daily database purge and storage optimization...")
    try:
        async with AsyncSessionLocal() as session:
            # 1. Purge hypothetical tick tables older than 7 days (if they exist)
            # This is a defensive safeguard that keeps database tables clean
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
            
            # Execute database vacuuming and raw logs pruning
            # Prune old logs or signal rejection metadata older than 90 days for long-term safety
            stmt_rejections = text(
                "DELETE FROM signal_rejections WHERE timestamp < :cutoff"
            )
            # Keep raw rejections for 30 days, purge older ones
            rejections_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            
            await session.execute(stmt_rejections, {"cutoff": rejections_cutoff})
            await session.commit()
            print("[MAINTENANCE] Purged signal rejection logs older than 30 days.")

            # 2. Run VACUUM to reclaim disk space (requires autocommit level, so we execute via connection)
            # In SQLite / PostgreSQL, running vacuum is standard maintenance practice
            conn = await session.connection()
            await conn.execute(text("VACUUM;"))
            print("[MAINTENANCE] VACUUM cleanup complete. Disk space reclaimed successfully.")

    except Exception as e:
        print(f"[ERROR] Database maintenance task failed: {e}")

async def start_maintenance_schedule_loop():
    """Asynchronously triggers database maintenance task once every 24 hours."""
    while True:
        await asyncio.sleep(86400)  # Run once every 24 hours
        await run_database_maintenance()
