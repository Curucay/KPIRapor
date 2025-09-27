import io
from datetime import datetime
import pandas as pd
import streamlit as st
import altair as alt

# =========================
#  Sabitler / Renkler
# =========================

HIER_ORDER   = ["site", "departman", "bolum", "makine"]  # df'de gelen küçük harf kolonlara göre
SERIES_NAME  = "Toplam"  # legend ismi
EMPTY_MSG    = "Gösterilecek veri yok."

# =========================
# Genel Yardımcılar
# =========================
def _check_df_empty(df: pd.DataFrame) -> bool:
    if df is None or df.empty:
        st.info(EMPTY_MSG)
        return True
    return False

def _resolve_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Verilen aday kolonlardan df'de bulunan ilkini döndür."""
    for c in candidates:
        if c in df.columns:
            return c
    return None

def _hier_groups(df: pd.DataFrame):
    """Hiyerarşik kırılımlara göre (site/…/makine) alt grupları ver."""
    dims = [c for c in HIER_ORDER if c in df.columns]
    if not dims:
        yield {}, df
    else:
        for keys, g in df.groupby(dims, dropna=False, sort=True):
            if not isinstance(keys, tuple):
                keys = (keys,)
            yield dict(zip(dims, keys)), g

def _group_title(meta: dict, extra: str | None = None) -> str:
    """
    Başlık kuralı: Bolum varsa başa yaz, sonra (varsa) extra (örn. hafta/ay),
    kuyruğa site/Departman/Makine bilgisi.
    """
    parts: list[str] = []
    if "bolum" in meta and pd.notna(meta["bolum"]):
        parts.append(str(meta["bolum"]))
    if extra:
        parts.append(str(extra))
    tail_keys = [k for k in ["site", "departman", "makine"] if k in meta and pd.notna(meta[k])]
    if tail_keys:
        parts.append(" / ".join(str(meta[k]) for k in tail_keys))
    return " – ".join(parts) if parts else (extra or "")

def _download_button(df: pd.DataFrame, filename_prefix: str = "transaction_ozet"):
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

def _prep_agg(df: pd.DataFrame, x_col: str, value_col: str = "toplam") -> pd.DataFrame:
    """
    X eksenine göre (saat/gun/hafta) 'value_col' (varsayılan: toplam) toplayıp
    sırayı koruyarak ['_etiket','Deger'] döndürür.
    """
    if x_col not in df.columns or value_col not in df.columns:
        return pd.DataFrame(columns=["_etiket", "Deger"])

    work = df[[x_col, value_col]].copy()
    # Tür ve sıralama işlemleri
    if x_col == "gun":
        work[x_col] = pd.to_datetime(work[x_col], errors="coerce")
        grp = (work.groupby(x_col, as_index=False)[value_col].sum()
               .sort_values(x_col, kind="mergesort"))
        grp["_etiket"] = grp[x_col].dt.strftime("%Y-%m-%d")
    elif x_col == "saat":
        # 'HH:MM(:SS)' string; güvenli sıralama için pars et, sonra etikete geri dön
        s = pd.to_datetime(work[x_col], format="%H:%M:%S", errors="coerce")
        work["_sort"] = (
            s.dt.hour.fillna(-1).astype(int) * 3600
            + s.dt.minute.fillna(0).astype(int) * 60
            + s.dt.second.fillna(0).astype(int)
        )
        grp = (work.groupby([x_col, "_sort"], as_index=False)[value_col]
                    .sum()
                    .sort_values("_sort"))
        grp["_etiket"] = grp[x_col]
    else:  # "hafta" veya diğer düz metin eksenleri
        grp = (work.groupby(x_col, as_index=False)[value_col].sum()
               .sort_values(x_col, kind="mergesort"))
        grp["_etiket"] = grp[x_col].astype(str)

    grp[value_col] = pd.to_numeric(grp[value_col], errors="coerce").fillna(0)
    out = grp.rename(columns={value_col: "Deger"})[["_etiket", "Deger"]]
    return out

def _prep_long(df: pd.DataFrame, x_col: str, value_col: str = "toplam") -> pd.DataFrame:
    """Altair için uzun form: ['_etiket','Seri','Deger']"""
    agg = _prep_agg(df, x_col=x_col, value_col=value_col)
    if agg.empty:
        return pd.DataFrame(columns=["_etiket", "Seri", "Deger"])
    agg["Seri"] = SERIES_NAME
    return agg[["_etiket", "Seri", "Deger"]]

# =========================
#  Grafik
# =========================
def _line_chart(long_df: pd.DataFrame, *, title: str | None, x_title: str, height: int = 360):
    """Toplam Tutar dağılımı çizgi grafiği."""
    if long_df.empty:
        st.info(EMPTY_MSG)
        return

    n = long_df["_etiket"].nunique()
    step_px = 90 if n <= 6 else max(60, int(900 / max(n, 1)))

    base = alt.Chart(long_df).encode(
        x=alt.X(
            "_etiket:N",
            title=x_title,
            axis=alt.Axis(labelAngle=0, labelLimit=10000, labelPadding=10),
        ),
        y=alt.Y("Deger:Q", title="Adet"),
        color=alt.Color(
            "Seri:N",
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
        # SOL boşluğu artır: eksen başlığı yer bulsun
        padding={"left": 48, "right": 10, "top": 30, "bottom": 60},
        title=title
    ).configure_axis(
        # Y ekseni başlığı ve etiketleri için ekstra iç boşluk
        titlePadding=24,
        labelPadding=10
    ).configure_legend(
        orient="top", direction="horizontal", title=None
    ).configure_view(strokeOpacity=0)

    st.altair_chart(chart, use_container_width=True)


# =========================
#  Render (Kullanacağın fonksiyon)
# =========================

def render_transaction_lines(df: pd.DataFrame, mode: str):
    """
    mode:
      - 'Gün'   => X: saat       (24 saatlik nokta)
      - 'Hafta' => X: gun        (haftanın günleri)
      - 'Ay'    => X: hafta      (ayın ISO haftaları)
    """
    if _check_df_empty(df):
        return

    mode = (mode or "").strip()
    value_col = "toplam"

    if mode == "Gün":
        x_col, x_title = "saat", "Saat"
        period_col, period_title = None, None
    elif mode == "Hafta":
        x_col, x_title = "gun", "Gün"
        period_col, period_title = "hafta", "Hafta"
    elif mode == "Ay":
        x_col, x_title = "hafta", "Hafta"
        period_col, period_title = "ay", "Ay"
    else:
        st.warning("Geçerli bir dönem seçiniz: Gün / Hafta / Ay")
        return

    # Hiyerarşi → (Site/Departman/Bölüm/Makine)
    for meta, g in _hier_groups(df):
        if period_col and period_col in g.columns:
            for pval, part in g.groupby(period_col, dropna=False, sort=True):
                title = _group_title(meta, extra=f"{period_title}: {pval}")
                long_df = _prep_long(part, x_col=x_col, value_col=value_col)
                _line_chart(long_df, title=title, x_title=x_title)
        else:
            title = _group_title(meta) or ""
            long_df = _prep_long(g, x_col=x_col, value_col=value_col)
            _line_chart(long_df, title=title, x_title=x_title)

    _download_button(df, filename_prefix=f"transaction_{mode.lower()}")

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
    if mode in ("Gün", "Hafta", "Ay"):
        render_transaction_lines(df, mode=mode)
    else:
        st.warning("Geçerli bir dönem seçiniz: Gün / Hafta / Ay")
