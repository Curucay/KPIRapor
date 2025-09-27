import pandas as pd
import streamlit as st
from database.connection import get_db_connection
import warnings


class BaseService:
    """Tüm servislerin ortak metodlarını içeren base class"""

    @staticmethod
    def execute_query(sql, params=None, cache_ttl=300):
        """Genel sorgu çalıştırma metodu"""
        with get_db_connection() as conn:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return pd.read_sql_query(sql, conn, params=params)

    @staticmethod
    def clean_numeric_columns(df, columns):
        """Sayısal sütunları temizle"""
        if not df.empty:
            for col in columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        return df