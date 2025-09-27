# database/services/oracle_base_service.py
from __future__ import annotations
import warnings
import pandas as pd
from database.connection_oracle import get_oracle_connection
from sqlalchemy import text
from sqlalchemy.engine import Connection

class OracleBaseService:
    """
    Oracle’a özel base servis.
    İmza ve davranış, mevcut BaseService'e paraleldir.
    """

    @staticmethod
    def execute_query(sql: str, params: dict | tuple | list | None = None) -> pd.DataFrame:
        """
        Oracle üzerinde SELECT sorgusu çalıştırır ve DataFrame döner.
        Parametre bağlama Oracle tarzı :name placeholder’larıyla yapılır.
        Örn: WHERE CREATED_AT BETWEEN :start_dt AND :end_dt
        """
        with get_oracle_connection() as conn:  # type: Connection
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return pd.read_sql_query(text(sql), conn, params=params)