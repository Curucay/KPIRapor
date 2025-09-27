import psycopg2
from contextlib import contextmanager
from config.settings import settings
import warnings

# Pandas uyarısını bastır
warnings.filterwarnings('ignore', message='pandas only supports SQLAlchemy connectable')

@contextmanager
def get_db_connection():
    """Database connection context manager"""
    conn = None
    try:
        if not settings.DB_CONN_STR:
            raise RuntimeError("DB_CONN_STR tanımlı değil (.env veya ortam değişkeni).")
        conn = psycopg2.connect(settings.DB_CONN_STR)
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

def get_db_info_from_conn(DB_CONN_STR):
    """Aktif psycopg2 connection üzerinden db bilgisi alır"""
    try:
        with psycopg2.connect(DB_CONN_STR) as conn:
            dbname = conn.info.dbname
            return f"{dbname}"
    except Exception as e:
        return f"DB Error: {e}"