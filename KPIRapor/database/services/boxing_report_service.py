import pandas as pd
from database.services.base.base_service import BaseService

class BoxingReportService(BaseService):
    @staticmethod
    def get_daily_boxing_report(
        date_from,
        date_to,
        branch_ids=None,
        department_ids=None,
        group_ids=None,
        machine_ids=None,
    ) -> pd.DataFrame:

        dims = []
        if branch_ids:     dims.append("Site")
        if department_ids: dims.append("Departman")
        if group_ids:      dims.append("Bolum")
        if machine_ids:    dims.extend(["Makine", "KaynakAdi"])

        empty_cols = dims + [
            "Gun",
            "Vardiya1ToplamUretim", "Vardiya2ToplamUretim", "Vardiya3ToplamUretim", "ToplamUretimAdet",
            "Vardiya1ToplamKasaDoldurmaAdet", "Vardiya2ToplamKasaDoldurmaAdet", "Vardiya3ToplamKasaDoldurmaAdet",
            "ToplamKasaDoldurmaAdet",
            "Vardiya1KasaDoldurulmayanAdet", "Vardiya2KasaDoldurulmayanAdet", "Vardiya3KasaDoldurulmayanAdet",
            "ToplamKasaDoldurulmayanAdet",
        ]
        if not date_from or not date_to:
            return pd.DataFrame(columns=empty_cols)

        # --- WHERE + params ---
        where_list = [
            'sopd."ByProduct" = FALSE',
            'sopd."StartDate" >= %s',
            'sopd."EndDate" < %s',
            '(p."PartNo" LIKE %s OR p."PartNo" LIKE %s)',  # <-- literal % yerine parametre
        ]
        params = [date_from, date_to, "3%", "2%"]

        def add_in(_where, _params, col_sql, values):
            if values:
                placeholders = ",".join(["%s"] * len(values))
                _where.append(f'{col_sql} IN ({placeholders})')
                _params.extend(values)

        add_in(where_list, params, 'm."BranchId"',     branch_ids)
        add_in(where_list, params, 'm."DepartmentId"', department_ids)
        add_in(where_list, params, 'm."GroupId"',      group_ids)
        add_in(where_list, params, 'm."Id"',           machine_ids)

        # --- Dinamik boyut alanları ---
        select_dim_parts, select_dim_columns = [], []
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

        # --- Zaman ve metrikler ---
        select_day = 'date_trunc(\'day\', sopd."CreatedAt")::date AS "Gun"'
        select_metrics = [
            # vardiya
            """CASE
                 WHEN sopd."CreatedAt"::time >= time '00:00' AND sopd."CreatedAt"::time < time '08:00' THEN 1
                 WHEN sopd."CreatedAt"::time >= time '08:00' AND sopd."CreatedAt"::time < time '16:00' THEN 2
                 ELSE 3
               END AS "VardiyaNo" """,
            # üretim adedi
            """CASE
                 WHEN EXTRACT(EPOCH FROM ("EndDate" - "StartDate")) >= 0
                 THEN "Quantity"
                 ELSE 0
               END AS "ToplamUretimAdet" """,
            # kasa doldurma adedi
            """CASE
                 WHEN (sopd."BoxID" <> '00000000-0000-0000-0000-000000000000' OR sopd."IfsReported" = TRUE)
                 THEN sopd."Quantity"
                 ELSE 0
               END AS "ToplamKasaDoldurmaAdet" """,
        ]

        select_parts = select_dim_parts + [select_day] + select_metrics
        select_sql = ",\n                    ".join(select_parts)

        # Dış SELECT (boyutlar + Gun)
        outer_select_cols = select_dim_columns + ['"Gun"']
        outer_select_sql  = ", ".join(outer_select_cols)

        # GROUP BY ve ORDER BY — kolon isimleriyle
        group_by_sql  = ", ".join(outer_select_cols)
        order_by_sql  = group_by_sql

        sql = f"""
            WITH base AS (
                SELECT
                    {select_sql}
                FROM public."ShopOrderProductionDetail" sopd
                LEFT JOIN "Machines"    m ON m."Id"        = sopd."WorkCenterID"
                LEFT JOIN "Branchs"     b ON b."Id"        = m."BranchId"
                LEFT JOIN "Departments" d ON d."Id"        = m."DepartmentId"
                LEFT JOIN "Groups"      g ON g."Id"        = m."GroupId"
                LEFT JOIN "Products"    p ON p."Id"        = sopd."ProductID"
                LEFT JOIN (
                    SELECT "PartID", MAX("alan1") AS "alan1"
                    FROM "ShopOrderOperations"
                    GROUP BY "PartID"
                ) soo ON soo."PartID" = p."Id"
                WHERE {' AND '.join(where_list)}
            )
            SELECT
                {outer_select_sql},
                COALESCE(SUM("ToplamUretimAdet")        FILTER (WHERE "VardiyaNo" = 1), 0) AS "Vardiya1ToplamUretim",
                COALESCE(SUM("ToplamUretimAdet")        FILTER (WHERE "VardiyaNo" = 2), 0) AS "Vardiya2ToplamUretim",
                COALESCE(SUM("ToplamUretimAdet")        FILTER (WHERE "VardiyaNo" = 3), 0) AS "Vardiya3ToplamUretim",
                COALESCE(SUM("ToplamUretimAdet"), 0)                                       AS "ToplamUretimAdet",
                COALESCE(SUM("ToplamKasaDoldurmaAdet")  FILTER (WHERE "VardiyaNo" = 1), 0) AS "Vardiya1ToplamKasaDoldurmaAdet",
                COALESCE(SUM("ToplamKasaDoldurmaAdet")  FILTER (WHERE "VardiyaNo" = 2), 0) AS "Vardiya2ToplamKasaDoldurmaAdet",
                COALESCE(SUM("ToplamKasaDoldurmaAdet")  FILTER (WHERE "VardiyaNo" = 3), 0) AS "Vardiya3ToplamKasaDoldurmaAdet",
                COALESCE(SUM("ToplamKasaDoldurmaAdet"), 0)                                 AS "ToplamKasaDoldurmaAdet",
                COALESCE(SUM("ToplamUretimAdet")        FILTER (WHERE "VardiyaNo" = 1), 0)
                  - COALESCE(SUM("ToplamKasaDoldurmaAdet") FILTER (WHERE "VardiyaNo" = 1), 0)     AS "Vardiya1KasaDoldurulmayanAdet",
                COALESCE(SUM("ToplamUretimAdet")        FILTER (WHERE "VardiyaNo" = 2), 0)
                  - COALESCE(SUM("ToplamKasaDoldurmaAdet") FILTER (WHERE "VardiyaNo" = 2), 0)     AS "Vardiya2KasaDoldurulmayanAdet",
                COALESCE(SUM("ToplamUretimAdet")        FILTER (WHERE "VardiyaNo" = 3), 0)
                  - COALESCE(SUM("ToplamKasaDoldurmaAdet") FILTER (WHERE "VardiyaNo" = 3), 0)     AS "Vardiya3KasaDoldurulmayanAdet",
                COALESCE(SUM("ToplamUretimAdet"), 0) - COALESCE(SUM("ToplamKasaDoldurmaAdet"), 0) AS "ToplamKasaDoldurulmayanAdet"
            FROM base
            GROUP BY {group_by_sql}
            ORDER BY {order_by_sql};
        """

        return BoxingReportService.execute_query(sql, params)

    @staticmethod
    def get_weekly_boxing_report(
            date_from,
            date_to,
            branch_ids=None,
            department_ids=None,
            group_ids=None,
            machine_ids=None,
    ) -> pd.DataFrame:

        dims = []
        if branch_ids:     dims.append("Site")
        if department_ids: dims.append("Departman")
        if group_ids:      dims.append("Bolum")
        if machine_ids:    dims.extend(["Makine", "KaynakAdi"])

        empty_cols = dims + [
            "Hafta", "Gun",
            "Vardiya1ToplamUretim", "Vardiya2ToplamUretim", "Vardiya3ToplamUretim", "ToplamUretimAdet",
            "Vardiya1ToplamKasaDoldurmaAdet", "Vardiya2ToplamKasaDoldurmaAdet", "Vardiya3ToplamKasaDoldurmaAdet",
            "ToplamKasaDoldurmaAdet",
            "Vardiya1KasaDoldurulmayanAdet", "Vardiya2KasaDoldurulmayanAdet", "Vardiya3KasaDoldurulmayanAdet",
            "ToplamKasaDoldurulmayanAdet",
        ]
        if not date_from or not date_to:
            return pd.DataFrame(columns=empty_cols)

        # --- WHERE + params ---
        where_list = [
            'sopd."ByProduct" = FALSE',
            'sopd."StartDate" >= %s',
            'sopd."EndDate" < %s',
            '(p."PartNo" LIKE %s OR p."PartNo" LIKE %s)',  # <-- literal % yerine parametre
        ]
        params = [date_from, date_to, "3%", "2%"]

        def add_in(_where, _params, col_sql, values):
            if values:
                placeholders = ",".join(["%s"] * len(values))
                _where.append(f'{col_sql} IN ({placeholders})')
                _params.extend(values)

        add_in(where_list, params, 'm."BranchId"', branch_ids)
        add_in(where_list, params, 'm."DepartmentId"', department_ids)
        add_in(where_list, params, 'm."GroupId"', group_ids)
        add_in(where_list, params, 'm."Id"', machine_ids)

        # --- Dinamik boyut alanları ---
        select_dim_parts, select_dim_columns = [], []
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

        # --- Zaman ve metrikler ---
        select_week = 'to_char(date_trunc(\'week\', sopd."CreatedAt")::date, \'YYYY-IW\') AS "Hafta"'
        select_day = 'date_trunc(\'day\', sopd."CreatedAt")::date AS "Gun"'
        select_metrics = [
            # vardiya
            """CASE
                 WHEN sopd."CreatedAt"::time >= time '00:00' AND sopd."CreatedAt"::time < time '08:00' THEN 1
                 WHEN sopd."CreatedAt"::time >= time '08:00' AND sopd."CreatedAt"::time < time '16:00' THEN 2
                 ELSE 3
               END AS "VardiyaNo" """,
            # üretim adedi
            """CASE
                 WHEN EXTRACT(EPOCH FROM ("EndDate" - "StartDate")) >= 0
                 THEN "Quantity"
                 ELSE 0
               END AS "ToplamUretimAdet" """,
            # kasa doldurma adedi
            """CASE
                 WHEN (sopd."BoxID" <> '00000000-0000-0000-0000-000000000000' OR sopd."IfsReported" = TRUE)
                 THEN sopd."Quantity"
                 ELSE 0
               END AS "ToplamKasaDoldurmaAdet" """,
        ]

        select_parts = select_dim_parts + [select_week, select_day] + select_metrics
        select_sql = ",\n                    ".join(select_parts)

        # Dış SELECT (boyutlar + Gun)
        outer_select_cols = select_dim_columns + ['"Hafta"', '"Gun"']
        outer_select_sql = ", ".join(outer_select_cols)

        # GROUP BY ve ORDER BY — kolon isimleriyle
        group_by_sql = ", ".join(outer_select_cols)
        order_by_sql = group_by_sql

        sql = f"""
                WITH base AS (
                    SELECT
                        {select_sql}
                    FROM public."ShopOrderProductionDetail" sopd
                    LEFT JOIN "Machines"    m ON m."Id"        = sopd."WorkCenterID"
                    LEFT JOIN "Branchs"     b ON b."Id"        = m."BranchId"
                    LEFT JOIN "Departments" d ON d."Id"        = m."DepartmentId"
                    LEFT JOIN "Groups"      g ON g."Id"        = m."GroupId"
                    LEFT JOIN "Products"    p ON p."Id"        = sopd."ProductID"
                    LEFT JOIN (
                        SELECT "PartID", MAX("alan1") AS "alan1"
                        FROM "ShopOrderOperations"
                        GROUP BY "PartID"
                    ) soo ON soo."PartID" = p."Id"
                    WHERE {' AND '.join(where_list)}
                )
                SELECT
                    {outer_select_sql},
                    COALESCE(SUM("ToplamUretimAdet")        FILTER (WHERE "VardiyaNo" = 1), 0) AS "Vardiya1ToplamUretim",
                    COALESCE(SUM("ToplamUretimAdet")        FILTER (WHERE "VardiyaNo" = 2), 0) AS "Vardiya2ToplamUretim",
                    COALESCE(SUM("ToplamUretimAdet")        FILTER (WHERE "VardiyaNo" = 3), 0) AS "Vardiya3ToplamUretim",
                    COALESCE(SUM("ToplamUretimAdet"), 0)                                       AS "ToplamUretimAdet",
                    COALESCE(SUM("ToplamKasaDoldurmaAdet")  FILTER (WHERE "VardiyaNo" = 1), 0) AS "Vardiya1ToplamKasaDoldurmaAdet",
                    COALESCE(SUM("ToplamKasaDoldurmaAdet")  FILTER (WHERE "VardiyaNo" = 2), 0) AS "Vardiya2ToplamKasaDoldurmaAdet",
                    COALESCE(SUM("ToplamKasaDoldurmaAdet")  FILTER (WHERE "VardiyaNo" = 3), 0) AS "Vardiya3ToplamKasaDoldurmaAdet",
                    COALESCE(SUM("ToplamKasaDoldurmaAdet"), 0)                                 AS "ToplamKasaDoldurmaAdet",
                    COALESCE(SUM("ToplamUretimAdet")        FILTER (WHERE "VardiyaNo" = 1), 0)
                      - COALESCE(SUM("ToplamKasaDoldurmaAdet") FILTER (WHERE "VardiyaNo" = 1), 0)     AS "Vardiya1KasaDoldurulmayanAdet",
                    COALESCE(SUM("ToplamUretimAdet")        FILTER (WHERE "VardiyaNo" = 2), 0)
                      - COALESCE(SUM("ToplamKasaDoldurmaAdet") FILTER (WHERE "VardiyaNo" = 2), 0)     AS "Vardiya2KasaDoldurulmayanAdet",
                    COALESCE(SUM("ToplamUretimAdet")        FILTER (WHERE "VardiyaNo" = 3), 0)
                      - COALESCE(SUM("ToplamKasaDoldurmaAdet") FILTER (WHERE "VardiyaNo" = 3), 0)     AS "Vardiya3KasaDoldurulmayanAdet",
                    COALESCE(SUM("ToplamUretimAdet"), 0) - COALESCE(SUM("ToplamKasaDoldurmaAdet"), 0) AS "ToplamKasaDoldurulmayanAdet"
                FROM base
                GROUP BY {group_by_sql}
                ORDER BY {order_by_sql};
            """

        return BoxingReportService.execute_query(sql, params)

    @staticmethod
    def get_monthly_boxing_report(
            date_from,
            date_to,
            branch_ids=None,
            department_ids=None,
            group_ids=None,
            machine_ids=None,
    ) -> pd.DataFrame:

        dims = []
        if branch_ids:     dims.append("Site")
        if department_ids: dims.append("Departman")
        if group_ids:      dims.append("Bolum")
        if machine_ids:    dims.extend(["Makine", "KaynakAdi"])

        empty_cols = dims + [
            "Hafta", "Gun",
            "Vardiya1ToplamUretim", "Vardiya2ToplamUretim", "Vardiya3ToplamUretim", "ToplamUretimAdet",
            "Vardiya1ToplamKasaDoldurmaAdet", "Vardiya2ToplamKasaDoldurmaAdet", "Vardiya3ToplamKasaDoldurmaAdet",
            "ToplamKasaDoldurmaAdet",
            "Vardiya1KasaDoldurulmayanAdet", "Vardiya2KasaDoldurulmayanAdet", "Vardiya3KasaDoldurulmayanAdet",
            "ToplamKasaDoldurulmayanAdet",
        ]
        if not date_from or not date_to:
            return pd.DataFrame(columns=empty_cols)

        # --- WHERE + params ---
        where_list = [
            'sopd."ByProduct" = FALSE',
            'sopd."StartDate" >= %s',
            'sopd."EndDate" < %s',
            '(p."PartNo" LIKE %s OR p."PartNo" LIKE %s)',  # <-- literal % yerine parametre
        ]
        params = [date_from, date_to, "3%", "2%"]

        def add_in(_where, _params, col_sql, values):
            if values:
                placeholders = ",".join(["%s"] * len(values))
                _where.append(f'{col_sql} IN ({placeholders})')
                _params.extend(values)

        add_in(where_list, params, 'm."BranchId"', branch_ids)
        add_in(where_list, params, 'm."DepartmentId"', department_ids)
        add_in(where_list, params, 'm."GroupId"', group_ids)
        add_in(where_list, params, 'm."Id"', machine_ids)

        # --- Dinamik boyut alanları ---
        select_dim_parts, select_dim_columns = [], []
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

        # --- Zaman ve metrikler ---
        select_month = 'to_char(date_trunc(\'month\', sopd."CreatedAt")::date, \'YYYY-MM\') AS "Ay"'
        select_week = 'to_char(date_trunc(\'week\', sopd."CreatedAt")::date, \'YYYY-IW\') AS "Hafta"'
        select_metrics = [
            # vardiya
            """CASE
                 WHEN sopd."CreatedAt"::time >= time '00:00' AND sopd."CreatedAt"::time < time '08:00' THEN 1
                 WHEN sopd."CreatedAt"::time >= time '08:00' AND sopd."CreatedAt"::time < time '16:00' THEN 2
                 ELSE 3
               END AS "VardiyaNo" """,
            # üretim adedi
            """CASE
                 WHEN EXTRACT(EPOCH FROM ("EndDate" - "StartDate")) >= 0
                 THEN "Quantity"
                 ELSE 0
               END AS "ToplamUretimAdet" """,
            # kasa doldurma adedi
            """CASE
                 WHEN (sopd."BoxID" <> '00000000-0000-0000-0000-000000000000' OR sopd."IfsReported" = TRUE)
                 THEN sopd."Quantity"
                 ELSE 0
               END AS "ToplamKasaDoldurmaAdet" """,
        ]

        select_parts = select_dim_parts + [select_month, select_week] + select_metrics
        select_sql = ",\n                    ".join(select_parts)

        # Dış SELECT (boyutlar + Gun)
        outer_select_cols = select_dim_columns + ['"Ay"', '"Hafta"']
        outer_select_sql = ", ".join(outer_select_cols)

        # GROUP BY ve ORDER BY — kolon isimleriyle
        group_by_sql = ", ".join(outer_select_cols)
        order_by_sql = group_by_sql

        sql = f"""
                    WITH base AS (
                        SELECT
                            {select_sql}
                        FROM public."ShopOrderProductionDetail" sopd
                        LEFT JOIN "Machines"    m ON m."Id"        = sopd."WorkCenterID"
                        LEFT JOIN "Branchs"     b ON b."Id"        = m."BranchId"
                        LEFT JOIN "Departments" d ON d."Id"        = m."DepartmentId"
                        LEFT JOIN "Groups"      g ON g."Id"        = m."GroupId"
                        LEFT JOIN "Products"    p ON p."Id"        = sopd."ProductID"
                        LEFT JOIN (
                            SELECT "PartID", MAX("alan1") AS "alan1"
                            FROM "ShopOrderOperations"
                            GROUP BY "PartID"
                        ) soo ON soo."PartID" = p."Id"
                        WHERE {' AND '.join(where_list)}
                    )
                    SELECT
                        {outer_select_sql},
                        COALESCE(SUM("ToplamUretimAdet")        FILTER (WHERE "VardiyaNo" = 1), 0) AS "Vardiya1ToplamUretim",
                        COALESCE(SUM("ToplamUretimAdet")        FILTER (WHERE "VardiyaNo" = 2), 0) AS "Vardiya2ToplamUretim",
                        COALESCE(SUM("ToplamUretimAdet")        FILTER (WHERE "VardiyaNo" = 3), 0) AS "Vardiya3ToplamUretim",
                        COALESCE(SUM("ToplamUretimAdet"), 0)                                       AS "ToplamUretimAdet",
                        COALESCE(SUM("ToplamKasaDoldurmaAdet")  FILTER (WHERE "VardiyaNo" = 1), 0) AS "Vardiya1ToplamKasaDoldurmaAdet",
                        COALESCE(SUM("ToplamKasaDoldurmaAdet")  FILTER (WHERE "VardiyaNo" = 2), 0) AS "Vardiya2ToplamKasaDoldurmaAdet",
                        COALESCE(SUM("ToplamKasaDoldurmaAdet")  FILTER (WHERE "VardiyaNo" = 3), 0) AS "Vardiya3ToplamKasaDoldurmaAdet",
                        COALESCE(SUM("ToplamKasaDoldurmaAdet"), 0)                                 AS "ToplamKasaDoldurmaAdet",
                        COALESCE(SUM("ToplamUretimAdet")        FILTER (WHERE "VardiyaNo" = 1), 0)
                          - COALESCE(SUM("ToplamKasaDoldurmaAdet") FILTER (WHERE "VardiyaNo" = 1), 0)     AS "Vardiya1KasaDoldurulmayanAdet",
                        COALESCE(SUM("ToplamUretimAdet")        FILTER (WHERE "VardiyaNo" = 2), 0)
                          - COALESCE(SUM("ToplamKasaDoldurmaAdet") FILTER (WHERE "VardiyaNo" = 2), 0)     AS "Vardiya2KasaDoldurulmayanAdet",
                        COALESCE(SUM("ToplamUretimAdet")        FILTER (WHERE "VardiyaNo" = 3), 0)
                          - COALESCE(SUM("ToplamKasaDoldurmaAdet") FILTER (WHERE "VardiyaNo" = 3), 0)     AS "Vardiya3KasaDoldurulmayanAdet",
                        COALESCE(SUM("ToplamUretimAdet"), 0) - COALESCE(SUM("ToplamKasaDoldurmaAdet"), 0) AS "ToplamKasaDoldurulmayanAdet"
                    FROM base
                    GROUP BY {group_by_sql}
                    ORDER BY {order_by_sql};
                """

        return BoxingReportService.execute_query(sql, params)
