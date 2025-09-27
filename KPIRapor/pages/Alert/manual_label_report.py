import streamlit as st
import pandas as pd
from components.filters import FilterComponent
from components.Alert.manual_label_data_display import render_daily_bars
from components.Alert.manual_label_data_display import render_period_bars
from components.Alert.manual_label_data_display import render_period_lines
from database.services.manual_label_service import ManualLabelService
from utils.session_helper import apply_pending_clear

def render_manual_label_report_page():
    st.markdown("## 🏷️ MANUEL ETİKET RAPORU")
    st.markdown("Şube, departman ve makine seçimi yaparak üretim raporlarını görüntüleyin.")

    # -- FİLTRE KARTI --
    filt = FilterComponent()
    result = filt.render_filter_card()

    # -- SONUÇLAR --
    # Session state'ten veriyi al
    df = st.session_state.get("manual_label_df", pd.DataFrame())

    if result["mode"] == "Gün":
        render_daily_bars(
            df,
            show_table=True,
        )
    elif result["mode"] == "Hafta":
        render_period_bars(
            df,
            period_col="Hafta",
            x_col="Gun",
            x_title="Gün",
            show_table=True
        )
    elif result["mode"] == "Ay":
        render_period_bars(
            df,
            period_col="Ay",
            x_col="Hafta",
            x_title="Hafta",
            show_table=True
        )




