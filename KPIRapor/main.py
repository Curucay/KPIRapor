import streamlit as st
import pandas as pd
from config.settings import settings
from components.navigation import Navigation
from styles.theme import get_custom_css
from pages.Alert.production_report import render_production_report_page
from pages.Alert.manual_label_report import render_manual_label_report_page
from pages.Alert.boxing_report import render_boxing_report_page
from pages.Alert.manual_production_report import render_manuel_production_report_page
from pages.Alert.transaction_report import render_transaction_report_page
from utils.session_helper import clear_on_page_change

def main():
    # Sayfa konfigürasyonu
    st.set_page_config(
        page_title=settings.PAGE_TITLE,
        page_icon=settings.PAGE_ICON,
        layout=settings.LAYOUT,
        initial_sidebar_state="expanded"
    )

    # Pandas ayarları
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 2000)

    # Özel CSS
    st.markdown(get_custom_css(), unsafe_allow_html=True)

    # Navigasyon
    selected_page = Navigation.render_sidebar()

    clear_on_page_change(selected_page)

    # Sayfa yönlendirme
    if selected_page == "production_report":
        render_production_report_page()
    elif selected_page == "manual_label_report":
        render_manual_label_report_page()
    elif selected_page == "boxing_report":
        render_boxing_report_page()
    elif selected_page == "manual_production_report":
        render_manuel_production_report_page()
    elif selected_page == "transaction_report":
        render_transaction_report_page()



if __name__ == "__main__":
    main()