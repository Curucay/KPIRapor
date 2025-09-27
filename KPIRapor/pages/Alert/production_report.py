import streamlit as st
import pandas as pd
from components.filters import FilterComponent
from components.Alert.production_data_display import render_daily_bars
from components.Alert.production_data_display import render_weekly_bars
from components.Alert.production_data_display import render_monthly_bars
from database.services.production_service import ProductionService
from utils.session_helper import apply_pending_clear

def render_production_report_page():
    st.markdown("## 📈 VARDİYA AŞAN ÜRETİM RAPORU")
    st.markdown("Şube, departman ve makine seçimi yaparak üretim raporlarını görüntüleyin.")

    # -- FİLTRE KARTI --
    filt = FilterComponent()
    result = filt.render_filter_card()

    # -- SONUÇLAR --
    # Session state'ten veriyi al
    df = st.session_state.get("production_df", pd.DataFrame())

    if result["mode"] == "Gün":
        render_daily_bars(
            df,
            show_table=True,
        )
    elif result["mode"] == "Hafta":
        render_weekly_bars(
            df,
            show_table=True
        )
    elif result["mode"] == "Ay":
        render_monthly_bars(
            df,
            show_table=True
        )


