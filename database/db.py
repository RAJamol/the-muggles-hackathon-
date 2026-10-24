import logging
from pathlib import Path
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
import config
from database.models import Base

logger = logging.getLogger(__name__)

# Engine configuration with resilient fallback
DB_MODE = "PostgreSQL"
DB_STATUS_NOTE = ""
HAS_DB_PGVECTOR = False

try:
    engine = create_engine(
        config.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20
    )
    # Test connection dialect loading
    engine.dialect.initialize(engine.connect())
    DB_MODE = "PostgreSQL"
    DB_STATUS_NOTE = "Connected to PostgreSQL"
except (ModuleNotFoundError, Exception) as err:
    # If psycopg2 / psycopg driver is not installed or Postgres is unreachable, fallback to SQLite
    sqlite_path = Path(__file__).resolve().parent.parent / "carebridge_local.db"
    sqlite_url = f"sqlite:///{sqlite_path}"
    logger.warning(
        f"PostgreSQL connection initialization failed ({err}). "
        f"Falling back to local SQLite at {sqlite_path}."
    )
    engine = create_engine(
        sqlite_url,
        connect_args={"check_same_thread": False}
    )
    DB_MODE = "SQLite (Zero-Config Fallback)"
    DB_STATUS_NOTE = (
        "Running in local SQLite mode because PostgreSQL driver ('psycopg2' / 'psycopg') is not installed "
        "or PostgreSQL is offline. Run 'pip install psycopg2-binary pgvector' to connect to PostgreSQL."
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def get_db():
    """Provide a transactional scope around a series of operations."""
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def init_database():
    """
    Initialize database schema.
    Attempts to enable pgvector extension if connected to PostgreSQL;
    creates all required tables (AppUser, Patient, Appointment, LabResult, PolicyChunk, etc.).
    """
    global HAS_DB_PGVECTOR, DB_STATUS_NOTE
    pgvector_status_msg = ""
    try:
        if "postgresql" in str(engine.url).lower():
            with engine.connect() as conn:
                try:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                    conn.commit()
                    HAS_DB_PGVECTOR = True
                    pgvector_status_msg = "pgvector extension active in PostgreSQL."
                except Exception as ve:
                    HAS_DB_PGVECTOR = False
                    pgvector_status_msg = "PostgreSQL active (pgvector extension not compiled on server; using standard vector fallback)."
        else:
            HAS_DB_PGVECTOR = False
            pgvector_status_msg = f"{DB_MODE} active."

        # Create all tables (AppUser, Patient, Appointment, LabResult, PolicyChunk, etc.)
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully.")
        return True, f"Database ready. ({pgvector_status_msg})"
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False, str(e)
