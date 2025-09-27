import io
from datetime import datetime
import pandas as pd
import streamlit as st
import altair as alt

# Stacked bar serileri
SHIFT_COLS = ["Vardiya1Toplam", "Vardiya2Toplam", "Vardiya3Toplam"]

# Hiyerarşi sırası (varsa olanları kullanır)
HIER_ORDER = ["Site", "Departman", "Bolum", "Makine"]

# Altair renk ve sıralama sabitleri
DEFAULT_SHIFT_ORDER = ("Vardiya 1", "Vardiya 2", "Vardiya 3")
DEFAULT_SHIFT_COLORS = {
    "Vardiya 1": "#1F77B4",
    "Vardiya 2": "#2CA02C",
    "Vardiya 3": "#F59E0B",
}

# DF kontrol mesajı
EMPTY_MSG = "Gösterilecek veri yok."

# --------------------------
# Genel yardımcılar
# --------------------------
def _check_df_empty(df):
    if df.empty:
        st.info(EMPTY_MSG)
        return True
    return False

def _axis_prep(df: pd.DataFrame, x_col: str) -> pd.DataFrame:
    """
    X eksenine göre vardiya kolonlarını toplar + temiz label üretir.
    x_col: "Gun" (YYYY-MM-DD) ya da "Hafta" (YYYY-WW)
    """
    if x_col not in df.columns:
        return pd.DataFrame(columns=["_x_label"] + SHIFT_COLS)

    tmp = df.copy()

    if x_col == "Gun":
        # günleri tarihe çevirip sırala
        tmp[x_col] = pd.to_datetime(tmp[x_col], errors="coerce")
        agg = (
            tmp.groupby(x_col, as_index=False)[SHIFT_COLS]
               .sum()
               .sort_values(x_col)
        )
        agg["_x_label"] = agg[x_col].dt.strftime("%Y-%m-%d")
    else:
        # Hafta gibi string/period gelebilir: direkt topla + sırala
        agg = (
            tmp.groupby(x_col, as_index=False)[SHIFT_COLS]
               .sum()
               .sort_values(x_col)
        )
        agg["_x_label"] = agg[x_col].astype(str)

    return agg


def _to_long_from_agg(agg: pd.DataFrame) -> pd.DataFrame:
    """
    _axis_prep çıktısını (agg) long-form’a çevirir:
    kolonlar -> ["_etiket","Kategori","Adet","Toplam"]
    """
    if agg.empty:
        return pd.DataFrame(columns=["_etiket", "Kategori", "Adet", "Toplam"])

    # Etiket sütunu
    long_df = agg.melt(
        id_vars=["_x_label"],
        value_vars=[c for c in SHIFT_COLS if c in agg.columns],
        var_name="_var",
        value_name="Adet",
    ).rename(columns={"_x_label": "_etiket"})

    # Kategori isimleri
    name_map = {
        "Vardiya1Toplam": "Vardiya 1",
        "Vardiya2Toplam": "Vardiya 2",
        "Vardiya3Toplam": "Vardiya 3",
    }
    long_df["Kategori"] = long_df["_var"].map(name_map).fillna(long_df["_var"])
    long_df.drop(columns=["_var"], inplace=True)

    # Nümerik güvenliği
    long_df["Adet"] = pd.to_numeric(long_df["Adet"], errors="coerce").fillna(0)

    # Toplam (tooltip için)
    totals = long_df.groupby("_etiket", as_index=False)["Adet"].sum().rename(columns={"Adet": "Toplam"})
    long_df = long_df.merge(totals, on="_etiket", how="left")

    return long_df

def _stacked_bars_generic_altair(
    long_df: pd.DataFrame,
    *,
    title: str | None,
    x_title: str,
    height: int = 380,
) -> None:
    """
    Altair ile stacked bar (genel). Streamlit'te çizer.
    long_df kolonları: ["_etiket","Kategori","Adet","Toplam"]
    """
    if _check_df_empty(long_df):
        return

    # Domain-range
    domain = list(DEFAULT_SHIFT_ORDER)
    range_ = [DEFAULT_SHIFT_COLORS.get(cat, "#999999") for cat in domain]

    # X genişliği dinamik
    n_bars = long_df["_etiket"].nunique()
    step_px = 110 if n_bars <= 6 else max(60, int(900 / max(n_bars, 1)))

    tooltip_fields = [
        alt.Tooltip("_etiket:N", title=x_title),
        alt.Tooltip("Toplam:Q",  title="Toplam", format=",.0f"),
        alt.Tooltip("Adet:Q",    title="Adet",   format=",.0f"),
        alt.Tooltip("Kategori:N", title="Vardiya"),
    ]

    chart = (
        alt.Chart(long_df)
        .mark_bar()
        .encode(
            x=alt.X("_etiket:N",
                    title=x_title,
                    axis=alt.Axis(labelAngle=0, labelLimit=10000, labelPadding=10)),
            y=alt.Y("Adet:Q", title="Adet", stack="zero"),
            color=alt.Color("Kategori:N",
                            scale=alt.Scale(domain=domain, range=range_),
                            legend=alt.Legend(orient="top", direction="horizontal", title="Vardiya")),
            order=alt.Order("Kategori:N"),
            tooltip=tooltip_fields,
        )
    )

    props = dict(
        width=alt.Step(step_px),
        height=height,
        padding={"left": 10, "right": 10, "top": 10, "bottom": 60},
    )
    if title:
        props["title"] = title

    chart = chart.properties(**props).configure_view(strokeOpacity=0)
    st.altair_chart(chart, use_container_width=True)


def _stacked_bars(agg: pd.DataFrame, title: str, x_title: str):
    long_df = _to_long_from_agg(agg)
    _stacked_bars_generic_altair(long_df, title=title or None, x_title=x_title, height=360)


def _group_title(grp_vals: dict, extra: str | None = None) -> str:
    """Kart başlığı: 'Bölüm – 2025-36 / Site / Departman / (Makine)' benzeri."""
    parts = []
    if "Bolum" in grp_vals and pd.notna(grp_vals["Bolum"]):
        parts.append(str(grp_vals["Bolum"]))
    # ekstra bilgi (Hafta/Ay)
    if extra:
        parts.append(str(extra))
    # hiyerarşinin geri kalanını ekle
    tail = [k for k in ["Site", "Departman", "Makine"] if k in grp_vals and pd.notna(grp_vals[k])]
    if tail:
        parts.append(" / ".join(str(grp_vals[k]) for k in tail))
    return " – ".join(parts) if parts else (extra or "")


def _hierarchy_groups(df: pd.DataFrame):
    """
    Veride var olan hiyerarşi kolonlarına göre sıralı groupby yapar.
    Örn: Site → Departman → Bolum → Makine (var olanlara göre)
    """
    dims = [c for c in HIER_ORDER if c in df.columns]
    if not dims:
        yield {}, df
    else:
        for keys, g in df.groupby(dims, dropna=False):
            if not isinstance(keys, tuple):
                keys = (keys,)
            yield dict(zip(dims, keys)), g


def _dowload_button(df: pd.DataFrame, filename_prefix: str = "manuel_etiket_rapor"):
    st.markdown("#### Özet Tablo")
    st.dataframe(df, use_container_width=True)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Özet")

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    st.download_button(
        "📥 Excel indir",
        data=buffer.getvalue(),
        file_name=f"{filename_prefix}_{ts}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


# --------------------------
# Günlük / Haftalık / Aylık
# --------------------------
def render_daily_bars(df: pd.DataFrame, show_table: bool = True):
    """
    Günlük görünüm: X = Gün (gün/gün aralığı varsa çoklu gün),
    vardiyalar stacked bar. Hiyerarşi korunur.
    """
    if _check_df_empty(df):
        return

    for meta, g in _hierarchy_groups(df):
        title = _group_title(meta)
        agg = _axis_prep(g, x_col="Gun")
        _stacked_bars(agg, title=title or "Günlük", x_title="Gün")

    if show_table:
        _dowload_button(df, filename_prefix="manuel_etiket")


def render_period_bars(df: pd.DataFrame, period_col: str, x_col: str, x_title: str, show_table: bool = True):
    if _check_df_empty(df):
        return
    for meta, g in _hierarchy_groups(df):
        if period_col not in g.columns:
            continue
        for period_val, g_part in g.groupby(period_col, dropna=False):
            title = _group_title(meta, extra=str(period_val))
            agg = _axis_prep(g_part, x_col=x_col)
            _stacked_bars(agg, title=title, x_title=x_title)

    render_period_lines(df, period_col, x_col, x_title)

    if show_table:
        _dowload_button(df, filename_prefix="manuel_etiket")

# --------------------------
# LINE CHART - HAFTALIK - AYLIK
# --------------------------
def _detect_total_prod_col(df: pd.DataFrame) -> str:
    """
    Servis tarafında isim 'ToplamUretim' ya da 'ToplamUretimAdet' olabilir.
    Hangisi varsa onu döndür.
    """
    for cand in ["ToplamUretim", "ToplamUretimAdet"]:
        if cand in df.columns:
            return cand
    # yoksa grafik çizemeyiz; sentinel döndür
    return "__MISSING__"


def _prep_trend_long(df: pd.DataFrame, x_col: str) -> pd.DataFrame:
    """
    Gün/Hafta sütununa göre (x_col) iki seriyi uzun forma çevirir:
    - 'ToplamManualAdet'  -> Seri='Manuel Etiket'
    - 'ToplamUretim'(*)   -> Seri='Toplam Üretim'
    Çıktı: ['_etiket','Seri','Deger']
    """
    if x_col not in df.columns or "ToplamManualAdet" not in df.columns:
        return pd.DataFrame(columns=["_etiket", "Seri", "Deger"])

    prod_col = _detect_total_prod_col(df)
    if prod_col == "__MISSING__":
        # üretim kolonu yoksa sadece manuel serisini çizebiliriz
        work = df.copy()
        if x_col == "Gun":
            work[x_col] = pd.to_datetime(work[x_col], errors="coerce")
            grp = work.groupby(x_col, as_index=False)["ToplamManualAdet"].sum().sort_values(x_col)
            etiket = grp[x_col].dt.strftime("%Y-%m-%d")
        else:
            grp = work.groupby(x_col, as_index=False)["ToplamManualAdet"].sum().sort_values(x_col)
            etiket = grp[x_col].astype(str)

        return pd.DataFrame({
            "_etiket": etiket,
            "Seri":    ["Manuel Etiket"] * len(grp),
            "Deger":   pd.to_numeric(grp["ToplamManualAdet"], errors="coerce").fillna(0),
        })

    # Her iki seri de var:
    work = df.copy()
    sums = {}
    for col in ["ToplamManualAdet", prod_col]:
        if x_col == "Gun":
            work[x_col] = pd.to_datetime(work[x_col], errors="coerce")
            grp = work.groupby(x_col, as_index=False)[col].sum().sort_values(x_col)
            sums[col] = grp
            sums[col]["_etiket"] = grp[x_col].dt.strftime("%Y-%m-%d")
        else:
            grp = work.groupby(x_col, as_index=False)[col].sum().sort_values(x_col)
            sums[col] = grp
            sums[col]["_etiket"] = grp[x_col].astype(str)

    manual = pd.DataFrame({
        "_etiket": sums["ToplamManualAdet"]["_etiket"],
        "Seri":    "Manuel Etiket",
        "Deger":   pd.to_numeric(sums["ToplamManualAdet"]["ToplamManualAdet"], errors="coerce").fillna(0),
    })

    uretim = pd.DataFrame({
        "_etiket": sums[prod_col]["_etiket"],
        "Seri":    "Toplam Üretim",
        "Deger":   pd.to_numeric(sums[prod_col][prod_col], errors="coerce").fillna(0),
    })

    return pd.concat([manual, uretim], ignore_index=True)


def _line_chart(df: pd.DataFrame, *, title: str | None, x_title: str, height: int = 360) -> None:
    """
    Altair çizgi grafik. Beklenen kolonlar: ['_etiket','Seri','Deger']
    """
    if _check_df_empty(df):
        return

    # X genişliği dinamik; bar ile aynı mantık
    n = df["_etiket"].nunique()
    step_px = 110 if n <= 6 else max(60, int(900 / max(n, 1)))

    # Renkler (2 seri)
    colors = {
        "Manuel Etiket": "#F59E0B",  # amber
        "Toplam Üretim": "#1F77B4",  # blue
    }
    domain = list(colors.keys())
    range_  = [colors[k] for k in domain]

    tooltip = [
        alt.Tooltip("_etiket:N", title=x_title),
        alt.Tooltip("Seri:N",    title="Seri"),
        alt.Tooltip("Deger:Q",   title="Adet", format=",.0f"),
    ]

    chart = (
        alt.Chart(df)
        .encode(
            x=alt.X("_etiket:N", title=x_title,
                    axis=alt.Axis(labelAngle=0, labelLimit=10000, labelPadding=10)),
            y=alt.Y("Deger:Q", title="Adet"),
            color=alt.Color("Seri:N",
                            scale=alt.Scale(domain=domain, range=range_),
                            legend=alt.Legend(orient="top", direction="horizontal", title=None)),
            tooltip=tooltip,
        )
    )

    line = chart.mark_line(point=True)

    # Nokta üstü etiketler
    labels = (
        chart.mark_text(align="center", baseline="bottom", dy=-6, size=14)  # dy: yazıyı biraz yukarı taşır
        .encode(
            text=alt.Text("Deger:Q", format=",.0f"),  # 1,234 biçiminde
            detail="Seri:N"  # her seri için ayrı etiket
        )
    )

    chart = (
        (line + labels)
        .properties(
            width=alt.Step(step_px),
            height=height,
            padding={"left": 10, "right": 10, "top": 30, "bottom": 60}  # üstte etikete yer aç
        )
        .configure_view(strokeOpacity=0)
    )

    if title:
        chart = chart.properties(title=title)

    st.altair_chart(chart, use_container_width=True)

def render_period_lines(df: pd.DataFrame, period_col: str, x_col: str, x_title: str):
    if _check_df_empty(df):
        return
    for meta, g in _hierarchy_groups(df):
        if period_col not in g.columns:
            continue
        for period_val, g_part in g.groupby(period_col, dropna=False):
            title = _group_title(meta, extra=str(period_val)) or str(period_val)
            long_df = _prep_trend_long(g_part, x_col=x_col)
            _line_chart(long_df, title=title, x_title=x_title)