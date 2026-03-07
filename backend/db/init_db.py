"""Initialize database and create tables."""
from sqlalchemy import text

from backend.db.models import Base, engine, SessionLocal, Watchlist
from backend.config import DEFAULT_WATCHLIST


def _safe_add_column(conn, table: str, column: str, col_type: str):
    """Add a column if it doesn't already exist (SQLite migration helper)."""
    try:
        conn.execute(text(f"SELECT {column} FROM {table} LIMIT 1"))
    except Exception:
        try:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            conn.commit()
        except Exception:
            pass


def init_db():
    """Create all tables if they don't exist and seed default watchlist."""
    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        # Migrate news table
        _safe_add_column(conn, "news", "category", "VARCHAR(32)")

        # Migrate predictions table (new columns)
        for col, typ in [
            ("entry_time", "VARCHAR(64)"),
            ("stop_loss_pct", "FLOAT"),
            ("sector_impact", "TEXT"),
            ("affected_tickers", "TEXT"),
            ("actual_outcome", "FLOAT"),
            ("action", "VARCHAR(24)"),
        ]:
            _safe_add_column(conn, "predictions", col, typ)

    db = SessionLocal()
    try:
        if db.query(Watchlist).count() == 0:
            for ticker in DEFAULT_WATCHLIST:
                db.add(Watchlist(ticker=ticker))
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
