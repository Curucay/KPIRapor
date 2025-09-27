import streamlit as st
from database.connection import get_db_info_from_conn
from config.settings import settings

class Navigation:
    MENU_STRUCTURE = {
        "🚨 Alarm Setleri": {
            "📈 Üretim Raporu": "production_report",
            "📊 Kasa Doldurma Raporu": "boxing_report",
            "🏷️ Manuel Etiket": "manual_label_report",
            "🔎 Manuel Üretim" : "manual_production_report",
            "🔁 Transaction" : "transaction_report"
        },
        #"📍 Lokasyon Tanımları": {
        #    "📦 Depo Raporları": "warehouse_reports",
        #    "📍 Konum Analizi": "location_analysis"
        #},
        #"📈 Raporlar": {
        #    "🔎 Soket Tanımları": "socket_definitions",
        #    "📊 İş Emri ": "shoporder_report",
        #    "🖨️ Yazıcı Tanımları": "printer_definitions",
        #    "📦 Envanter Raporu": "inventory_report"
        #}
    }

    @staticmethod
    def render_sidebar():
        with st.sidebar:
            st.markdown("""
                <div style="text-align: center; padding: 0; position: relative; top: -60px;">
                    <img src="data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPHN2ZyBpZD0iTGF5ZXJfMSIgZGF0YS1uYW1lPSJMYXllciAxIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZlcnNpb249IjEuMSIgeG1sbnM6eGxpbms9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkveGxpbmsiIHZpZXdCb3g9IjAgMCAxNTIgMzAuMSI+CiAgPGRlZnM+CiAgICA8c3R5bGU+CiAgICAgIC5jbHMtMSB7CiAgICAgICAgZmlsbDogdXJsKCNsaW5lYXItZ3JhZGllbnQpOwogICAgICB9CgogICAgICAuY2xzLTEsIC5jbHMtMiwgLmNscy0zLCAuY2xzLTQsIC5jbHMtNSB7CiAgICAgICAgc3Ryb2tlLXdpZHRoOiAwcHg7CiAgICAgIH0KCiAgICAgIC5jbHMtMiB7CiAgICAgICAgZmlsbDogIzAwMDsKICAgICAgfQoKICAgICAgLmNscy0zIHsKICAgICAgICBmaWxsOiAjNDE0MDQyOwogICAgICB9CgogICAgICAuY2xzLTQgewogICAgICAgIGZpbGw6IHVybCgjbGluZWFyLWdyYWRpZW50LTIpOwogICAgICB9CgogICAgICAuY2xzLTUgewogICAgICAgIGZpbGw6ICMyMzFmMjA7CiAgICAgIH0KICAgIDwvc3R5bGU+CiAgICA8bGluZWFyR3JhZGllbnQgaWQ9ImxpbmVhci1ncmFkaWVudCIgeDE9Ijk2MS40IiB5MT0iMTk3LjgiIHgyPSIxMDA2LjciIHkyPSIxOTcuOCIgZ3JhZGllbnRUcmFuc2Zvcm09InRyYW5zbGF0ZSgxMTEzLjQgLTE3Mykgcm90YXRlKC0xODApIHNjYWxlKDEgLTEpIiBncmFkaWVudFVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+CiAgICAgIDxzdG9wIG9mZnNldD0iMCIgc3RvcC1jb2xvcj0iIzAwMCIvPgogICAgICA8c3RvcCBvZmZzZXQ9Ii43IiBzdG9wLWNvbG9yPSIjZjY4OTRjIi8+CiAgICA8L2xpbmVhckdyYWRpZW50PgogICAgPGxpbmVhckdyYWRpZW50IGlkPSJsaW5lYXItZ3JhZGllbnQtMiIgeDE9IjU4My42IiB5MT0iMTk3LjgiIHgyPSI2MjkiIHkyPSIxOTcuOCIgZ3JhZGllbnRUcmFuc2Zvcm09InRyYW5zbGF0ZSgtNTMxLjYgLTE3MykiIGdyYWRpZW50VW5pdHM9InVzZXJTcGFjZU9uVXNlIj4KICAgICAgPHN0b3Agb2Zmc2V0PSIwIiBzdG9wLWNvbG9yPSIjMDAwIi8+CiAgICAgIDxzdG9wIG9mZnNldD0iLjciIHN0b3AtY29sb3I9IiNmNjg5NGMiLz4KICAgIDwvbGluZWFyR3JhZGllbnQ+CiAgPC9kZWZzPgogIDxnPgogICAgPHBhdGggY2xhc3M9ImNscy0yIiBkPSJNNTEuOCw5LjNoLTUuOGMtLjEsMC0uMiwwLS4zLjFzLS4xLjItLjEuM3YxNS42YzAsLjIuMi40LjQuNGgzLjRjLjIsMCwuNC0uMi40LS40di0zLjZjMC0uNS40LS45LjktLjloMS4xYy4yLDAsLjQtLjIuNC0uNHYtMWMwLS4yLS4yLS40LS40LS40aC0xLjFjLS41LDAtLjktLjQtLjktLjl2LTZjMC0uNS40LS45LjktLjloMS4xYy4yLDAsLjQtLjIuNC0uNHYtMWMwLS4yLS4yLS40LS40LS40WiIvPgogICAgPHBhdGggY2xhc3M9ImNscy0yIiBkPSJNNzUuOCw5LjNoLTcuM2MtLjUsMC0uOS40LS45Ljl2OS43YzAsLjUuNC45LjkuOWgyLjRjLjUsMCwuOS0uNC45LS45di03LjRjMC0uOC43LTEuNCwxLjQtMS40aDIuNmMuNSwwLC45LS40LjktLjlzLS40LS45LS45LS45WiIvPgogICAgPHBhdGggY2xhc3M9ImNscy0yIiBkPSJNOTYuNCw5LjNoLTE3Yy0uNSwwLTEsLjQtMSwxdjkuNmMwLC41LjQsMSwxLDFoMi40Yy41LDAsMS0uNCwxLTF2LTcuMmMwLS44LjctMS41LDEuNS0xLjVzMS41LjcsMS41LDEuNXY3LjJjMCwuNS40LDEsMSwxaDIuM2MuNiwwLDEtLjQsMS0xdi03LjJjMC0uOC43LTEuNSwxLjUtMS41czEuNS43LDEuNSwxLjV2Ny4yYzAsLjUuNCwxLDEsMWgyLjNjLjUsMCwxLS40LDEtMXYtOS42YzAtLjUtLjQtMS0xLTFoMFoiLz4KICAgIDxwYXRoIGNsYXNzPSJjbHMtMiIgZD0iTTEwNS4yLDkuM2gtNS41Yy0uMiwwLS4zLDAtLjQuMnMtLjIuMy0uMi40djE1LjJjMCwuMy4zLjYuNi42aDNjLjMsMCwuNi0uMy42LS42di0zLjJjMC0uNi41LTEuMSwxLjEtMS4xaC43Yy4zLDAsLjYtLjMuNi0uNnYtLjZjMC0uMy0uMy0uNi0uNi0uNmgtLjdjLS42LDAtMS4xLS41LTEuMS0xLjF2LTUuNmMwLS42LjUtMS4xLDEuMS0xLjFoLjdjLjMsMCwuNi0uMy42LS42di0uNmMwLS4zLS4zLS42LS42LS42aDBaIi8+CiAgICA8cGF0aCBjbGFzcz0iY2xzLTIiIGQ9Ik0xMjQuMyw5LjNoLTkuN2MtLjUsMC0uOS40LS45Ljl2OS43YzAsLjUuNC45LjkuOWg5LjdjLjUsMCwuOS0uNC45LS45cy0uNC0uOS0uOS0uOWgtNWMtLjgsMC0xLjQtLjYtMS40LTEuNHMuNy0xLjUsMS40LTEuNWg1Yy41LDAsLjktLjQuOS0uOXYtNWMwLS41LS40LS45LS45LS45aDBaTTEyMSwxNC4xaC0zdi0yLjloM3YyLjlaIi8+CiAgICA8cGF0aCBjbGFzcz0iY2xzLTIiIGQ9Ik0xMzcuNiw5LjNoLTIuM2MtLjYsMC0xLC40LTEsMXYyLjNjMCwuOC0uNywxLjUtMS41LDEuNXMtMS41LS43LTEuNS0xLjV2LTcuMmMwLS42LS40LTEtMS0xaC0yLjJjLS42LDAtMSwuNC0xLDF2MTQuNGMwLC42LjQsMSwxLDFoMi4yYy42LDAsMS0uNSwxLTF2LTIuMmMwLS44LjctMS41LDEuNS0xLjVzMS41LjcsMS41LDEuNXYyLjJjMCwuNi40LDEsMSwxaDIuM2MuNiwwLDEtLjUsMS0xdi0yLjJjMC0uNi0uNC0xLTEtMWgtMi4zYy0uOCwwLTEuNS0uNy0xLjUtMS41cy43LTEuNSwxLjUtMS41aDIuM2MuNiwwLDEtLjQsMS0xdi0yLjNjMC0uNi0uNC0xLTEtMWgwWiIvPgogICAgPHBhdGggY2xhc3M9ImNscy0yIiBkPSJNMTUxLjEsMTRoLTVjLS44LDAtMS40LS42LTEuNC0xLjRzLjYtMS41LDEuNC0xLjVoNWMuNSwwLC45LS40LjktLjlzLS40LS45LS45LS45aC05LjdjLS41LDAtLjkuNC0uOS45djQuOWMwLC41LjQuOS45LjloNC45Yy44LDAsMS40LjYsMS40LDEuNGgwYzAsLjktLjYsMS41LTEuNCwxLjVoLTQuOWMtLjUsMC0uOS40LS45LjlzLjQuOS45LjloOS43Yy41LDAsLjktLjQuOS0uOXYtNWMwLS41LS40LS45LS45LS45aDBaIi8+CiAgICA8cGF0aCBjbGFzcz0iY2xzLTEiIGQ9Ik0xNTEuMiwyNS43aC00My42Yy0uNSwwLS45LS40LS45LS45aDBjMC0uNS40LS45LjktLjloNDMuNmMuNSwwLC45LjQuOS45aDBjMCwuNS0uNC45LS45LjlaIi8+CiAgICA8cGF0aCBjbGFzcz0iY2xzLTQiIGQ9Ik01Mi45LDI1LjdoNDMuNmMuNSwwLC45LS40LjktLjloMGMwLS41LS40LS45LS45LS45aC00My42Yy0uNSwwLS45LjQtLjkuOWgwYzAsLjUuNC45LjkuOVoiLz4KICAgIDxwYXRoIGNsYXNzPSJjbHMtMiIgZD0iTTU1LjcsMjAuOWg4LjRjLjksMCwxLjYtLjcsMS42LTEuNnYtOC40YzAtLjktLjctMS42LTEuNi0xLjZoLTguNGMtLjksMC0xLjYuNy0xLjYsMS42djguNGMwLC45LjcsMS42LDEuNiwxLjZoMFpNNTguMywxMS4yaDMuMXY3LjdoLTMuMXYtNy43WiIvPgogICAgPHJlY3QgY2xhc3M9ImNscy0yIiB4PSIxMDcuNyIgeT0iNC40IiB3aWR0aD0iNC4yIiBoZWlnaHQ9IjE2LjQiIHJ4PSIxIiByeT0iMSIvPgogIDwvZz4KICA8Zz4KICAgIDxnPgogICAgICA8cGF0aCBjbGFzcz0iY2xzLTUiIGQ9Ik0zOC41LDEwLjFsLTEuOC0xLjktLjUtMS42cy0uNy0uMy0xLjMsMGgwczAsMCwwLDBoMHMwLDAsMCwwbC0yLjUsMy45Yy0uNC42LTEuMS42LTEuNi4xbC0uMi0uMi0uMi0xLjFzLS45LS42LTEuNS4xaDBzMCwwLDAsMGwtLjgsMS4yYy0uMi4zLS4xLjcuMS45bDEuMiwxLjFjLjUuNS43LDEuNC4zLDIuMWwtNS4xLDcuOGMtLjUuNy0xLjQuOS0yLC40bC0uOS0uN3YtLjVjLjEsMC0uNS0uMy0xLjIsMCwwLDAsMCwwLS4xLDBoMHMwLDAtLjEuMWwtMSwxLjVjLS4yLjMtLjIuOC4xLDFsNy40LDUuM2gwcy4xLDAsLjEsMGgwczAsMCwwLDBoMGMuMiwwLDEsLjIsMS40LS4xbDEwLjMtMTgtLjItLjQuMy0uNmMuMS0uMiwwLS42LDAtLjhoMFoiLz4KICAgICAgPHBhdGggY2xhc3M9ImNscy01IiBkPSJNMTYuNCwxOC4yYy0uMi0uNS0uMi0xLjIuMi0xLjdsNi04Yy41LS42LDEuNC0uNywyLDBsMS4zLDEuMmMuMS4xLjIuMi40LjJoMHMuNy4zLDEuNCwwbC0uMi0xLjF2LS4yYy4zLS4zLjMtLjcsMC0uOWwtNC0zLjktMi43LTMuM2gwYzAtLjEtLjYtLjQtMS4zLS4xLDAsMC0uMSwwLS4yLjFoMHMwLDAsMCwwTC4yLDIzYy0uMy40LS4yLDEsLjIsMS4ybDYuNCwzLjhjMCwwLC4xLDAsLjIsMGgwczEuMy4zLDEuOS0uMmMuMi0uMiwwLS41LS4zLS45bDMuOC01Yy42LS44LDEuNy0xLDIuNS0uNGwxLjYsMS4yczAsMCwwLDBoMHMuNy41LDEuNywwdi0uN2wxLjEtMS42LTMuMS0yLjNoMFoiLz4KICAgIDwvZz4KICAgIDxnPgogICAgICA8cGF0aCBjbGFzcz0iY2xzLTMiIGQ9Ik0yOC40LDcuNUwyMS4yLjNoMGMtLjEtLjEtLjMtLjItLjUtLjItLjIsMC0uMywwLS41LjJMMS4yLDIzYy0uMy40LS4yLDEsLjIsMS4ybDYuNCwzLjhjLjQuMiwxLC4xLDEuMi0uM2w0LjQtNS44Yy42LS44LDEuNy0xLDIuNS0uNGwxLjYsMS4yYy4zLjIuOC4xLDEtLjJsMS0xLjVjLjItLjMuMi0uOC0uMS0xbC0xLjYtMS4yYy0uOC0uNi0uOS0xLjYtLjQtMi40bDYtOGMuNS0uNiwxLjQtLjcsMiwwbDEuMywxLjJjLjMuMi42LjIuOCwwbC45LTEuMmMuMi0uMy4xLS43LS4xLS45aDBaIi8+CiAgICAgIDxwYXRoIGNsYXNzPSJjbHMtMyIgZD0iTTIwLjIsMjQuNmw3LjQsNS4zaDBjLjEsMCwuMy4xLjQsMCwuMSwwLC4zLS4yLjQtLjNsMTEuMi0xOC44Yy4xLS4yLDAtLjYsMC0uOGwtMy0zLjNjLS4yLS4yLS41LS4yLS43LDBsLTIuNSwzLjljLS40LjYtMS4xLjYtMS42LjFsLTEuMi0xLjJjLS4yLS4yLS42LS4yLS44LDBsLS44LDEuMmMtLjIuMy0uMS43LjEuOWwxLjIsMS4xYy41LjUuNywxLjQuMywyLjFsLTUuMSw3LjhjLS41LjctMS40LjktMiwuNGwtMS40LTEuMWMtLjMtLjItLjctLjEtMSwuMmwtMSwxLjVjLS4yLjMtLjIuOC4xLDFoMFoiLz4KICAgIDwvZz4KICA8L2c+Cjwvc3ZnPg==" 
                         style="width: 200px; height: auto; margin-bottom: 0.5rem;" 
                         alt="Formfleks">
                </div>
            """, unsafe_allow_html=True)

            selected_page = st.session_state.get("active_page", None)

            for category_name, items in Navigation.MENU_STRUCTURE.items():
                with st.expander(category_name, expanded=True if "Alarm Setleri" in category_name else False):
                    for item_name, item_key in items.items():
                        if st.button(
                                f"  {item_name}",
                                key=f"nav_{item_key}_{category_name}",
                                use_container_width=True
                        ):
                            # 1) Hedef sayfayı ata
                            st.session_state["active_page"] = item_key
                            # 2) Sayfa değişiminde filtreleri sıfırla (prefixsiz kullanıyoruz)
                            st.session_state["__pending_clear"] = True
                            # 3) Top-level rerun
                            st.rerun()
                    if selected_page is None:
                        st.session_state["active_page"] = "production_report"

        return st.session_state["active_page"]


