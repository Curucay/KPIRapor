import streamlit as st
import pandas as pd
import re
from database.services.base.oracle_base_service import OracleBaseService

class ManualProductionService(OracleBaseService):
    @staticmethod
    def get_manuel_production_report(
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
        select_day = ""
        select_week = ""
        select_month = ""

        # --- 0) Boş dönüş kolonları (seçili seviyelere göre) ---
        if branch_contract:
            dim_empty += ["Site"]
            order_parts.append('"Site"')

        # Site, PersonelAdi ve mode göre order by oluşturulur.
        order_parts += ['"PersonelAdi"']

        if mode == "Gün":
            select_mode = ["Gun"]
            order_parts.append('"Gun"')
        elif mode == "Hafta":
            select_mode = ["Hafta", "Gun"]
            order_parts.append('"Hafta"')
            order_parts.append('"Gun"')
        elif mode == "Ay":
            select_mode = ["Ay", "Hafta"]
            order_parts.append('"Ay"')
            order_parts.append('"Hafta"')

        empty_cols = dim_empty + select_mode + ["PersonelAdi", "SiparisNo", "UrunKodu", "UrunTanimi", "Miktar", "Tutar"]
        if not date_from or not date_to:
            return pd.DataFrame(columns=empty_cols)

        # --- 1) WHERE ve paramlar ---
        where_clauses = [
            "A.transaction_code = :trans_code",
            "(A.quantity - A.qty_reversed) > 0",
            "A.date_applied >= :date_from",
            "A.date_applied < :date_to",
            "A.userid NOT IN (:user1, :user2)"
        ]
        params = {
            "trans_code": "OOREC",
            "date_from": date_from,
            "date_to": date_to,
            "user1": "IFSAPP",
            "user2": "IMES",
        }

        if branch_contract:
            # :c0, :c1, ... üret
            keys = [f"c{i}" for i in range(len(branch_contract))]
            where_clauses.append("A.contract IN (" + ",".join(f":{k}" for k in keys) + ")")
            params.update({k: v for k, v in zip(keys, branch_contract)})

        # --- 2) Dinamik boyut kolonları (alt sorgu stili) ---
        if branch_contract:
            select_dim_parts.append("(A.contract || ' ' || site_api.Get_Description(A.contract)) AS \"Site\"")

        # --- 3) Gün periyodu (date_trunc) ---
        select_day = "TO_CHAR(A.date_applied, 'YYYY-MM-DD') AS \"Gun\""
        select_week = "TO_CHAR(A.date_applied, 'IYYY-IW')   AS \"Hafta\""
        select_month = "TO_CHAR(A.date_applied, 'YYYY-MM')  AS \"Ay\""


        # --- 4) Metrikler (liste halinde tut) ---
        # (a) Toplanmayanlar -> GROUP BY'a girecek
        nonagg_metric_parts = [
            'A.userid                                                         AS "PersonelAdi"',
            'A.source_ref1                                                    AS "SiparisNo"',
            'A.part_no                                                        AS "UrunKodu"',
            'IFSAPP.INVENTORY_PART_API.Get_Description(A.contract, A.part_no) AS "UrunTanimi"',
        ]
        # (b) Agregatlar -> GROUP BY'a girmeyecek
        agg_metric_parts = [
            'SUM(A.quantity - A.qty_reversed) AS "Miktar"',
            '''ROUND(SUM( (A.quantity - A.qty_reversed)
                * Erkurt_Util20_Api.get_cntpart_last_unit_cost(A.contract, A.Part_No) ), 0) AS "Tutar"'''
        ]

        # --- 5) SELECT/GROUP BY/ORDER BY ---
        period_dims = []
        if mode == "Gün":
            period_dims.append(select_day)
        elif mode == "Hafta":
            period_dims.append(select_week)
            period_dims.append(select_day)
        elif mode == "Ay":
            period_dims.append(select_month)
            period_dims.append(select_week)

        select_parts = select_dim_parts + period_dims + nonagg_metric_parts + agg_metric_parts
        select_sql = ",\n                ".join(select_parts)

        # GROUP BY: dim sayısı + Gun (pozisyonla)
        def strip_alias(expr: str) -> str:
            # sondaki  AS "Alias" kısmını düşür
            return re.sub(r'\s+AS\s+"[^"]+"\s*$', '', expr, flags=re.I)

        group_by_parts = []
        # boyutlar
        group_by_parts += [strip_alias(x) for x in select_dim_parts]
        # GroupBy mode secimine göre period eklenir
        if mode == "Gün":
            group_by_parts.append(strip_alias(select_day))
        elif mode == "Hafta":
            group_by_parts.append(strip_alias(select_week))
            group_by_parts.append(strip_alias(select_day))
        elif mode == "Ay":
            group_by_parts.append(strip_alias(select_month))
            group_by_parts.append(strip_alias(select_week))
        # toplanmayan metrikler
        group_by_parts += [strip_alias(x) for x in nonagg_metric_parts]

        group_by_sql = ",\n                ".join(group_by_parts)

        # --- 7) ORDER BY ---
        order_by_sql = ", ".join(order_parts)

        sql = f"""
            SELECT
                {select_sql}
            FROM IFSAPP.INVENTORY_TRANSACTION_HIST2 A
            WHERE {' AND '.join(where_clauses)}
            GROUP BY 
                {group_by_sql}
            ORDER BY 
                {order_by_sql}
        """

        return ManualProductionService.execute_query(sql, params)