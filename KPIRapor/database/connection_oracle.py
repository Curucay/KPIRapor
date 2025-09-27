# database/connection_oracle.py
from __future__ import annotations
from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

import oracledb
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine, Connection

from config.settings import settings


def _auth_mode(connect_as: str | None) -> int:
    cmap = {
        "NORMAL": oracledb.AUTH_MODE_DEFAULT,
        "SYSDBA": oracledb.AUTH_MODE_SYSDBA,
        "SYSOPER": oracledb.AUTH_MODE_SYSOPER,
        "SYSASM": oracledb.AUTH_MODE_SYSASM,
    }
    key = (connect_as or "NORMAL").upper()
    return cmap.get(key, oracledb.AUTH_MODE_DEFAULT)


def _build_url() -> URL:
    """
    est.py’deki gibi URL’i kurar: oracle+oracledb + service_name’i query ile verir.
    """
    return URL.create(
        "oracle+oracledb",
        username=settings.ORACLE_USER,
        password=settings.ORACLE_PASSWORD,
        host=settings.ORACLE_HOST,
        port=int(getattr(settings, "ORACLE_PORT", 1521)),
        query={"service_name": settings.ORACLE_SERVICE},  # <— test.py ile aynı yaklaşım
    )


@lru_cache(maxsize=1)
def get_oracle_engine() -> Engine:
    """
    Tek bir Engine üretir ve cache’ler. Pooling, pre-ping açık.
    """
    url = _build_url()
    mode = _auth_mode(getattr(settings, "ORACLE_CONNECT_AS", "NORMAL"))

    engine = create_engine(
        url,
        connect_args={"mode": mode},
        pool_pre_ping=True,
        hide_parameters=True,
        # echo=True,  # debug için açılabilir
    )
    return engine


@contextmanager
def get_oracle_connection() -> Iterator[Connection]:
    """
    Kullan-at bağlantı context’i. Bağlantıyı otomatik kapatır.
    """
    engine = get_oracle_engine()
    with engine.connect() as conn:
        yield conn

