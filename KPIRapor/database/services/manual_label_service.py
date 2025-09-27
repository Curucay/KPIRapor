import pandas as pd
import streamlit as st
from database.services.base.base_service import BaseService

class ManualLabelService(BaseService):
    @staticmethod
    def get_daily_manual_label_report(
        date_from,
        date_to,
        branch_ids=None,       # list[uuid] -> m."BranchId"
        department_ids=None,   # list[uuid] -> m."DepartmentId"
        group_ids=None,        # list[uuid] -> m."GroupId"
        machine_ids=None,      # list[uuid] -> m."Id"
    ) -> pd.DataFrame:

        # 0) Boş dönüş kolonları (seçilen boyutlara göre)
        dims = []
        if branch_ids:     dims.append("Site")
        if department_ids: dims.append("Departman")
        if group_ids:      dims.append("Bolum")
        if machine_ids:    dims.extend(["Makine", "KaynakAdi"])

        empty_cols = dims + ["Gun", "Vardiya1Toplam", "Vardiya2Toplam", "Vardiya3Toplam", "ToplamManualAdet", "ToplamUretimAdet"]
        if not date_from or not date_to:
            return pd.DataFrame(columns=empty_cols)

        # ---- 1) WHERE ve paramlar ----
        where_manual = [
            'm."PlcActive" = TRUE',
            'sopd."CreatedAt" >= %s',
            'sopd."CreatedAt" < %s',
        ]
        params_manual = [date_from, date_to]

        where_total = [
            'sopd."ByProduct" = FALSE',
            'sopd."StartDate" >= %s',
            'sopd."EndDate"   < %s',
        ]
        params_total = [date_from, date_to]

        def add_in(where_list, params_list, col_sql, values):
            if values:
                placeholders = ",".join(["%s"] * len(values))
                where_list.append(f'{col_sql} IN ({placeholders})')
                params_list.extend(values)

        add_in(where_manual, params_manual, 'm."BranchId"',     branch_ids)
        add_in(where_manual, params_manual, 'm."DepartmentId"', department_ids)
        add_in(where_manual, params_manual, 'm."GroupId"',      group_ids)
        add_in(where_manual, params_manual, 'm."Id"',           machine_ids)

        add_in(where_total, params_total, 'm."BranchId"',     branch_ids)
        add_in(where_total, params_total, 'm."DepartmentId"', department_ids)
        add_in(where_total, params_total, 'm."GroupId"',      group_ids)
        add_in(where_total, params_total, 'm."Id"',           machine_ids)

        # 2) Dinamik boyut SELECT parçaları (JOIN edilen tablolardan isim al)
        select_dim_parts   = []
        select_dim_columns = []

        if branch_ids:
            select_dim_parts.append('b."Name" AS "Site"')
            select_dim_columns.append('"Site"')

        if department_ids:
            select_dim_parts.append('d."Name" AS "Departman"')
            select_dim_columns.append('"Departman"')

        if group_ids:
            select_dim_parts.append('g."Name" AS "Bolum"')
            select_dim_columns.append('"Bolum"')

        if machine_ids:
            select_dim_parts.append('m."Definition"   AS "Makine"')
            select_dim_parts.append('m."resourceName" AS "KaynakAdi"')
            select_dim_columns.append('"Makine"')
            select_dim_columns.append('"KaynakAdi"')

        # 3) Zaman ve metrik alanları
        select_day = 'date_trunc(\'day\', sopd."CreatedAt")::date AS "Gun"'
        select_manual_metrics = [
            'sopd."ManualInput" AS "ManualInput"',
            """CASE
                 WHEN sopd."CreatedAt"::time >= time '00:00' AND sopd."CreatedAt"::time < time '08:00' THEN 1
                 WHEN sopd."CreatedAt"::time >= time '08:00' AND sopd."CreatedAt"::time < time '16:00' THEN 2
                 ELSE 3
               END AS "VardiyaNo" """
        ]

        manual_select_parts = select_dim_parts + [select_day] + select_manual_metrics
        manual_select_sql = ",\n                    ".join(manual_select_parts)  # <-- listeyi join ediyoruz

        # 4) GROUP BY (pozisyonla: tüm boyutlar + Gun)
        dim_count = len(select_dim_parts)
        manual_group_positions = list(range(1, dim_count + 1)) + [dim_count + 1]  # "Gun" pozisyonu

        # 5) Dış SELECT kolonları: boyutlar + Gun
        manual_outer_cols = select_dim_columns + ['"Gun"']
        manual_outer_sql = ", ".join(manual_outer_cols)  # <-- join!

        select_list = ", ".join(f"m.{c}" for c in manual_outer_cols)

        # 6) ORDER BY
        order_by_sql = ""
        if manual_outer_cols:
            order_by_sql += ", ".join(manual_outer_cols)
        order_by_sql += ', "Gun"'

        #  Aynı dim kolonları + "Gun" üretelim
        total_dim_select = ",\n               ".join(select_dim_parts) if select_dim_parts else ""
        total_select_sql = ",\n               ".join(
            [p for p in [total_dim_select, 'sopd."StartDate"::date AS "Gun"'] if p]
        )

        # TotalAgg group by pozisyonları da aynı olmalı:
        # select_dim_parts (varsa) + "Gun"
        total_group_positions = list(range(1, dim_count + 1)) + [dim_count + 1]

        sql = f"""
            WITH BASE AS (
                SELECT
                    {manual_select_sql}
                FROM public."ShopOrderProductionDetail" sopd
                LEFT JOIN "Machines"    m ON m."Id"        = sopd."WorkCenterID"
                LEFT JOIN "Branchs"     b ON b."Id"        = m."BranchId"
                LEFT JOIN "Departments" d ON d."Id"        = m."DepartmentId"
                LEFT JOIN "Groups"      g ON g."Id"        = m."GroupId"
                WHERE {' AND '.join(where_manual)}
            ),
            ManualLabel AS (
                SELECT
                    {manual_outer_sql},
                    COALESCE(SUM("ManualInput") FILTER (WHERE "VardiyaNo" = 1), 0) AS "Vardiya1Toplam",
                    COALESCE(SUM("ManualInput") FILTER (WHERE "VardiyaNo" = 2), 0) AS "Vardiya2Toplam",
                    COALESCE(SUM("ManualInput") FILTER (WHERE "VardiyaNo" = 3), 0) AS "Vardiya3Toplam",
                    COALESCE(SUM("ManualInput"), 0)                                AS "ToplamManualAdet"
                FROM BASE
            GROUP BY {", ".join(map(str, manual_group_positions))}
            ),
            TotalProduct AS (
                SELECT 
                    {total_select_sql},
                    SUM(CASE
                            WHEN EXTRACT(EPOCH FROM ("EndDate" - "StartDate")) >= 0
                            THEN "Quantity"
                            ELSE 0
                        END) AS "ToplamUretimAdet"
                FROM public."ShopOrderProductionDetail" sopd
                LEFT JOIN "Machines"    m ON m."Id"        = sopd."WorkCenterID"
                LEFT JOIN "Branchs"     b ON b."Id"        = m."BranchId"
                LEFT JOIN "Departments" d ON d."Id"        = m."DepartmentId"
                LEFT JOIN "Groups"      g ON g."Id"        = m."GroupId"
                WHERE { ' AND '.join(where_total)}
                GROUP BY {", ".join(map(str, total_group_positions))}
            )
            SELECT
                {select_list},
                m."Vardiya1Toplam",
                m."Vardiya2Toplam",
                m."Vardiya3Toplam",
                m."ToplamManualAdet",
                t."ToplamUretimAdet"
            FROM ManualLabel m
            LEFT JOIN TotalProduct t ON {" AND ".join([f"m.{c} = t.{c}" for c in manual_outer_cols])}
            ORDER BY {order_by_sql};
        """

        params_all = params_manual + params_total
        return ManualLabelService.execute_query(sql, params_all)

    @staticmethod
    def get_weekly_manual_label_report(
            date_from,
            date_to,
            branch_ids=None,  # list[uuid] -> m."BranchId"
            department_ids=None,  # list[uuid] -> m."DepartmentId"
            group_ids=None,  # list[uuid] -> m."GroupId"
            machine_ids=None,  # list[uuid] -> m."Id"
    ) -> pd.DataFrame:

        # 0) Boş dönüş kolonları (seçilen boyutlara göre)
        dims = []
        if branch_ids:     dims.append("Site")
        if department_ids: dims.append("Departman")
        if group_ids:      dims.append("Bolum")
        if machine_ids:    dims.extend(["Makine", "KaynakAdi"])

        empty_cols = dims + ["Hafta", "Gun", "Vardiya1Toplam", "Vardiya2Toplam", "Vardiya3Toplam", "ToplamManualAdet", "ToplamUretimAdet"]
        if not date_from or not date_to:
            return pd.DataFrame(columns=empty_cols)

        # 1) WHERE ve paramlar (doğru alias'lar ile)
        where_manual = [
            'm."PlcActive" = TRUE',
            'sopd."CreatedAt" >= %s',
            'sopd."CreatedAt" < %s',
        ]
        params_manual = [date_from, date_to]

        where_total = [
            'sopd."ByProduct" = FALSE',
            'sopd."StartDate" >= %s',
            'sopd."EndDate"   < %s',
        ]
        params_total = [date_from, date_to]

        def add_in(where_list, params_list, col_sql, values):
            if values:
                placeholders = ",".join(["%s"] * len(values))
                where_list.append(f'{col_sql} IN ({placeholders})')
                params_list.extend(values)

        add_in(where_manual, params_manual, 'm."BranchId"',     branch_ids)
        add_in(where_manual, params_manual, 'm."DepartmentId"', department_ids)
        add_in(where_manual, params_manual, 'm."GroupId"',      group_ids)
        add_in(where_manual, params_manual, 'm."Id"',           machine_ids)

        add_in(where_total, params_total, 'm."BranchId"',     branch_ids)
        add_in(where_total, params_total, 'm."DepartmentId"', department_ids)
        add_in(where_total, params_total, 'm."GroupId"',      group_ids)
        add_in(where_total, params_total, 'm."Id"',           machine_ids)

        # 2) Dinamik boyut SELECT parçaları (JOIN edilen tablolardan isim al)
        select_dim_parts = []
        select_columns = []

        if branch_ids:
            select_dim_parts.append('b."Name" AS "Site"')
            select_columns.append('"Site"')

        if department_ids:
            select_dim_parts.append('d."Name" AS "Departman"')
            select_columns.append('"Departman"')

        if group_ids:
            select_dim_parts.append('g."Name" AS "Bolum"')
            select_columns.append('"Bolum"')

        if machine_ids:
            select_dim_parts.append('m."Definition"   AS "Makine"')
            select_dim_parts.append('m."resourceName" AS "KaynakAdi"')
            select_columns.append('"Makine"')
            select_columns.append('"KaynakAdi"')

        # 3) Zaman ve metrik alanları
        select_week = 'to_char(date_trunc(\'week\', sopd."CreatedAt")::date, \'YYYY-IW\') AS "Hafta"'
        select_day = 'date_trunc(\'day\', sopd."CreatedAt")::date   AS "Gun"'
        select_metrics = [
            'sopd."ManualInput" AS "ManualInput"',
            """CASE
                 WHEN sopd."CreatedAt"::time >= time '00:00' AND sopd."CreatedAt"::time < time '08:00' THEN 1
                 WHEN sopd."CreatedAt"::time >= time '08:00' AND sopd."CreatedAt"::time < time '16:00' THEN 2
                 ELSE 3
               END AS "VardiyaNo" """
        ]

        manual_select_parts = select_dim_parts + [select_week, select_day] + select_metrics
        manual_select_sql = ",\n                    ".join(manual_select_parts)  # <-- listeyi join ediyoruz

        # 4) GROUP BY (pozisyonla: tüm boyutlar + Gun)
        dim_count = len(select_dim_parts)
        manual_group_positions = list(range(1, dim_count + 1)) + [dim_count + 1, dim_count + 2]  # "Hafta" ve "Gun" pozisyonu

        # 5) Dış SELECT kolonları: boyutlar + Gun
        manual_outer_cols = select_columns + ['"Hafta"', '"Gun"']
        manual_outer_sql = ", ".join(manual_outer_cols)  # <-- join!

        select_list = ", ".join(f"m.{c}" for c in manual_outer_cols)

        # 6) ORDER BY
        order_by_sql = ", ".join([*manual_outer_cols])  # dims + "Hafta" + "Gun"

        #  Aynı dim kolonları için "Hafta" + "Gun" üretelim
        total_dim_select = ",\n               ".join(select_dim_parts) if select_dim_parts else ""

        total_select_sql = ",\n               ".join([p for p in [total_dim_select, select_week, select_day] if p])

        # TotalAgg group by pozisyonları da aynı olmalı:
        total_group_positions = list(range(1, dim_count + 1)) + [dim_count + 1 ,dim_count + 2]

        sql = f"""
                WITH BASE AS (
                SELECT
                    {manual_select_sql}
                FROM public."ShopOrderProductionDetail" sopd
                LEFT JOIN "Machines"    m ON m."Id"        = sopd."WorkCenterID"
                LEFT JOIN "Branchs"     b ON b."Id"        = m."BranchId"
                LEFT JOIN "Departments" d ON d."Id"        = m."DepartmentId"
                LEFT JOIN "Groups"      g ON g."Id"        = m."GroupId"
                WHERE {' AND '.join(where_manual)}
            ),
            ManualLabel AS (
                SELECT
                    {manual_outer_sql},
                    COALESCE(SUM("ManualInput") FILTER (WHERE "VardiyaNo" = 1), 0) AS "Vardiya1Toplam",
                    COALESCE(SUM("ManualInput") FILTER (WHERE "VardiyaNo" = 2), 0) AS "Vardiya2Toplam",
                    COALESCE(SUM("ManualInput") FILTER (WHERE "VardiyaNo" = 3), 0) AS "Vardiya3Toplam",
                    COALESCE(SUM("ManualInput"), 0)                                AS "ToplamManualAdet"
                FROM BASE
            GROUP BY {", ".join(map(str, manual_group_positions))}
            ),
            TotalProduct AS (
                SELECT 
                    {total_select_sql},
                    SUM(CASE
                            WHEN EXTRACT(EPOCH FROM ("EndDate" - "StartDate")) >= 0
                            THEN "Quantity"
                            ELSE 0
                        END) AS "ToplamUretim"
                FROM public."ShopOrderProductionDetail" sopd
                LEFT JOIN "Machines"    m ON m."Id"        = sopd."WorkCenterID"
                LEFT JOIN "Branchs"     b ON b."Id"        = m."BranchId"
                LEFT JOIN "Departments" d ON d."Id"        = m."DepartmentId"
                LEFT JOIN "Groups"      g ON g."Id"        = m."GroupId"
                WHERE { ' AND '.join(where_total)}
                GROUP BY {", ".join(map(str, total_group_positions))}
            )
            SELECT
                {select_list},
                m."Vardiya1Toplam",
                m."Vardiya2Toplam",
                m."Vardiya3Toplam",
                m."ToplamManualAdet",
                t."ToplamUretim"
            FROM ManualLabel m
            LEFT JOIN TotalProduct t ON {" AND ".join([f"m.{c} = t.{c}" for c in manual_outer_cols])}
            ORDER BY {", ".join([f"m.{c}" for c in manual_outer_cols])};;
            """

        params_all = params_manual + params_total
        return ManualLabelService.execute_query(sql, params_all)

    @staticmethod
    def get_monthly_manual_label_report(
            date_from,
            date_to,
            branch_ids=None,  # list[uuid] -> m."BranchId"
            department_ids=None,  # list[uuid] -> m."DepartmentId"
            group_ids=None,  # list[uuid] -> m."GroupId"
            machine_ids=None,  # list[uuid] -> m."Id"
    ) -> pd.DataFrame:

        # 0) Boş dönüş kolonları (seçilen boyutlara göre)
        dims = []
        if branch_ids:     dims.append("Site")
        if department_ids: dims.append("Departman")
        if group_ids:      dims.append("Bolum")
        if machine_ids:    dims.extend(["Makine", "KaynakAdi"])

        empty_cols = dims + ["Ay", "Hafta", "Vardiya1Toplam", "Vardiya2Toplam", "Vardiya3Toplam", "ToplamManualAdet", "ToplamUretimAdet"]
        if not date_from or not date_to:
            return pd.DataFrame(columns=empty_cols)

        # 1) WHERE ve paramlar (doğru alias'lar ile)
        where_manual = [
            'm."PlcActive" = TRUE',
            'sopd."CreatedAt" >= %s',
            'sopd."CreatedAt" < %s',
        ]
        params_manual = [date_from, date_to]

        where_total = [
            'sopd."ByProduct" = FALSE',
            'sopd."StartDate" >= %s',
            'sopd."EndDate"   < %s',
        ]
        params_total = [date_from, date_to]

        def add_in(where_list, params_list, col_sql, values):
            if values:
                placeholders = ",".join(["%s"] * len(values))
                where_list.append(f'{col_sql} IN ({placeholders})')
                params_list.extend(values)

        add_in(where_manual, params_manual, 'm."BranchId"',     branch_ids)
        add_in(where_manual, params_manual, 'm."DepartmentId"', department_ids)
        add_in(where_manual, params_manual, 'm."GroupId"',      group_ids)
        add_in(where_manual, params_manual, 'm."Id"',           machine_ids)

        add_in(where_total, params_total, 'm."BranchId"',     branch_ids)
        add_in(where_total, params_total, 'm."DepartmentId"', department_ids)
        add_in(where_total, params_total, 'm."GroupId"',      group_ids)
        add_in(where_total, params_total, 'm."Id"',           machine_ids)

        # 2) Dinamik boyut SELECT parçaları (JOIN edilen tablolardan isim al)
        select_dim_parts = []
        select_columns = []

        if branch_ids:
            select_dim_parts.append('b."Name" AS "Site"')
            select_columns.append('"Site"')

        if department_ids:
            select_dim_parts.append('d."Name" AS "Departman"')
            select_columns.append('"Departman"')

        if group_ids:
            select_dim_parts.append('g."Name" AS "Bolum"')
            select_columns.append('"Bolum"')

        if machine_ids:
            select_dim_parts.append('m."Definition"   AS "Makine"')
            select_dim_parts.append('m."resourceName" AS "KaynakAdi"')
            select_columns.append('"Makine"')
            select_columns.append('"KaynakAdi"')

        # 3) Zaman ve metrik alanları
        select_month = 'to_char(date_trunc(\'month\', sopd."CreatedAt")::date, \'YYYY-MM\') AS "Ay"'
        select_week = 'to_char(date_trunc(\'week\', sopd."CreatedAt")::date, \'YYYY-IW\') AS "Hafta"'
        select_metrics = [
            'sopd."ManualInput" AS "ManualInput"',
            """CASE
                 WHEN sopd."CreatedAt"::time >= time '00:00' AND sopd."CreatedAt"::time < time '08:00' THEN 1
                 WHEN sopd."CreatedAt"::time >= time '08:00' AND sopd."CreatedAt"::time < time '16:00' THEN 2
                 ELSE 3
               END AS "VardiyaNo" """
        ]

        manual_select_parts = select_dim_parts + [select_month, select_week] + select_metrics
        manual_select_sql = ",\n                    ".join(manual_select_parts)  # <-- listeyi join ediyoruz

        # 4) GROUP BY (pozisyonla: tüm boyutlar + Gun)
        dim_count = len(select_dim_parts)
        manual_group_positions = list(range(1, dim_count + 1)) + [dim_count + 1, dim_count + 2]  # "Ay" ve "Hafta" pozisyonu

        # 5) Dış SELECT kolonları: boyutlar + Gun
        manual_outer_cols = select_columns + ['"Ay"', '"Hafta"']
        manual_outer_sql = ", ".join(manual_outer_cols)  # <-- join!

        select_list = ", ".join(f"m.{c}" for c in manual_outer_cols)

        # 6) ORDER BY
        order_by_sql = ", ".join([*manual_outer_cols])  # dims + "Ay" + "Hafta"

        #  Aynı dim kolonları için "Hafta" + "Gun" üretelim
        total_dim_select = ",\n               ".join(select_dim_parts) if select_dim_parts else ""

        total_select_sql = ",\n               ".join([p for p in [total_dim_select, select_month, select_week] if p])

        # TotalAgg group by pozisyonları da aynı olmalı:
        total_group_positions = list(range(1, dim_count + 1)) + [dim_count + 1, dim_count + 2]

        sql = f"""
                WITH BASE AS (
                SELECT
                    {manual_select_sql}
                FROM public."ShopOrderProductionDetail" sopd
                LEFT JOIN "Machines"    m ON m."Id"        = sopd."WorkCenterID"
                LEFT JOIN "Branchs"     b ON b."Id"        = m."BranchId"
                LEFT JOIN "Departments" d ON d."Id"        = m."DepartmentId"
                LEFT JOIN "Groups"      g ON g."Id"        = m."GroupId"
                WHERE {' AND '.join(where_manual)}
            ),
            ManualLabel AS (
                SELECT
                    {manual_outer_sql},
                    COALESCE(SUM("ManualInput") FILTER (WHERE "VardiyaNo" = 1), 0) AS "Vardiya1Toplam",
                    COALESCE(SUM("ManualInput") FILTER (WHERE "VardiyaNo" = 2), 0) AS "Vardiya2Toplam",
                    COALESCE(SUM("ManualInput") FILTER (WHERE "VardiyaNo" = 3), 0) AS "Vardiya3Toplam",
                    COALESCE(SUM("ManualInput"), 0)                                AS "ToplamManualAdet"
                FROM BASE
            GROUP BY {", ".join(map(str, manual_group_positions))}
            ),
            TotalProduct AS (
                SELECT 
                    {total_select_sql},
                    SUM(CASE
                            WHEN EXTRACT(EPOCH FROM ("EndDate" - "StartDate")) >= 0
                            THEN "Quantity"
                            ELSE 0
                        END) AS "ToplamUretim"
                FROM public."ShopOrderProductionDetail" sopd
                LEFT JOIN "Machines"    m ON m."Id"        = sopd."WorkCenterID"
                LEFT JOIN "Branchs"     b ON b."Id"        = m."BranchId"
                LEFT JOIN "Departments" d ON d."Id"        = m."DepartmentId"
                LEFT JOIN "Groups"      g ON g."Id"        = m."GroupId"
                WHERE {' AND '.join(where_total)}
                GROUP BY {", ".join(map(str, total_group_positions))}
            )
            SELECT
                {select_list},
                m."Vardiya1Toplam",
                m."Vardiya2Toplam",
                m."Vardiya3Toplam",
                m."ToplamManualAdet",
                t."ToplamUretim"
            FROM ManualLabel m
            LEFT JOIN TotalProduct t ON {" AND ".join([f"m.{c} = t.{c}" for c in manual_outer_cols])}
            ORDER BY {", ".join([f"m.{c}" for c in manual_outer_cols])};;
            """

        params_all = params_manual + params_total

        return ManualLabelService.execute_query(sql, params_all)
