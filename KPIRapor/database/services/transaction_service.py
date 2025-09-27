import streamlit as st
import pandas as pd
from database.services.base.oracle_base_service import OracleBaseService

class TransactionService(OracleBaseService):
    @staticmethod
    def get_transaction_report(
        date_from,
        date_to,
        branch_contract=None,
        mode=None
    ) -> pd.DataFrame:
        # Değişken tanımlamaları
        dim_empty = []
        select_mode = []
        select_dim_parts = []
        order_parts = []
        group_by_parts = []
        select_day = ""
        select_week = ""
        select_month = ""

        # --- 0) Boş dönüş kolonları (seçili seviyelere göre) ---
        if branch_contract:
            dim_empty += ["Site"]
            order_parts.append('q.Site')
            group_by_parts.append('q.Site')

        if mode == "Gün":
            select_mode = ["Gun"]
            order_parts.append('q.Gun')
            order_parts.append('q.Saat')
            group_by_parts.append('q.Gun')
            group_by_parts.append('q.Saat')
        elif mode == "Hafta":
            select_mode = ["Hafta", "Gun"]
            order_parts.append('q.Hafta')
            order_parts.append('q.Gun')
            group_by_parts.append('q.Hafta')
            group_by_parts.append('q.Gun')
        elif mode == "Ay":
            select_mode = ["Ay", "Hafta"]
            order_parts.append('q.Ay')
            order_parts.append('q.Hafta')
            group_by_parts.append('q.Ay')
            group_by_parts.append('q.Hafta')

        empty_cols = dim_empty + select_mode + ["Toplam"]
        if not date_from or not date_to:
            return pd.DataFrame(columns=empty_cols)

        # --- 1) WHERE ve paramlar ---
        where_clauses = [
            "q.Tarih >= :date_from",
            "q.Tarih < :date_to",
        ]
        params = {
            "date_from": date_from,
            "date_to": date_to,
        }

        if branch_contract:
            # :c0, :c1, ... üret
            keys = [f"c{i}" for i in range(len(branch_contract))]
            where_clauses.append("q.contract IN (" + ",".join(f":{k}" for k in keys) + ")")
            params.update({k: v for k, v in zip(keys, branch_contract)})

        # --- 2) Dinamik boyut kolonları (alt sorgu stili) ---
        if branch_contract:
            select_dim_parts.append("q.Site")

        # --- 3) Gün periyodu (date_trunc) ---
        select_hour = 'q.Saat'
        select_day = "q.Gun"
        select_week = "q.Hafta"
        select_month = "q.Ay"

        # --- 4) Metrikler (liste halinde tut) ---
        agg_metric_parts = [
            'SUM(q.trn_sayisi) AS Toplam'
        ]

        # --- 5) SELECT ---
        period_dims = []
        if mode == "Gün":
            period_dims.append(select_day)
            period_dims.append(select_hour)
        elif mode == "Hafta":
            period_dims.append(select_week)
            period_dims.append(select_day)
        elif mode == "Ay":
            period_dims.append(select_month)
            period_dims.append(select_week)

        select_parts = select_dim_parts + period_dims + agg_metric_parts
        select_sql = ",\n       ".join(select_parts)

        # --- 6) GROUP BY ---
        group_by_sql = ",\n     ".join(group_by_parts)

        # --- 7) ORDER BY ---
        order_by_sql = ",\n     ".join(order_parts)

        sql = f"""
            SELECT
                {select_sql}
            FROM(
                    SELECT
                       t.contract,
                       site_api.Get_Description(t.contract) AS Site,
                       TRUNC(t.saat) AS Tarih, 
                       TO_CHAR(t.saat, 'YYYY-MM')       AS Ay,
                       TO_CHAR(t.saat, 'IYYY-IW')       AS Hafta, 
                       TO_CHAR(t.saat, 'YYYY-MM-DD')    AS Gun, 
                       TO_CHAR(t.saat, 'HH24:MI:SS')    AS Saat,  
                       t.trn_sayisi
                    FROM erk_temp_trn_tab t
                ) q
            WHERE {' AND '.join(where_clauses)}
            GROUP BY 
                {group_by_sql}
            ORDER BY 
                {order_by_sql}
        """

        return TransactionService.execute_query(sql, params)