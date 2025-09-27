import streamlit as st
import pandas as pd
from components.filters import FilterComponent
from components.Alert.manual_production_data_display import render_period_lines
from utils.session_helper import apply_pending_clear

def render_manuel_production_report_page():
    st.markdown("## 🔎 MANUEL ÜRETİM RAPORU")
    st.markdown("Şube seçimi yaparak üretim raporlarını görüntüleyin.")

    # -- FİLTRE KARTI --
    filt = FilterComponent()
    result = filt.render_filter_card()

    # -- SONUÇLAR --
    # Session state'ten veriyi al
    df = st.session_state.get("manual_production_df", pd.DataFrame())

    render_period_lines(df, result["mode"])