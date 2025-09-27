from __future__ import annotations
import pandas as pd
import numpy as np
import altair as alt
import streamlit as st
import io
from datetime import datetime
from utils.session_helper import mark_skip_clear_once

# Hiyerarşi sırası – gelen DF’te hangileri varsa onlar dikkate alınır
LEVELS = ["Site", "Departman", "Bolum", "Makine"]

# DF kontrol mesajı
EMPTY_MSG = "Gösterilecek veri yok."

# --------------------------
# Genel Yardımcılar
# --------------------------
def _check_df_empty(df):
    if df.empty:
        st.info(EMPTY_MSG)
        return True
    return False

def _make_label(
    df: pd.DataFrame,
    base_col: str,                # x ekseni baz kolu (Gun / Hafta)
    base_fmt: str | None = None,  # datetime ise format
    exclude_levels: list[str] | None = None,  # etikete DAHİL ETME (üst kırılımları gizle)
) -> pd.DataFrame:
    """Tek bir yerde etiket üretimi (DRY)."""
    out = df.copy()

    # baz metin
    if base_fmt:
        col = pd.to_datetime(out[base_col], errors="coerce")
        base = col.dt.strftime(base_fmt).fillna("")
    else:
        base = out[base_col].astype("string").fillna("")

    dims = [c for c in LEVELS if c in out.columns]
    if exclude_levels:
        dims = [c for c in dims if c not in exclude_levels]

    if dims:
        right = out[dims].astype("string").agg(" / ".join, axis=1)
        out["_etiket"] = (base + " " + right).str.strip()
    else:
        out["_etiket"] = base

    return out


def _aggregate_for_chart(labeled_df: pd.DataFrame) -> pd.DataFrame:
    """Aynı etiketi toplar; yüzdeyi güvenli yeniden hesaplar."""
    if "_etiket" not in labeled_df.columns:
        raise ValueError("Önce _make_label ile '_etiket' oluşturun.")

    for c in ["Toplam", "AsanUretim", "AsmayanUretim"]:
        if c in labeled_df.columns:
            labeled_df[c] = pd.to_numeric(labeled_df[c], errors="coerce").fillna(0)

    agg = (
        labeled_df
        .groupby("_etiket", as_index=False)
        .agg(
            Toplam=("Toplam", "sum"),
            AsanUretim=("AsanUretim", "sum"),
            AsmayanUretim=("AsmayanUretim", "sum"),
        )
    )

    agg["AsanUretimYuzde"] = (
        agg["AsanUretim"] / agg["Toplam"]
    ).replace([np.inf, -np.inf], 0).fillna(0) * 100.0

    return agg


def _to_long_for_stacked(agg: pd.DataFrame) -> pd.DataFrame:
    """Stacked bar için tek tip long-form üretimi."""
    long_df = agg.melt(
        id_vars=["_etiket", "Toplam", "AsanUretimYuzde"],
        value_vars=["AsmayanUretim", "AsanUretim"],
        var_name="DurumRaw",
        value_name="Adet",
    )
    long_df["Durum"] = long_df["DurumRaw"].map({
        "AsmayanUretim": "Asmayan Üretim",
        "AsanUretim":    "Asan Üretim",
    })
    long_df["Durum"] = pd.Categorical(
        long_df["Durum"],
        ["Asmayan Üretim", "Asan Üretim"],
        ordered=True,
    )
    long_df["Adet"] = pd.to_numeric(long_df["Adet"], errors="coerce").fillna(0)
    return long_df


def _stacked_chart(long_df: pd.DataFrame, height: int = 380) -> alt.Chart:
    n_bars = long_df["_etiket"].nunique()
    step_px = 110 if n_bars <= 6 else max(60, int(900 / max(n_bars, 1)))

    return (
        alt.Chart(long_df)
        .mark_bar()
        .encode(
            x=alt.X("_etiket:N", title="Grup",
                    axis=alt.Axis(labelAngle=0, labelLimit=10000, labelPadding=10)),
            y=alt.Y("Adet:Q", title="Adet", stack="zero"),
            color=alt.Color(
                "Durum:N",
                scale=alt.Scale(domain=["Asmayan Üretim", "Asan Üretim"],
                                range=["#F59E0B", "#1F77B4"]),
                legend=alt.Legend(orient="top", direction="horizontal"),
                title="Durum",
            ),
            order=alt.Order("Durum:N"),
            tooltip=[
                alt.Tooltip("_etiket:N",         title="Grup"),
                alt.Tooltip("Toplam:Q",          title="Toplam",  format=",.0f"),
                alt.Tooltip("Adet:Q",            title="Parça",   format=",.0f"),
                alt.Tooltip("Durum:N",           title="Tür"),
                alt.Tooltip("AsanUretimYuzde:Q", title="Asan %",  format=".2f"),
            ],
        )
        .properties(width=alt.Step(step_px), height=height, padding={"left":10,"right":10,"top":10,"bottom":60})
        .configure_view(strokeOpacity=0)
    )

# -----------------------------------------
#   HİYERARŞİK ÇİZİM
# -----------------------------------------

def _render_hierarchy(
    df: pd.DataFrame,
    *,
    base_col: str,                # "Gun" ya da "Hafta"
    base_fmt: str | None,         # Gun için "%Y-%m-%d" gibi; Hafta’da None
    title: str,
) -> None:
    st.subheader(title)

    # zorunlu kolonlar
    required = ["Toplam", "AsanUretim", "AsmayanUretim", base_col]

    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error("Eksik kolon(lar): " + ", ".join(missing))
        return

    levels = [c for c in LEVELS if c in df.columns]

    def next_split_index(sub: pd.DataFrame, start_i: int) -> int | None:
        for i in range(start_i, len(levels)):
            col = levels[i]
            if sub[col].astype("string").nunique(dropna=True) > 1:
                return i
        return None

    def recurse(sub: pd.DataFrame, start_i: int, used: list[str]):
        idx = next_split_index(sub, start_i)
        if idx is None:
            labeled = _make_label(sub, base_col=base_col, base_fmt=base_fmt, exclude_levels=used)
            agg = _aggregate_for_chart(labeled)
            if agg[["Toplam", "AsanUretim", "AsmayanUretim"]].sum().sum() == 0:
                return
            long_df = _to_long_for_stacked(agg)
            st.altair_chart(_stacked_chart(long_df), use_container_width=True)
            st.divider()
            return

        dim = levels[idx]
        for val in sub[dim].astype("string").dropna().unique():
            st.markdown(f"**{dim}: {val}**")
            recurse(sub[sub[dim].astype("string") == val], idx + 1, used + [dim])

    recurse(df, 0, used=[])


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


# ----------------------------------
#    LINE CHART - HAFTALIK - AYLIK
# ----------------------------------
def _group_title(meta: dict, extra: str | None = None) -> str:
    parts = []
    if "Bolum" in meta and pd.notna(meta["Bolum"]):
        parts.append(str(meta["Bolum"]))
    if extra:
        parts.append(str(extra))
    tail = [k for k in ["Site", "Departman", "Makine"] if k in meta and pd.notna(meta[k])]
    if tail:
        parts.append(" / ".join(str(meta[k]) for k in tail))
    return " – ".join(parts) if parts else (extra or "")

def _prep_trend_long(df: pd.DataFrame, base_col: str) -> pd.DataFrame:
    """
    X ekseni kolonu (base_col: 'Gun' ya da 'Hafta') baz alınarak
    iki seriyi (Toplam, AsanUretim) uzun forma çevirir.
    Çıktı: ['_etiket','Seri','Deger']
    """
    work = df.copy()
    for c in ["Toplam", "AsanUretim"]:
        if c in work.columns:
            work[c] = pd.to_numeric(work[c], errors="coerce").fillna(0)

    if base_col == "Gun":
        work[base_col] = pd.to_datetime(work[base_col], errors="coerce")
        work["_etiket"] = work[base_col].dt.strftime("%Y-%m-%d")
    else:
        work["_etiket"] = work[base_col].astype(str)

    grp = (
        work.groupby("_etiket", as_index=False)[["Toplam", "AsanUretim"]]
            .sum()
            .sort_values("_etiket")
    )

    long_df = grp.melt(
        id_vars=["_etiket"],
        value_vars=["Toplam", "AsanUretim"],
        var_name="Seri",
        value_name="Deger",
    )

    long_df["Seri"] = long_df["Seri"].map({
        "Toplam":     "Toplam Üretim",
        "AsanUretim": "Asan Üretim",
    })
    long_df["Deger"] = pd.to_numeric(long_df["Deger"], errors="coerce").fillna(0)
    return long_df[["_etiket", "Seri", "Deger"]]

def _line_chart(df_long: pd.DataFrame, *, title: str | None, x_title: str, height: int = 360) -> None:
    """
    Uzun formdaki veriyi (['_etiket','Seri','Deger']) çizgi grafik olarak çizer.
    """
    if df_long is None or df_long.empty:
        return

    n = df_long["_etiket"].nunique()
    step_px = 110 if n <= 6 else max(60, int(900 / max(n, 1)))

    colors = {
        "Toplam Üretim": "#1F77B4",  # mavi
        "Asan Üretim":   "#F59E0B",  # amber
    }
    domain = list(colors.keys())
    range_  = [colors[k] for k in domain]

    tooltip = [
        alt.Tooltip("_etiket:N", title=x_title),
        alt.Tooltip("Seri:N",    title="Seri"),
        alt.Tooltip("Deger:Q",   title="Adet", format=",.0f"),
    ]

    base = alt.Chart(df_long).encode(
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
        tooltip=tooltip,
    )

    line = base.mark_line(point=True)
    labels = base.mark_text(align="center", baseline="bottom", dy=-6, size=14) \
                 .encode(text=alt.Text("Deger:Q", format=",.0f"), detail="Seri:N")

    chart = (line + labels).properties(
        width=alt.Step(step_px),
        height=height,
        padding={"left": 10, "right": 10, "top": 30, "bottom": 60},
    ).configure_view(strokeOpacity=0)

    if title:
        chart = chart.properties(title=title)

    st.altair_chart(chart, use_container_width=True)


def render_period_lines(df: pd.DataFrame, period_col: str, x_col: str, x_title: str):
    """
    Hiyerarşik kırılımlara göre (varsa) period_col’a (Hafta/Ay) göre bölerek,
    x_col (Gun/Hafta) ekseninde Toplam & Asan serilerini çizer.
    """
    if df is None or df.empty:
        return

    # Hiyerarşi: dataframe'inizde varsa bu kolonlar üzerinden kırılım yapın
    _levels = [c for c in LEVELS if c in df.columns]

    def _iter_groups(frame: pd.DataFrame):
        if not _levels:
            yield {}, frame
        else:
            for keys, g in frame.groupby(_levels, dropna=False):
                if not isinstance(keys, tuple):
                    keys = (keys,)
                yield dict(zip(_levels, keys)), g

    for meta, g in _iter_groups(df):
        if period_col not in g.columns:
            continue
        for period_val, g_part in g.groupby(period_col, dropna=False):
            title = _group_title(meta, extra=str(period_val)) or str(period_val)
            long_df = _prep_trend_long(g_part, base_col=x_col)
            _line_chart(long_df, title=title, x_title=x_title)


# ----------------------------------
#     GUNLUK - HAFTALIK - AYLIK
# ----------------------------------

def render_daily_bars(df: pd.DataFrame, title: str = "Üretim Raporu (Günlük)", show_table: bool = True) -> None:
    if _check_df_empty(df):
        return
    # Günlükte x = Gun (tarih) ve format uygulanır
    _render_hierarchy(df, base_col="Gun",   base_fmt="%Y-%m-%d", title=title)
    if show_table:
        _dowload_button(df, filename_prefix="uretim_asan")

def render_weekly_bars(df: pd.DataFrame, title: str = "Üretim Raporu (Haftalık)", show_table: bool = True) -> None:
    if _check_df_empty(df):
        return
    # Haftalıkta da x = Gun (haftanın günleri / periyot başlangıcı), tarih formatı isterseniz güncelleyebilirsiniz
    _render_hierarchy(df, base_col="Gun",   base_fmt="%Y-%m-%d", title=title)
    render_period_lines(df, period_col="Hafta", x_col="Gun", x_title="Gün")
    if show_table:
        _dowload_button(df, filename_prefix="uretim_asan")

def render_monthly_bars(df: pd.DataFrame, title: str = "Üretim Raporu (Aylık)", show_table: bool = True) -> None:
    if _check_df_empty(df):
        return
    # Aylık görünüm sizde “Hafta” kolonuna göre (örn 2025-31, 2025-32 …) – format yok
    _render_hierarchy(df, base_col="Hafta", base_fmt=None, title=title)
    render_period_lines(df, period_col="Ay", x_col="Hafta", x_title="Hafta")
    if show_table:
        _dowload_button(df, filename_prefix="uretim_asan")
