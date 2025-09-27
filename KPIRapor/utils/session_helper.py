# utils/session_helper.py
import streamlit as st
import pandas as pd

def schedule_clear(prefix: str = ""):
    """Temizlemeyi bir sonraki run'a planla ve rerun et (butonlar için)."""

    st.session_state[f"{prefix}__pending_clear"] = True

def apply_pending_clear(prefix: str = ""):
    flag = st.session_state.get(f"{prefix}__pending_clear")
    if not flag:
        return

    st.session_state.pop(f"{prefix}__pending_clear", None)
    st.session_state[f"{prefix}branch_ms"] = []
    st.session_state[f"{prefix}machine_ms"] = []
    st.session_state[f"{prefix}quick_search"] = ""

    # dataframe’leri temizle
    if "production_df" in st.session_state:
        st.session_state["production_df"] = pd.DataFrame()
    if "shop_order_df" in st.session_state:
        st.session_state["shop_order_df"] = pd.DataFrame()
    if "machine_printer_df" in st.session_state:
        st.session_state["machine_printer_df"] = pd.DataFrame()

def clear_on_page_change(selected_page: str):
    """
    Sayfa değişiminde, ilgili prefix'ler için temizleme planlar ve rerun eder.
    """
    prev = st.session_state.get("_active_page")
    if prev != selected_page:
        st.session_state["__pending_clear"] = True
        st.session_state["_active_page"] = selected_page
        st.rerun()


def clear_on_page_dataframe(dataframe_name: str):
    """
    Sayfa içerisinde ki, ilgili takvim de farklı seçimlerde dataframe temizle yapılır.
    """
    if st.session_state.get("__skip_apply_clear"):
        # Sadece bu rerun'ı atla, sonra bayrağı temizle
        st.session_state["__skip_apply_clear"] = False
        return
    # dataframe’leri temizle
    if dataframe_name in st.session_state:
        st.session_state[dataframe_name] = pd.DataFrame()

def mark_skip_clear_once():
    """
    Bir sonraki rerun için apply_pending_clear'ı tek seferlik devre dışı bırakır.
    """
    st.session_state["__skip_apply_clear"] = True