import io
from datetime import datetime
import pandas as pd
import streamlit as st
import altair as alt

# =========================
#  Sabitler / Renkler
# =========================

HIER_ORDER   = ["Site", "Departman", "Bolum", "Makine"]

LINE_COLORS = {
    "Toplam Tutar": "#1F77B4",
}

EMPTY_MSG = "Gösterilecek veri yok."

# =========================
# Genel Yardımcılar
# =========================
def _check_df_empty(df: pd.DataFrame) -> bool:
    if df.empty:
        st.info(EMPTY_MSG)
        return True
    return False

def _resolve_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Verilen aday kolonlardan mevcut olan ilkini döndür."""
    for c in candidates:
        if c in df.columns:
            return c
    return None

def _hier_groups(df: pd.DataFrame):
    dims = [c for c in HIER_ORDER if c in df.columns]
    if not dims:
        yield {}, df
    else:
        for keys, g in df.groupby(dims, dropna=False):
            if not isinstance(keys, tuple):
                keys = (keys,)
            yield dict(zip(dims, keys)), g

def _group_title(meta: dict, extra: str | None = None) -> str:
    parts: list[str] = []
    if "Bolum" in meta and pd.notna(meta["Bolum"]):
        parts.append(str(meta["Bolum"]))
    if extra:
        parts.append(str(extra))
    tail = [k for k in ["Site", "Departman", "Makine"] if k in meta and pd.notna(meta[k])]
    if tail:
        parts.append(" / ".join(str(meta[k]) for k in tail))
    return " – ".join(parts) if parts else (extra or "")

def _dowload_button(df: pd.DataFrame, filename_prefix: str = "manuel_üretim"):
    """Altta tablo ve Excel indirme düğmesi."""
    st.markdown("#### Özet Tablo")
    st.dataframe(df, use_container_width=True)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
        df.to_excel(w, index=False, sheet_name="Özet")

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    st.download_button(
        "📥 Excel indir",
        data=buf.getvalue(),
        file_name=f"{filename_prefix}_{ts}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# =========================
#  Dönüşümler
# =========================
def _prep_agg(df: pd.DataFrame, x_col: str, cols: list[str]) -> pd.DataFrame:
    """X ekseni (Gun/Hafta) bazında cols kolonlarının toplamı + düzgün etiket döndürür."""
    col = _resolve_col(df, [x_col, "Gün", "Gun"])  # 'Gün'/'Gun' otomatik
    if col is None:
        return pd.DataFrame(columns=["_etiket"] + cols)

    work = df.copy()
    if col in ("Gün", "Gun"):
        work[col] = pd.to_datetime(work[col], errors="coerce")
        agg = (work.groupby(col, as_index=False)[[c for c in cols if c in work.columns]]
                    .sum().sort_values(col))
        agg["_etiket"] = agg[col].dt.strftime("%Y-%m-%d")
    else:
        agg = (work.groupby(col, as_index=False)[[c for c in cols if c in work.columns]]
                    .sum().sort_values(col))
        agg["_etiket"] = agg[col].astype(str)
    return agg

def _prep_totals_long(df: pd.DataFrame, x_col: str) -> pd.DataFrame:
    """Çizgi grafik için sadece Toplam Tutar serisini hazırlar: ['_etiket','Seri','Deger']"""
    agg = _prep_agg(df, x_col=x_col, cols=["Tutar"])
    if agg.empty or "Tutar" not in agg.columns:
        return pd.DataFrame(columns=["_etiket", "Seri", "Deger"])
    agg["Tutar"] = pd.to_numeric(agg["Tutar"], errors="coerce").fillna(0)
    out = agg.rename(columns={"Tutar": "Deger"})[["_etiket", "Deger"]].copy()
    out["Seri"] = "Toplam Tutar"
    # Sıra korunsun
    return out[["_etiket", "Seri", "Deger"]]

# =========================
#  Grafikler
# =========================
def _line_chart(long_df: pd.DataFrame, *, title: str | None, x_title: str, height: int = 360):
    """Toplam Tutar dağılımı çizgi grafiği."""
    if long_df.empty:
        st.info(EMPTY_MSG)
        return

    n = long_df["_etiket"].nunique()
    step_px = 90 if n <= 6 else max(60, int(900 / max(n, 1)))

    domain = list(LINE_COLORS.keys())
    range_ = [LINE_COLORS[k] for k in domain if k in LINE_COLORS]

    base = alt.Chart(long_df).encode(
        x=alt.X(
            "_etiket:N",
            title=x_title,
            axis=alt.Axis(labelAngle=0, labelLimit=10000, labelPadding=10),
        ),
        y=alt.Y("Deger:Q", title="Tutar (₺)"),
        color=alt.Color(
            "Seri:N",
            scale=alt.Scale(domain=domain, range=range_),
            legend=alt.Legend(orient="top", direction="horizontal", title=None),
        ),
        tooltip=[
            alt.Tooltip("_etiket:N", title=x_title),
            alt.Tooltip("Seri:N", title="Seri"),
            alt.Tooltip("Deger:Q", title="Tutar (₺)", format=",.0f"),
        ],
    )

    chart = (
        base.mark_line(point=True)
        + base.mark_text(align="center", baseline="bottom", dy=-6, size=14).encode(
            text=alt.Text("Deger:Q", format=",.0f")
        )
    ).properties(
        width=alt.Step(step_px),
        height=height,
        padding={"left": 10, "right": 10, "top": 30, "bottom": 60},
        title=title,
    ).configure_view(strokeOpacity=0)

    st.altair_chart(chart, use_container_width=True)

def _render_grouped(df: pd.DataFrame, period_col: str, x_col: str, x_title: str):
    """Site (ve varsa diğer hiyerarşik boyutlar) altında periyot kırılımına göre çiz."""
    if _check_df_empty(df):
        return

    if period_col and period_col in df.columns:
        # Örn: Ay -> period_col='Ay' ve x_col='Hafta' (her Ay kendi içinde hafta hafta)
        for meta, g in _hier_groups(df):
            for period_val, g_part in g.groupby(period_col, dropna=False):
                title = _group_title(meta, extra=str(period_val)) or str(period_val)
                long_df = _prep_totals_long(g_part, x_col=x_col)
                _line_chart(long_df, title=title, x_title=x_title)
    else:
        # Örn: Gün filtresi -> period yok; doğrudan gün gün
        for meta, g in _hier_groups(df):
            title = _group_title(meta) or ""
            long_df = _prep_totals_long(g, x_col=x_col)
            _line_chart(long_df, title=title, x_title=x_title)

    _dowload_button(df)

# =========================
#  Render Fonksiyonu
# =========================

def render_period_lines(df: pd.DataFrame, mode: str):
    """
    mode:
      - 'Gün'   => X: Gün,   periyot kırılımı yok (doğrudan gün/gün)
      - 'Hafta' => X: Gün,   periyot kırılımı: Hafta
      - 'Ay'    => X: Hafta, periyot kırılımı: Ay
    """
    mode = (mode or "").strip()
    if mode == "Gün":
        _render_grouped(df, x_col="Gun",    x_title="Gün",   period_col=None)
    elif mode == "Hafta":
        _render_grouped(df, x_col="Gun",    x_title="Gün",   period_col="Hafta")
    elif mode == "Ay":
        _render_grouped(df, x_col="Hafta",  x_title="Hafta", period_col="Ay")
    else:
        st.warning("Geçerli bir dönem seçiniz: Gün / Hafta / Ay")