import streamlit as st
import pandas as pd
import datetime as _dt
import calendar as _cal
from database.services.production_service import ProductionService
from database.services.manual_label_service import ManualLabelService
from database.services.boxing_report_service import BoxingReportService
from database.services.manual_production_service import ManualProductionService
from database.services.transaction_service import TransactionService
from database.services.filter_service import FilterService
from utils.session_helper import apply_pending_clear, schedule_clear, clear_on_page_dataframe

TR_MONTHS = [
    "Ocak","Şubat","Mart","Nisan","Mayıs","Haziran",
    "Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"
]

PAGE_DF_KEY = {
    "production_report": "production_df",
    "manual_label_report" : "manual_label_df",
    "boxing_report" : "boxing_report_df",
    "manual_production_report" : "manual_production_df",
    "transaction_report" : "transaction_df"
}


def _week_bounds(d: _dt.date):
    start = d - _dt.timedelta(days=d.weekday())  # Pazartesi
    end   = start + _dt.timedelta(days=6)        # Pazar
    return start, end


class FilterComponent:
    def __init__(self):
        self.db = FilterService()

    @staticmethod
    def _month_bounds(year: int, month: int):
        first_day = _dt.date(year, month, 1)
        last_day  = _dt.date(year, month, _cal.monthrange(year, month)[1])
        return first_day, last_day

    # ---------- Şube ----------
    def render_branch_filter(self):
        branches_df = self.db.get_branches()
        if branches_df.empty:
            st.warning("Şube verisi bulunamadı.")
            return [], {}

        name2id = dict(zip(branches_df["Name"], branches_df["Id"]))
        selected_names = st.multiselect(
            "🏢 Şube(ler)i seçin",
            options=list(name2id.keys()),
            placeholder="Şube seçin...",
            help="Rapor için şube(leri) seçin",
            key="branch_ms",
        )
        return [name2id[n] for n in selected_names], name2id

    def render_branch_contract_filter(self):
        branches_df = self.db.get_branches()
        if branches_df.empty:
            st.warning("Şube verisi bulunamadı.")
            return [], {}

        name2id = dict(zip(branches_df["Name"], branches_df["ERPConnectionCode"]))
        selected_names = st.multiselect(
            "🏢 Şube(ler)i seçin",
            options=list(name2id.keys()),
            placeholder="Şube seçin...",
            help="Rapor için şube(leri) seçin",
            key="branch_ms",
        )
        return [name2id[n] for n in selected_names], name2id

    # ---------- Departman ----------
    def render_department_filter(self, selected_branch_ids):
        if not selected_branch_ids:
            st.info("Önce şube seçimi yapın.")
            return [], {}

        department_df = self.db.get_departments(selected_branch_ids)
        if department_df is None or department_df.empty:
            st.warning("Departman verisi bulunamadı.")
            return [], {}

        name2id = dict(zip(department_df["Name"], department_df["Id"]))
        selected_names = st.multiselect(
            "🏢 Departman(lar)ı seçin",
            options=list(name2id.keys()),
            placeholder="Departman seçin...",
            help="Rapor için departman(ları) seçin",
            key="department_ms",
        )
        return [name2id[n] for n in selected_names], name2id

    # ---------- Grup ----------
    def render_group_filter(self, selected_department_ids):
        if not selected_department_ids:
            st.info("Önce departman seçimi yapın.")
            return [], {}

        group_df = self.db.get_groups(selected_department_ids)
        if group_df is None or group_df.empty:
            st.warning("Bölüm verisi bulunamadı.")
            return [], {}

        name2id = dict(zip(group_df["Name"], group_df["Id"]))
        selected_names = st.multiselect(
            "🏢 Bölüm(ler)i seçin",
            options=list(name2id.keys()),
            placeholder="Bölüm seçin...",
            help="Rapor için bölüm(leri) seçin",
            key="group_ms",
        )
        return [name2id[n] for n in selected_names], name2id

    # ---------- Makine ----------
    def render_machine_filter(self, selected_branch_ids, selected_department_ids=None, selected_group_ids=None):
        if not selected_branch_ids:
            st.info("Önce şube/departman/bölüm seçimi yapın.")
            return []

        machines_df = self.db.get_machines_by_branches_and_departments(selected_branch_ids, selected_department_ids, selected_group_ids)

        if machines_df is None or machines_df.empty:
            st.info("Seçilen filtrelere ait makine bulunamadı.")
            return []

        machines_df["Label"] = machines_df.apply(
            lambda r: f"{r.get('Definition', '(Tanımsız)')} ({r.get('Code', '')})", axis=1
        )
        label2id = dict(zip(machines_df["Label"], machines_df["Id"]))

        selected_labels = st.multiselect(
            "🔧 Makine(leri) seçin",
            options=list(label2id.keys()),
            placeholder="Makine seçin...",
            help="Rapor için makine(leri) seçin",
            key="machine_ms",
        )
        return [label2id[l] for l in selected_labels]

    # ---------- Hızlı arama (opsiyonel) ----------
    def render_quick_filter(self):
        return st.text_input(
            "🔍 Hızlı Arama",
            value=st.session_state.get("quick_search", ""),
            placeholder="Makine, parça, kaynak adı...",
            help="Sonuçlar içinde arama yapın",
            key="quick_search",
        )

    # ---------- Tarih ----------
    def render_date_column(self):
        """Gün/Hafta/Ay seçimli tarih filtresi (uyarı üretmez)."""
        today = _dt.date.today()

        # State başlangıçları (sadece ilk kez)
        st.session_state.setdefault("prd_mode", "Gün")          # "Gün" | "Hafta" | "Ay"
        st.session_state.setdefault("prd_year", today.year)
        st.session_state.setdefault("prd_month", today.month)
        st.session_state.setdefault("prd_day", today)
        st.session_state.setdefault("prd_week_monday", today)

        # Aktif sayfa için aktif kullanılan dataframe seçilir.
        current_page = st.session_state.get("active_page")
        current_df = PAGE_DF_KEY.get(current_page)

        left, right = st.columns([1, 1])
        with left:
            st.markdown("#### 🗓️ Tarih")
            st.radio("Dönem", ["Gün", "Hafta", "Ay"], key="prd_mode", horizontal=True)

        mode = st.session_state["prd_mode"]

        if mode == "Gün":
            clear_on_page_dataframe(current_df)
            # Yalnız key veriyoruz; value vermiyoruz -> uyarı yok
            st.date_input("Tarih", key="prd_day")
            d = st.session_state["prd_day"]
            date_from = d
            date_to = d + _dt.timedelta(days=1)

        elif mode == "Hafta":
            clear_on_page_dataframe(current_df)
            st.date_input("Hafta seçin", key="prd_week_monday")
            monday = st.session_state["prd_week_monday"]
            monday = monday - _dt.timedelta(days=monday.weekday())
            sunday = monday + _dt.timedelta(days=7)
            iso = monday.isocalendar()
            week_no = iso.week
            date_from, date_to = monday, sunday
            st.markdown(f"🔎 Seçilen {week_no}. hafta: **{monday:%d.%m.%Y} – {(sunday - _dt.timedelta(days=1)):%d.%m.%Y}**")


        else:  # Ay
            clear_on_page_dataframe(current_df)
            yc, mc = st.columns([1, 1])
            with yc:
                st.number_input(
                    "Yıl",
                    min_value=2025, max_value=2100, step=1,
                    key="prd_year"
                )

            with mc:
                st.selectbox(
                    "Ay",
                    options=list(range(1, 13)),
                    format_func=lambda m: TR_MONTHS[m - 1],
                    key="prd_month"
                )

            y = int(st.session_state["prd_year"])
            m = int(st.session_state["prd_month"])
            month_first_day, month_end_day = self._month_bounds(y, m)
            date_from = month_first_day
            date_to = month_end_day + _dt.timedelta(days=1)
            st.markdown(f"🔎 Seçilen ay: **{month_first_day:%d.%m.%Y} – {month_end_day:%d.%m.%Y}**")

        return date_from, date_to, mode

    # ---------- Kart ----------
    def render_filter_card(self):
        apply_pending_clear()

        # Listeler tanımlanır
        branch_ids = []
        department_ids = []
        group_ids = []
        machine_ids = []
        branch_contract = []

        if "result_df" not in st.session_state:
            st.session_state["result_df"] = pd.DataFrame()

        current_page = st.session_state.get("active_page", "production_report")

        st.markdown('<div class="filter-card">', unsafe_allow_html=True)
        st.markdown('<h3>🔧 Filtreler</h3>', unsafe_allow_html=True)

        # Sol: şube/departman/grup/makine – Sağ: tarih
        left, right = st.columns([1.1, 1.2])
        with left:
            if current_page == "manual_production_report" or current_page == "transaction_report":
                branch_contract, _     = self.render_branch_contract_filter()
            else:
                branch_ids, _     = self.render_branch_filter()
                department_ids, _ = self.render_department_filter(branch_ids)
                group_ids, _      = self.render_group_filter(department_ids)
                machine_ids       = self.render_machine_filter(branch_ids, department_ids, group_ids)

        with right:
            date_from, date_to, mode = self.render_date_column()

        st.markdown("</div>", unsafe_allow_html=True)

        # Aksiyonlar
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("✖️ Temizle", use_container_width=True, key="filter_clear_btn"):
                # Temizleme işini sizin session_helper.schedule_clear yönetiyor
                schedule_clear()
                st.rerun()

        with c2:
            if st.button("✅ Uygula", type="primary", use_container_width=True, key="filter_apply_btn"):
                try:
                    if current_page == "production_report":
                        if mode == "Gün":
                            data = ProductionService.get_daily_production_report(date_from, date_to, branch_ids, department_ids, group_ids, machine_ids)
                        elif mode == "Hafta":
                            data = ProductionService.get_weekly_production_report(date_from, date_to, branch_ids, department_ids, group_ids, machine_ids)
                        elif mode == "Ay":
                            data = ProductionService.get_monthly_production_report(date_from, date_to, branch_ids, department_ids, group_ids, machine_ids)
                        st.session_state["production_df"] = data
                    elif current_page == "manual_label_report":
                        if mode == "Gün":
                            data = ManualLabelService.get_daily_manual_label_report(date_from, date_to, branch_ids, department_ids, group_ids, machine_ids)
                        elif mode == "Hafta":
                            data = ManualLabelService.get_weekly_manual_label_report(date_from, date_to, branch_ids, department_ids, group_ids, machine_ids)
                        elif mode == "Ay":
                            data = ManualLabelService.get_monthly_manual_label_report(date_from, date_to, branch_ids, department_ids, group_ids, machine_ids)
                        st.session_state["manual_label_df"] = data
                    elif current_page == "boxing_report":
                        if mode == "Gün":
                            data = BoxingReportService.get_daily_boxing_report(date_from, date_to, branch_ids, department_ids, group_ids, machine_ids)
                        elif mode == "Hafta":
                            data = BoxingReportService.get_weekly_boxing_report(date_from, date_to, branch_ids, department_ids, group_ids, machine_ids)
                        elif mode == "Ay":
                            data = BoxingReportService.get_monthly_boxing_report(date_from, date_to, branch_ids, department_ids, group_ids, machine_ids)
                        st.session_state["boxing_report_df"] = data
                    elif current_page == "manual_production_report":
                        st.session_state["manual_production_df"] = ManualProductionService.get_manuel_production_report(date_from, date_to, branch_contract, mode)
                    elif current_page == "transaction_report":
                        st.session_state["transaction_df"] = TransactionService.get_transaction_report(date_from, date_to, branch_contract, mode)
                except Exception as e:
                    st.error(f"Veri alınırken hata: {e}")

        # Sayfa tarafında kullanmak için dönen parametreler
        return {
            "branch_ids": branch_ids,
            "branch_contract" : branch_contract,
            "department_ids": department_ids,
            "group_ids": group_ids,
            "machine_ids": machine_ids,
            "date_from": date_from,
            "date_to": date_to,
            "mode" : mode
        }
