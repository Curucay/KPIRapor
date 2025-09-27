import io
from datetime import datetime
import pandas as pd
import streamlit as st
import altair as alt

# =========================
#  Sabitler / Renkler
# =========================
SHIFT_SETS = {
    "uretim": ["Vardiya1ToplamUretim","Vardiya2ToplamUretim","Vardiya3ToplamUretim"],
    "kasa":   ["Vardiya1ToplamKasaDoldurmaAdet","Vardiya2ToplamKasaDoldurmaAdet","Vardiya3ToplamKasaDoldurmaAdet"],
    "eksik":  ["Vardiya1KasaDoldurulmayanAdet","Vardiya2KasaDoldurulmayanAdet","Vardiya3KasaDoldurulmayanAdet"],
}

HIER_ORDER   = ["Site", "Departman", "Bolum", "Makine"]
COLOR_DOMAIN = ("Vardiya 1", "Vardiya 2", "Vardiya 3")
COLOR_RANGE  = ("#1F77B4", "#2CA02C", "#F59E0B")  # 1= mavi, 2= yeşil, 3= amber

# Çizgi grafikte kullanılacak renkler
LINE_COLORS = {
    "Toplam Üretim Adet": "#1F77B4",
    "Toplam Kasa Doldurma": "#2CA02C",
    "Toplam Kasa Doldurulmayan": "#E45756",
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

def _hier_groups(df: pd.DataFrame):
    dims = [c for c in HIER_ORDER if c in df.columns]
    if not dims:
        yield {}, df
    else:
        for keys, g in df.groupby(dims, dropna=False):
            if not isinstance(keys, tuple):
                keys = (keys,)
            yield dict(zip(dims, keys)), g

def _dowload_button(df: pd.DataFrame, filename_prefix: str = "kasa_rapor"):
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
def _prep_totals_long(df: pd.DataFrame, x_col: str) -> pd.DataFrame:
    """
    Çizgi grafik için toplam serileri döndürür:
    ['_etiket','Seri','Deger']  (Seri: Toplam Üretim Adet / Toplam Kasa Doldurma / Toplam Kasa Doldurulmayan)
    """
    # Tüm vardiya kolonlarını tek seferde toplayalım
    cols_all = SHIFT_SETS["uretim"] + SHIFT_SETS["kasa"] + SHIFT_SETS["eksik"]
    agg = _prep_agg(df, x_col=x_col, cols=cols_all)
    if agg.empty:
        return pd.DataFrame(columns=["_etiket", "Seri", "Deger"])

    def ssum(cols: list[str]) -> pd.Series:
        exist = [c for c in cols if c in agg.columns]
        if not exist:
            return pd.Series(0, index=agg.index, dtype="float64")

        # Her kolonu ayrı ayrı sayıya çevir, sonra satır bazında topla
        return (
            agg[exist]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0)
            .sum(axis=1)
        )

    totals = pd.DataFrame({
        "_etiket": agg["_etiket"],
        "Toplam Üretim Adet":       ssum(SHIFT_SETS["uretim"]),
        "Toplam Kasa Doldurma":     ssum(SHIFT_SETS["kasa"]),
        "Toplam Kasa Doldurulmayan": ssum(SHIFT_SETS["eksik"]),
    })

    # Uzun forma çevir
    long_df = totals.melt(id_vars="_etiket", var_name="Seri", value_name="Deger")
    # Zaman/etikete göre sıralı kalsın
    return long_df.sort_values(["_etiket", "Seri"]).reset_index(drop=True)

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

def _prep_breakdown_long(df: pd.DataFrame, x_col: str) -> pd.DataFrame:
    """Vardiya bazında Kasa/Doldurulmayan breakdown için uzun form:
       ['_etiket','Vardiya','Tip','Adet'] + toplam."""
    kasa  = SHIFT_SETS["kasa"]
    eksik = SHIFT_SETS["eksik"]
    cols  = kasa + eksik

    agg = _prep_agg(df, x_col=x_col, cols=cols)
    if agg.empty:
        return pd.DataFrame(columns=["_etiket","Vardiya","Tip","Adet","Toplam"])

    pieces = []
    map_v = {1:"Vardiya 1", 2:"Vardiya 2", 3:"Vardiya 3"}
    for i in (1,2,3):
        k = kasa[i-1]
        e = eksik[i-1]
        sub = agg[["_etiket"]].copy()
        sub["Vardiya"] = map_v[i]
        sub["Kasa"]    = pd.to_numeric(agg.get(k, 0), errors="coerce").fillna(0)
        sub["Eksik"]   = pd.to_numeric(agg.get(e, 0), errors="coerce").fillna(0)
        pieces.append(sub)

    wide = pd.concat(pieces, ignore_index=True)
    long = wide.melt(id_vars=["_etiket","Vardiya"], value_vars=["Kasa","Eksik"],
                     var_name="Tip", value_name="Adet")
    totals = long.groupby(["_etiket","Vardiya"], as_index=False)["Adet"].sum().rename(columns={"Adet":"Toplam"})
    return long.merge(totals, on=["_etiket","Vardiya"], how="left")

# =========================
#  Grafikler
# =========================

def _stacked_bars(long_df: pd.DataFrame, *, title: str | None, x_title: str, height: int = 360):
    if _check_df_empty(long_df):
        return

    n_ticks = long_df["_etiket"].nunique()
    step_px = 110 if n_ticks <= 6 else max(60, int(900 / max(n_ticks, 1)))

    # 1) Barlar (x-ekseni gizli!)
    bars = (
        alt.Chart(long_df)
        .mark_bar()
        .encode(
            x=alt.X("_etiket:N", axis=None),  # <--- eksen yok
            xOffset=alt.XOffset("Vardiya:N", sort=["Vardiya 1","Vardiya 2","Vardiya 3"]),
            y=alt.Y("Adet:Q", title="Adet", stack="zero"),
            color=alt.Color("Tip:N",
                            legend=alt.Legend(orient="top", direction="horizontal", title="Tür")),
            tooltip=[
                alt.Tooltip("_etiket:N", title=x_title),
                alt.Tooltip("Vardiya:N", title="Vardiya"),
                alt.Tooltip("Tip:N",     title="Tür"),
                alt.Tooltip("Adet:Q",    title="Adet", format=",.0f"),
                alt.Tooltip("Toplam:Q",  title="Vardiya Toplamı", format=",.0f"),
            ],
        )
        .properties(width=alt.Step(step_px), height=height)
    )

    # 2) Vardiya bandı (V1 V2 V3)
    labels_df = (
        long_df[["_etiket", "Vardiya"]]
        .drop_duplicates()
        .assign(V=lambda d: d["Vardiya"].str.replace("Vardiya ", "V", regex=False))
    )
    labels = (
        alt.Chart(labels_df)
        .mark_text(
            fontWeight="bold",
            fontSize=12,
            align="center",
            baseline="top",
            dy=2,
            color="#e6e6e6")
        .encode(
            x=alt.X("_etiket:N", axis=None),
            xOffset=alt.XOffset("Vardiya:N", sort=["Vardiya 1","Vardiya 2","Vardiya 3"]),
            text="V:N"
        )
        .properties(width=alt.Step(step_px), height=22)
    )

    xaxis_df = long_df[["_etiket"]].drop_duplicates()
    date_axis = (
        alt.Chart(xaxis_df)
        .mark_point(opacity=0)
        .encode(
            x=alt.X("_etiket:N",
                    title=x_title,  # "Gün"
                    axis=alt.Axis(
                        labelAngle=0,
                        labelLimit=10000,
                        titlePadding=6,
                        labelPadding=8,
                        offset=-6))
        )
        .properties(width=alt.Step(step_px), height=28)
    )

    combo = (
        alt.vconcat(bars, labels, date_axis, spacing=2,
                    padding={"left":12, "right":10, "top":10, "bottom":10})
          .resolve_scale(x="shared")
          .configure_view(strokeOpacity=0)
    )
    if title:
        combo = combo.properties(title=title)

    st.altair_chart(combo, use_container_width=True)

def _line_chart(long_df: pd.DataFrame, *, title: str | None, x_title: str, height: int = 360):
    """Toplam Üretim/Kasa/Eksik dağılımı çizgi grafiği."""
    if long_df.empty:
        st.info(EMPTY_MSG)
        return

    n = long_df["_etiket"].nunique()
    step_px = 110 if n <= 6 else max(60, int(900 / max(n, 1)))

    domain = list(LINE_COLORS.keys())
    range_ = [LINE_COLORS[k] for k in domain if k in LINE_COLORS]

    base = alt.Chart(long_df).encode(
        x=alt.X(
            "_etiket:N",
            title=x_title,
            axis=alt.Axis(labelAngle=0, labelLimit=10000, labelPadding=10),
        ),
        y=alt.Y("Deger:Q", title="Adet"),
        color=alt.Color(
            "Seri:N",
            scale=alt.Scale(domain=domain, range=range_),
            legend=alt.Legend(orient="top", direction="horizontal", title=None),
        ),
        tooltip=[
            alt.Tooltip("_etiket:N", title=x_title),
            alt.Tooltip("Seri:N", title="Seri"),
            alt.Tooltip("Deger:Q", title="Adet", format=",.0f"),
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

def render_period_lines(df: pd.DataFrame, period_col: str, x_col: str, x_title: str):
    if _check_df_empty(df):
        return
    for meta, g in _hier_groups(df):
        if period_col not in g.columns:
            continue
        for period_val, g_part in g.groupby(period_col, dropna=False):
            title = _group_title(meta, extra=str(period_val)) or str(period_val)
            long_df = _prep_totals_long(g_part, x_col=x_col)
            _line_chart(long_df, title=title, x_title=x_title)

# =========================
#  Render (Gün / Hafta / Ay)
# =========================
def render_daily_bars(df: pd.DataFrame, show_table: bool = True):
    if _check_df_empty(df):
        return

    for meta, g in _hier_groups(df):
        title = _group_title(meta) or "Günlük (Vardiya Kırılımı)"
        long_ = _prep_breakdown_long(g, x_col="Gun")
        _stacked_bars(long_, title=title, x_title="Gün")

    if show_table:
        _dowload_button(df, filename_prefix="kasa_doldurma")


def render_weekly_bars(df: pd.DataFrame, show_table: bool = True):
    if _check_df_empty(df):
        return

    for meta, g in _hier_groups(df):
        if "Hafta" not in g.columns:
            continue
        for hafta, g_part in g.groupby("Hafta", dropna=False):
            title = _group_title(meta, extra=str(hafta))
            long_ = _prep_breakdown_long(g_part, x_col="Gun")
            _stacked_bars(long_, title=title, x_title="Gün")

    render_period_lines(df, period_col="Hafta", x_col="Gun", x_title="Gün")

    if show_table:
        _dowload_button(df, filename_prefix="kasa_doldurma")

def render_monthly_bars(df: pd.DataFrame, show_table: bool = True):
    if _check_df_empty(df):
        return

    for meta, g in _hier_groups(df):
        if "Ay" not in g.columns:
            continue
        for ay, g_part in g.groupby("Ay", dropna=False):
            title = _group_title(meta, extra=str(ay))
            long_ = _prep_breakdown_long(g_part, x_col="Hafta")
            _stacked_bars(long_, title=title, x_title="Hafta")

    render_period_lines(df, period_col="Ay", x_col="Hafta", x_title="Hafta")

    if show_table:
        _dowload_button(df, filename_prefix="kasa_doldurma")
