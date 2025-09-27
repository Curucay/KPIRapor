import streamlit as st
import pandas as pd
from database.services.base.base_service import BaseService

class ProductionService(BaseService):
    @staticmethod
    def get_daily_production_report(
        date_from,
        date_to,
        branch_ids=None,
        department_ids=None,
        group_ids=None,
        machine_ids=None,
    ) -> pd.DataFrame:
        # --- 0) Boş dönüş kolonları (seçili seviyelere göre) ---
        dim_empty = []
        if branch_ids:     dim_empty += ["Site"]
        if department_ids: dim_empty += ["Departman"]
        if group_ids:      dim_empty += ["Bolum"]
        if machine_ids:    dim_empty += ["Makine"]

        empty_cols = dim_empty + ["Gun", "Toplam", "AsanUretim", "AsmayanUretim", "AsanUretimYuzde"]
        if not date_from or not date_to:
            return pd.DataFrame(columns=empty_cols)

        # --- 1) WHERE ve paramlar ---
        where_clauses = [
            'vs."UretimBaslangicSaati" >= %s',
            'vs."UretimBaslangicSaati" < %s',
        ]
        params = [date_from, date_to]

        def add_in_filter(colname, values):
            nonlocal where_clauses, params
            if values:
                placeholders = ",".join(["%s"] * len(values))
                where_clauses.append(f'vs."{colname}" IN ({placeholders})')
                params.extend(values)

        add_in_filter("Site",            branch_ids)
        add_in_filter("UretimDepartman", department_ids)
        add_in_filter("UretimBolum",     group_ids)
        add_in_filter("ResourceID",      machine_ids)

        # --- 2) Dinamik boyut kolonları (alt sorgu stili) ---
        select_dim_parts = []
        order_labels = []

        if branch_ids:
            select_dim_parts.append('(SELECT b."Name" FROM "Branchs" b WHERE b."Id" = vs."Site") AS "Site"')
            order_labels.append('"Site"')

        if department_ids:
            select_dim_parts.append('(SELECT d."Name" FROM "Departments" d WHERE d."Id" = vs."UretimDepartman") AS "Departman"')
            order_labels.append('"Departman"')

        if group_ids:
            select_dim_parts.append('(SELECT g."Name" FROM "Groups" g WHERE g."Id" = vs."UretimBolum") AS "Bolum"')
            order_labels.append('"Bolum"')

        if machine_ids:
            select_dim_parts.append('vs."KaynakAdi"  AS "Makine"')
            order_labels.append('"Makine"')  # sıralamada isim kullan

        # --- 3) Gün periyodu (date_trunc) ---
        select_gun = 'date_trunc(\'day\', vs."UretimBaslangicSaati")::date AS "Gun"'

        # --- 4) Metrikler (liste halinde tut) ---
        select_metric_parts = [
            'COUNT(*) AS "Toplam"',
            'SUM((vs."AsimVarMi")::int) AS "AsanUretim"',
            'COUNT(*) - SUM((vs."AsimVarMi")::int) AS "AsmayanUretim"',
            'ROUND(100.0 * SUM((vs."AsimVarMi")::int) / NULLIF(COUNT(*), 0), 2) AS "AsanUretimYuzde"',
        ]

        # --- 5) SELECT/GROUP BY/ORDER BY ---
        select_parts = select_dim_parts + [select_gun] + select_metric_parts
        select_sql = ",\n                ".join(select_parts)

        # GROUP BY: dim sayısı + Gun (pozisyonla)
        dim_count = len(select_dim_parts)
        group_positions = list(range(1, dim_count + 1)) + [dim_count + 1]  # "Gun" pozisyonu
        group_by_sql = ", ".join(map(str, group_positions))

        order_by_sql = '"Gun"'
        if order_labels:
            order_by_sql += ", " + ", ".join(order_labels)

        sql = f"""
            SELECT
                {select_sql}
            FROM public."vw_ShopOrderProduction_AlertSet" vs
            WHERE {' AND '.join(where_clauses)}
            GROUP BY {group_by_sql}
            ORDER BY {order_by_sql};
        """

        return ProductionService.execute_query(sql, params)

    @staticmethod
    def get_weekly_production_report(
            date_from,
            date_to,
            branch_ids=None,
            department_ids=None,
            group_ids=None,
            machine_ids=None,
    ) -> pd.DataFrame:
        # --- 0) Boş dönüş kolonları (seçili seviyelere göre) ---
        dim_empty = []
        if branch_ids:     dim_empty += ["Site"]
        if department_ids: dim_empty += ["Departman"]
        if group_ids:      dim_empty += ["Bolum"]
        if machine_ids:    dim_empty += ["Makine"]

        empty_cols = dim_empty + ["Hafta", "Gun", "Toplam", "AsanUretim", "AsmayanUretim", "AsanUretimYuzde"]
        if not date_from or not date_to:
            return pd.DataFrame(columns=empty_cols)

        # --- 1) WHERE ve paramlar ---
        where_clauses = [
            'vs."UretimBaslangicSaati" >= %s',
            'vs."UretimBaslangicSaati" < %s',
        ]
        params = [date_from, date_to]

        def add_in_filter(colname, values):
            nonlocal where_clauses, params
            if values:
                placeholders = ",".join(["%s"] * len(values))
                where_clauses.append(f'vs."{colname}" IN ({placeholders})')
                params.extend(values)

        add_in_filter("Site", branch_ids)
        add_in_filter("UretimDepartman", department_ids)
        add_in_filter("UretimBolum", group_ids)
        add_in_filter("ResourceID", machine_ids)

        # --- 2) Dinamik boyut kolonları (alt sorgu stili) ---
        select_dim_parts = []
        order_labels = []

        if branch_ids:
            select_dim_parts.append('(SELECT b."Name" FROM "Branchs" b WHERE b."Id" = vs."Site") AS "Site"')
            order_labels.append('"Site"')

        if department_ids:
            select_dim_parts.append(
                '(SELECT d."Name" FROM "Departments" d WHERE d."Id" = vs."UretimDepartman") AS "Departman"')
            order_labels.append('"Departman"')

        if group_ids:
            select_dim_parts.append('(SELECT g."Name" FROM "Groups" g WHERE g."Id" = vs."UretimBolum") AS "Bolum"')
            order_labels.append('"Bolum"')

        if machine_ids:
            select_dim_parts.append('vs."KaynakAdi"  AS "Makine"')
            order_labels.append('"Makine"')  # sıralamada isim kullan

        # --- 3) Hafta ve Gün periyodu ---
        select_gun = [
            'vs."Hafta"',
            'vs."Gun"'
            ]

        # --- 4) Metrikler (liste halinde tut) ---
        select_metric_parts = [
            'COUNT(*) AS "Toplam"',
            'SUM((vs."AsimVarMi")::int) AS "AsanUretim"',
            'COUNT(*) - SUM((vs."AsimVarMi")::int) AS "AsmayanUretim"',
            'ROUND(100.0 * SUM((vs."AsimVarMi")::int) / NULLIF(COUNT(*), 0), 2) AS "AsanUretimYuzde"',
        ]

        # --- 5) SELECT/GROUP BY/ORDER BY ---
        select_parts = select_dim_parts + select_gun + select_metric_parts
        select_sql = ",\n                ".join(select_parts)

        # GROUP BY: dim sayısı
        dim_count = len(select_dim_parts)
        group_positions = list(range(1, dim_count + 1)) + [dim_count + 1 , dim_count + 2]  # "Hafta" ve "Gün" pozisyonu
        group_by_sql = ", ".join(map(str, group_positions))

        order_by_sql = '"Hafta"'
        if order_labels:
            order_by_sql += ", " + ", ".join(order_labels)

        sql = f"""
                SELECT
                    {select_sql}
                FROM public."vw_ShopOrderProduction_AlertSet" vs
                WHERE {' AND '.join(where_clauses)}
                GROUP BY {group_by_sql}
                ORDER BY {order_by_sql};
            """

        return ProductionService.execute_query(sql, params)

    @staticmethod
    def get_monthly_production_report(
            date_from,
            date_to,
            branch_ids=None,
            department_ids=None,
            group_ids=None,
            machine_ids=None,
    ) -> pd.DataFrame:
        # --- 0) Boş dönüş kolonları (seçili seviyelere göre) ---
        dim_empty = []
        if branch_ids:     dim_empty += ["Site"]
        if department_ids: dim_empty += ["Departman"]
        if group_ids:      dim_empty += ["Bolum"]
        if machine_ids:    dim_empty += ["Makine"]

        empty_cols = dim_empty + ["Ay", "Hafta", "Toplam", "AsanUretim", "AsmayanUretim", "AsanUretimYuzde"]
        if not date_from or not date_to:
            return pd.DataFrame(columns=empty_cols)

        # --- 1) WHERE ve paramlar ---
        where_clauses = [
            'vs."UretimBaslangicSaati" >= %s',
            'vs."UretimBaslangicSaati" < %s',
        ]
        params = [date_from, date_to]

        def add_in_filter(colname, values):
            nonlocal where_clauses, params
            if values:
                placeholders = ",".join(["%s"] * len(values))
                where_clauses.append(f'vs."{colname}" IN ({placeholders})')
                params.extend(values)

        add_in_filter("Site", branch_ids)
        add_in_filter("UretimDepartman", department_ids)
        add_in_filter("UretimBolum", group_ids)
        add_in_filter("ResourceID", machine_ids)

        # --- 2) Dinamik boyut kolonları (alt sorgu stili) ---
        select_dim_parts = []
        order_labels = []

        if branch_ids:
            select_dim_parts.append('(SELECT b."Name" FROM "Branchs" b WHERE b."Id" = vs."Site") AS "Site"')
            order_labels.append('"Site"')

        if department_ids:
            select_dim_parts.append(
                '(SELECT d."Name" FROM "Departments" d WHERE d."Id" = vs."UretimDepartman") AS "Departman"')
            order_labels.append('"Departman"')

        if group_ids:
            select_dim_parts.append('(SELECT g."Name" FROM "Groups" g WHERE g."Id" = vs."UretimBolum") AS "Bolum"')
            order_labels.append('"Bolum"')

        if machine_ids:
            select_dim_parts.append('vs."KaynakAdi"  AS "Makine"')
            order_labels.append('"Makine"')  # sıralamada isim kullan

        # --- 3) Hafta ve Gün periyodu ---
        select_gun = [
            'vs."Ay"',
            'vs."Hafta"'
            ]

        # --- 4) Metrikler (liste halinde tut) ---
        select_metric_parts = [
            'COUNT(*) AS "Toplam"',
            'SUM((vs."AsimVarMi")::int) AS "AsanUretim"',
            'COUNT(*) - SUM((vs."AsimVarMi")::int) AS "AsmayanUretim"',
            'ROUND(100.0 * SUM((vs."AsimVarMi")::int) / NULLIF(COUNT(*), 0), 2) AS "AsanUretimYuzde"',
        ]

        # --- 5) SELECT/GROUP BY/ORDER BY ---
        select_parts = select_dim_parts + select_gun + select_metric_parts
        select_sql = ",\n                ".join(select_parts)

        # GROUP BY: dim sayısı
        dim_count = len(select_dim_parts)
        group_positions = list(range(1, dim_count + 1)) + [dim_count + 1 , dim_count + 2]  # "Ay" ve "Hafta" pozisyonu
        group_by_sql = ", ".join(map(str, group_positions))

        order_by_sql = '"Ay"'
        if order_labels:
            order_by_sql += ", " + ", ".join(order_labels)

        sql = f"""
                SELECT
                    {select_sql}
                FROM public."vw_ShopOrderProduction_AlertSet" vs
                WHERE {' AND '.join(where_clauses)}
                GROUP BY {group_by_sql}
                ORDER BY {order_by_sql};
            """

        return ProductionService.execute_query(sql, params)
