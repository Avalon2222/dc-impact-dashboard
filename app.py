"""
app.py - Dashboard Dampak Data Center Indonesia
=================================================
Jalankan dengan:   streamlit run app.py

Alur besar file ini (baca dari atas ke bawah):
  1. Import library
  2. Muat data (CSV) + parameter asumsi
  3. Sidebar: filter + slider asumsi
  4. Hitung estimasi listrik & air
  5. Tampilkan: angka ringkasan -> tab peta / listrik / air / warga / ML / SQL / API / data / cara kerja

Catatan gaya: setiap bagian punya komentar "APA" dan "KENAPA". Kalau ada
istilah yang asing, cek docs/BELAJAR.md.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import db, hitung
from src.model import muat_metrik
from src.muat_data import muat_data_center, muat_parameter, muat_parameter_lengkap

# ----------------------------------------------------------------------------
# 0. KONFIGURASI HALAMAN & WARNA
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="Dampak Data Center Indonesia",
    page_icon="🏭",
    layout="wide",
)

# Satu status = satu warna, URUTANNYA TETAP (bukan diacak) supaya konsisten di semua grafik.
WARNA_STATUS = {
    "beroperasi": "#2a78d6",  # biru
    "dibangun": "#eb6834",    # oranye
    "rencana": "#1baf7a",     # hijau-aqua
}
LABEL_STATUS = {"beroperasi": "Beroperasi", "dibangun": "Dibangun", "rencana": "Rencana"}
WARNA_BIRU_SEKUENSIAL = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]

TEMPLATE = "plotly_white"


def ruang_label(fig: go.Figure, nilai_maks: float, faktor: float = 1.35) -> go.Figure:
    """Perlebar sumbu X supaya angka di ujung batang tidak terpotong."""
    fig.update_xaxes(range=[0, nilai_maks * faktor])
    return fig


def rapikan(fig: go.Figure, tinggi: int = 420) -> go.Figure:
    """Gaya seragam untuk semua grafik: grid tipis, margin kecil, legenda di atas."""
    fig.update_layout(
        template=TEMPLATE,
        height=tinggi,
        margin=dict(l=10, r=20, t=85, b=10),
        title=dict(y=0.98, yanchor="top", x=0, xanchor="left", font=dict(size=15)),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, title=None),
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif"),
        hoverlabel=dict(bgcolor="white"),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#e1e0d9", zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)
    return fig


# ----------------------------------------------------------------------------
# 1. MUAT DATA (di-cache supaya tidak dibaca ulang setiap klik)
# ----------------------------------------------------------------------------
@st.cache_data
def ambil_data():
    return muat_data_center(), muat_parameter(), muat_parameter_lengkap()


@st.cache_data
def ambil_prediksi():
    """Prediksi PUE/WUE per lokasi dari model (data/prediksi_lokasi.csv) + metrik evaluasinya."""
    try:
        prediksi = db.jalankan("SELECT * FROM prediksi_lokasi")
    except Exception:
        prediksi = pd.DataFrame()
    return prediksi, muat_metrik()


@st.cache_data(show_spinner=False)
def jalankan_sql_cache(sql: str) -> pd.DataFrame:
    return db.jalankan(sql)


df_mentah, PARAM, df_param = ambil_data()
df_prediksi, METRIK = ambil_prediksi()
df_mentah["lokasi_id"] = [f"{a:.2f},{b:.2f}" for a, b in zip(df_mentah["lat"], df_mentah["lon"])]
ADA_MODEL = METRIK is not None and not df_prediksi.empty

# ----------------------------------------------------------------------------
# 2. SIDEBAR: filter + asumsi
# ----------------------------------------------------------------------------
with st.sidebar:
    st.title("🏭 Dampak Data Center")
    st.caption("Dashboard estimasi konsumsi listrik & air data center di Indonesia.")

    mode_belajar = st.toggle("🎓 Learning mode", value=False,
                             help="Tampilkan penjelasan & potongan kode di balik setiap grafik.")

    st.subheader("Filter")
    pilih_status = st.multiselect(
        "Status fasilitas",
        options=list(LABEL_STATUS.keys()),
        default=["beroperasi", "dibangun"],
        format_func=lambda s: LABEL_STATUS[s],
    )
    pilih_provinsi = st.multiselect(
        "Provinsi", options=sorted(df_mentah["provinsi"].unique()),
        default=sorted(df_mentah["provinsi"].unique()),
    )
    pilih_keyakinan = st.multiselect(
        "Tingkat keyakinan data",
        options=["tinggi", "sedang", "rendah"], default=["tinggi", "sedang", "rendah"],
        help="'rendah' = kapasitas tidak dipublikasikan, kami pakai estimasi kasar.",
    )

    st.subheader("Assumptions (slide to test scenarios)")
    utilisasi = st.slider("Server utilization", 0.1, 1.0, float(PARAM["utilisasi"]), 0.05,
                          help="Seberapa penuh kapasitas IT terpakai rata-rata. 0,6 = 60%.")
    pakai_model = st.toggle(
        "🤖 PUE from climate model", value=False, disabled=not ADA_MODEL,
        help="Ganti PUE tunggal dengan PUE hasil model per lokasi (kelas hyperscale, dari iklim). Lihat tab ML Prediction.",
    )
    pue = st.slider("PUE (power efficiency)", 1.1, 2.5, float(PARAM["pue"]), 0.05, disabled=pakai_model,
                    help="Listrik total / listrik server. Makin dekat 1 makin efisien.")
    wue = st.slider("WUE (liters of water per server kWh)", 0.0, 4.0, float(PARAM["wue"]), 0.1,
                    help="0 = pendingin tanpa air. Rata-rata industri ~1,8. Hyperscaler efisien 0,2-0,6.")
    kwh_per_kapita = st.number_input("Electricity per capita (kWh/person/year)",
                                     value=int(PARAM["listrik_per_kapita_kwh_tahun"]), step=50,
                                     help="ESDM 2024: 1.411 kWh/kapita.")
    liter_per_orang = st.number_input("Water need (liters/person/day)",
                                      value=int(PARAM["air_per_orang_liter_hari"]), step=10,
                                      help="SNI kota besar 150 L; kebutuhan pokok minimum 60 L.")
    orang_per_rt = int(PARAM["orang_per_rumah_tangga"])

    st.caption("Sumber & catatan tiap angka ada di tab **Data & Sources**.")

# ----------------------------------------------------------------------------
# 3. FILTER + HITUNG
# ----------------------------------------------------------------------------
df = df_mentah[
    df_mentah["status"].isin(pilih_status)
    & df_mentah["provinsi"].isin(pilih_provinsi)
    & df_mentah["keyakinan"].isin(pilih_keyakinan)
].copy()

# PUE bisa satu angka (slider) atau satu angka per fasilitas (prediksi model menurut iklim lokasinya).
if pakai_model:
    peta_pue = df_prediksi.set_index("lokasi_id")["pue_prediksi"]
    df["pue_dipakai"] = df["lokasi_id"].map(peta_pue).fillna(float(PARAM["pue"]))
    pue_efektif = df["pue_dipakai"]
else:
    df["pue_dipakai"] = pue
    pue_efektif = pue

df = hitung.tambah_kolom_estimasi(
    df, utilisasi=utilisasi, pue=pue_efektif, wue=wue,
    kwh_per_kapita_tahun=kwh_per_kapita, liter_per_orang_hari=liter_per_orang,
    orang_per_rumah_tangga=orang_per_rt,
)
df["status_label"] = df["status"].map(LABEL_STATUS).astype(str)

# ----------------------------------------------------------------------------
# 4. HEADER + ANGKA RINGKASAN
# ----------------------------------------------------------------------------
st.title("Dampak Data Center terhadap Listrik & Air di Indonesia")
st.markdown(
    "Peta dan estimasi seberapa besar data center di Indonesia menyedot **listrik** dan **air**, "
    "dibandingkan dengan kebutuhan **warga**. Angka adalah *estimasi* dari kapasitas yang "
    "dipublikasikan; geser asumsi di kiri untuk melihat skenario lain."
)

if df.empty:
    st.warning("Tidak ada data yang cocok dengan filter. Coba longgarkan filter di sidebar.")
    st.stop()

total_mw = df["kapasitas_it_mw"].sum()
total_gwh = df["listrik_gwh_tahun"].sum()
total_air_m3 = df["air_m3_tahun"].sum()
total_orang_listrik = df["setara_orang_listrik"].sum()
total_orang_air = df["setara_orang_air"].sum()

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Fasilitas", f"{len(df)}", help="Jumlah data center sesuai filter.")
k2.metric("Kapasitas IT", f"{hitung.format_angka(total_mw)} MW")
k3.metric("Listrik / tahun", f"{hitung.format_angka(total_gwh)} GWh",
          help="Kapasitas x utilisasi x PUE x 8.760 jam." + (" PUE per lokasi dari model iklim." if pakai_model else ""))
k4.metric("Air / tahun", f"{hitung.format_ringkas(total_air_m3)} m³",
          help="kWh server x WUE.")
k5.metric("Setara listrik (orang)", hitung.format_ringkas(total_orang_listrik),
          help=f"Dibagi {hitung.format_angka(kwh_per_kapita)} kWh/orang/tahun.")

st.caption(
    f"💧 Air sebanyak itu setara kebutuhan harian **{hitung.format_ringkas(total_orang_air)} orang** "
    f"({liter_per_orang} L/orang/hari). Data: {len(df_mentah)} fasilitas dari sumber publik; "
    f"{(df_mentah['keyakinan'] == 'rendah').sum()} di antaranya kapasitasnya estimasi kasar."
)

tab_peta, tab_listrik, tab_air, tab_warga, tab_ml, tab_sql, tab_api, tab_data, tab_cara = st.tabs(
    ["🗺️ Map", "⚡ Electricity", "💧 Water", "🏘️ Impact on Residents",
     "🤖 ML Prediction", "🗄️ SQL Explorer", "🔌 API", "📋 Data & Sources", "🧭 How it works"]
)

# ----------------------------------------------------------------------------
# TAB 1: PETA
# ----------------------------------------------------------------------------
with tab_peta:
    st.subheader("Di mana data center Indonesia berada?")
    st.caption("Ukuran lingkaran = kapasitas IT (MW). Warna = status. Arahkan kursor untuk detail.")

    fig_peta = px.scatter_map(
        df,
        lat="lat", lon="lon",
        size="kapasitas_it_mw", size_max=45,
        color="status_label",
        color_discrete_map={LABEL_STATUS[k]: v for k, v in WARNA_STATUS.items()},
        category_orders={"status_label": list(LABEL_STATUS.values())},
        hover_name="nama",
        hover_data={
            "lat": False, "lon": False, "status_label": False,
            "operator": True, "kabupaten_kota": True,
            "kapasitas_it_mw": ":.1f", "listrik_gwh_tahun": ":.0f",
            "air_m3_tahun": ":,.0f", "keyakinan": True,
        },
        labels={
            "kapasitas_it_mw": "Kapasitas IT (MW)", "listrik_gwh_tahun": "Listrik (GWh/thn)",
            "air_m3_tahun": "Air (m³/thn)", "operator": "Operator",
            "kabupaten_kota": "Kab/Kota", "keyakinan": "Keyakinan data",
        },
        zoom=4.7, center={"lat": -3.4, "lon": 107.0},
        map_style="carto-positron",
    )
    fig_peta.update_traces(marker=dict(opacity=0.8))
    fig_peta.update_layout(height=520, margin=dict(l=0, r=0, t=0, b=0),
                           legend=dict(orientation="h", y=0.02, x=0.02, title=None, bgcolor="rgba(255,255,255,0.8)"))
    st.plotly_chart(fig_peta, use_container_width=True)

    st.info(
        "💡 **Pola yang kelihatan:** hampir semua kapasitas menumpuk di **koridor Bekasi-Cikarang-Karawang** "
        "(dekat Jakarta, lahan industri, jaringan listrik kuat) dan **Batam** (dekat Singapura yang "
        "membatasi data center baru). Padahal dua daerah ini juga padat penduduk dan sering kesulitan air."
    )

    if mode_belajar:
        with st.expander("🎓 Bagaimana peta ini dibuat?"):
            st.markdown(
                "Peta ini hanya **scatter plot** (titik-titik) yang ditempel di atas peta dunia. "
                "Setiap baris CSV punya `lat`/`lon`, Plotly menaruh satu lingkaran di koordinat itu. "
                "`size` mengatur besar lingkaran dari kolom MW, `color` memberi warna dari kolom status."
            )
            st.code(
                'px.scatter_map(df, lat="lat", lon="lon",\n'
                '               size="kapasitas_it_mw",   # besar lingkaran\n'
                '               color="status_label",     # warna\n'
                '               hover_name="nama",        # judul tooltip\n'
                '               map_style="carto-positron")',
                language="python",
            )
            st.markdown("**Latihan:** ganti `map_style` jadi `\"open-street-map\"` lalu lihat bedanya.")

# ----------------------------------------------------------------------------
# TAB 2: LISTRIK
# ----------------------------------------------------------------------------
with tab_listrik:
    st.subheader("Siapa yang paling banyak menyedot listrik?")

    kol_a, kol_b = st.columns([3, 2])

    with kol_a:
        top = df.sort_values("listrik_gwh_tahun", ascending=True).tail(15)
        fig_bar = px.bar(
            top, x="listrik_gwh_tahun", y="nama", orientation="h",
            color="status_label",
            color_discrete_map={LABEL_STATUS[k]: v for k, v in WARNA_STATUS.items()},
            category_orders={"status_label": list(LABEL_STATUS.values())},
            text=top["listrik_gwh_tahun"].map(lambda v: hitung.format_angka(v)),
            labels={"listrik_gwh_tahun": "GWh per tahun", "nama": ""},
            title="15 fasilitas dengan estimasi listrik terbesar (GWh/tahun)",
        )
        fig_bar.update_traces(textposition="outside", marker_line_width=0, width=0.7)
        ruang_label(fig_bar, top["listrik_gwh_tahun"].max())
        rapikan(fig_bar, 520)
        st.plotly_chart(fig_bar, use_container_width=True)

    with kol_b:
        per_kota = (
            df.groupby("kabupaten_kota", observed=True)["listrik_gwh_tahun"]
            .sum().sort_values(ascending=False).reset_index()
        )
        fig_kota = px.bar(
            per_kota, x="listrik_gwh_tahun", y="kabupaten_kota", orientation="h",
            labels={"listrik_gwh_tahun": "GWh per tahun", "kabupaten_kota": ""},
            title="Total per kabupaten/kota",
            color="listrik_gwh_tahun", color_continuous_scale=WARNA_BIRU_SEKUENSIAL,
        )
        fig_kota.update_layout(coloraxis_showscale=False, yaxis=dict(autorange="reversed"))
        fig_kota.update_traces(marker_line_width=0,
                               text=per_kota["listrik_gwh_tahun"].map(lambda v: hitung.format_angka(v)),
                               textposition="outside")
        ruang_label(fig_kota, per_kota["listrik_gwh_tahun"].max())
        rapikan(fig_kota, 520)
        st.plotly_chart(fig_kota, use_container_width=True)

    # Perbandingan: kapasitas per status (beroperasi vs pipeline)
    st.subheader("Yang beroperasi vs yang masih datang")
    per_status = (
        df_mentah.groupby("status", observed=True)["kapasitas_it_mw"].sum().reset_index()
    )
    per_status["status_label"] = per_status["status"].map(LABEL_STATUS).astype(str)
    fig_status = px.bar(
        per_status, x="status_label", y="kapasitas_it_mw",
        color="status_label",
        color_discrete_map={LABEL_STATUS[k]: v for k, v in WARNA_STATUS.items()},
        text=per_status["kapasitas_it_mw"].map(lambda v: f"{hitung.format_angka(v)} MW"),
        labels={"kapasitas_it_mw": "Kapasitas IT (MW)", "status_label": ""},
        title="Kapasitas IT seluruh dataset (tidak terpengaruh filter) menurut status",
    )
    fig_status.update_traces(textposition="outside", marker_line_width=0, width=0.5, showlegend=False)
    fig_status.update_yaxes(showgrid=True, gridcolor="#e1e0d9")
    fig_status.update_xaxes(showgrid=False)
    rapikan(fig_status, 380)
    st.plotly_chart(fig_status, use_container_width=True)

    beroperasi_mw = per_status.loc[per_status["status"] == "beroperasi", "kapasitas_it_mw"].sum()
    rencana_mw = per_status.loc[per_status["status"] != "beroperasi", "kapasitas_it_mw"].sum()
    st.info(
        f"💡 Yang beroperasi di dataset ini ~**{hitung.format_angka(beroperasi_mw)} MW** "
        f"(riset pasar memperkirakan total nasional ~{int(PARAM['indonesia_dc_mw_terpasang_1h26'])} MW "
        f"per 1H 2026, jadi dataset kami menangkap sebagian besar). Yang sedang dibangun + direncanakan "
        f"~**{hitung.format_angka(rencana_mw)} MW**, alias **{rencana_mw / beroperasi_mw:.1f}x** lipat "
        f"dari yang ada sekarang. Di situlah pertanyaan pentingnya: siapa yang menanggung "
        f"lonjakan kebutuhan listrik dan air itu?"
    )

    if mode_belajar:
        with st.expander("🎓 Rumus listrik & cara grafik ini dibuat"):
            st.latex(r"E_{tahun}\ (\text{GWh}) = \frac{MW \times utilisasi \times PUE \times 8760}{1000}")
            pue_contoh = float(df["pue_dipakai"].mean())
            st.markdown(
                f"Dengan asumsi sekarang (utilisasi **{utilisasi:.2f}**, PUE **{pue_contoh:.2f}**"
                f"{' rata-rata prediksi model' if pakai_model else ''}), "
                f"fasilitas 10 MW ≈ **{hitung.listrik_tahunan_gwh(10, utilisasi, pue_contoh):.1f} GWh/tahun**. "
                "Coba geser PUE di sidebar dan lihat semua angka berubah: itulah gunanya memisahkan "
                "*parameter* dari *rumus*."
            )
            st.code(
                'top = df.sort_values("listrik_gwh_tahun").tail(15)   # ambil 15 terbesar\n'
                'px.bar(top, x="listrik_gwh_tahun", y="nama",\n'
                '       orientation="h", color="status_label")           # bar horizontal',
                language="python",
            )
            st.markdown("**Latihan:** ganti `tail(15)` jadi `tail(5)`. Lalu coba `groupby(\"provinsi\")` "
                        "untuk grafik per provinsi, bukan per kabupaten/kota.")

# ----------------------------------------------------------------------------
# TAB 3: AIR
# ----------------------------------------------------------------------------
with tab_air:
    st.subheader("Berapa banyak air yang dipakai untuk mendinginkan server?")
    st.caption(
        "Air dipakai terutama untuk **pendingin evaporatif** (menguapkan air membuang panas). "
        "Angka sangat tergantung teknologi: WUE 0 (pendingin udara/closed-loop) sampai ~4 L/kWh."
    )

    kol_a, kol_b = st.columns([3, 2])
    with kol_a:
        top_air = df.sort_values("air_m3_tahun", ascending=True).tail(15)
        fig_air = px.bar(
            top_air, x="air_m3_tahun", y="nama", orientation="h",
            color="status_label",
            color_discrete_map={LABEL_STATUS[k]: v for k, v in WARNA_STATUS.items()},
            category_orders={"status_label": list(LABEL_STATUS.values())},
            text=top_air["air_m3_tahun"].map(hitung.format_ringkas),
            labels={"air_m3_tahun": "m³ per tahun", "nama": ""},
            title=f"15 fasilitas dengan estimasi air terbesar (WUE {wue:.1f} L/kWh)",
        )
        fig_air.update_traces(textposition="outside", marker_line_width=0, width=0.7)
        ruang_label(fig_air, top_air["air_m3_tahun"].max())
        rapikan(fig_air, 520)
        st.plotly_chart(fig_air, use_container_width=True)

    with kol_b:
        # Skenario WUE: angka total air dengan 3 teknologi pendingin berbeda.
        skenario = pd.DataFrame({
            "Skenario": ["Hyperscaler efisien (0,3)", "Rata-rata industri (1,8)", "Boros / tropis (3,5)"],
            "wue": [0.3, 1.8, 3.5],
        })
        kwh_server_total = (df["kapasitas_it_mw"] * utilisasi * hitung.JAM_PER_TAHUN * 1000).sum()
        skenario["air_m3"] = kwh_server_total * skenario["wue"] / 1000
        skenario["orang"] = skenario["air_m3"].map(
            lambda m3: hitung.setara_penduduk_air(m3, liter_per_orang))
        fig_sken = px.bar(
            skenario, x="Skenario", y="air_m3",
            text=skenario["air_m3"].map(lambda v: f"{hitung.format_ringkas(v)} m³"),
            custom_data=["orang"],
            labels={"air_m3": "m³ per tahun"},
            title="Total air menurut skenario teknologi pendingin",
            color="wue", color_continuous_scale=WARNA_BIRU_SEKUENSIAL,
        )
        fig_sken.update_traces(textposition="outside", marker_line_width=0, width=0.55, textfont_size=12,
                               hovertemplate="%{x}<br>%{y:,.0f} m³/tahun<br>≈ %{customdata[0]:,.0f} orang<extra></extra>")
        fig_sken.update_layout(coloraxis_showscale=False)
        fig_sken.update_yaxes(showgrid=True, gridcolor="#e1e0d9", range=[0, skenario["air_m3"].max() * 1.35])
        fig_sken.update_xaxes(showgrid=False)
        rapikan(fig_sken, 520)
        st.plotly_chart(fig_sken, use_container_width=True)
        st.caption("Setara kebutuhan harian: " + " · ".join(
            f"{r.Skenario.split(' (')[0]} ≈ {hitung.format_ringkas(r.orang)} orang" for r in skenario.itertuples()))

    kolam = total_air_m3 / 2500  # kolam renang olimpiade ~2.500 m³
    st.info(
        f"💡 Dengan asumsi sekarang, fasilitas yang terfilter memakai ~**{hitung.format_ringkas(total_air_m3)} m³ air/tahun** "
        f"≈ **{hitung.format_angka(kolam)} kolam renang olimpiade**, atau kebutuhan harian "
        f"**{hitung.format_ringkas(total_orang_air)} orang**. Catatan jujur: operator di Indonesia "
        f"hampir tidak pernah mempublikasikan WUE, jadi ini area yang layak digali lebih jauh "
        f"(wawancara operator, dokumen AMDAL, izin pengambilan air tanah)."
    )

    if mode_belajar:
        with st.expander("🎓 Rumus air & kenapa PUE tidak ikut"):
            st.latex(r"Air_{tahun}\ (m^3) = \frac{MW \times utilisasi \times 8760 \times 1000 \times WUE}{1000}")
            st.markdown(
                "WUE didefinisikan sebagai liter air per **kWh listrik server** (bukan listrik total), "
                "jadi PUE tidak dikalikan di sini. Dua pembagi/pengali 1000 itu: MW→kW, lalu liter→m³."
            )
            st.code(
                'kwh_server = mw * utilisasi * 8760 * 1000\n'
                'air_m3 = kwh_server * wue / 1000',
                language="python",
            )
            st.markdown("**Latihan:** tambahkan skenario ke-4 'Tanpa air (0,0)' di tabel `skenario`.")

# ----------------------------------------------------------------------------
# TAB 4: DAMPAK KE WARGA
# ----------------------------------------------------------------------------
with tab_warga:
    st.subheader("Kalau satu data center dibanding satu kampung, seperti apa?")

    pilihan = st.selectbox("Select facility", options=df.sort_values("kapasitas_it_mw", ascending=False)["nama"])
    baris = df[df["nama"] == pilihan].iloc[0]

    st.markdown(
        f"**{baris['nama']}** · {baris['operator']} · {baris['lokasi']}, {baris['kabupaten_kota']} · "
        f"status **{LABEL_STATUS[baris['status']]}** · keyakinan data **{baris['keyakinan']}**"
    )
    if baris["catatan"]:
        st.caption(f"📝 {baris['catatan']}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kapasitas IT", f"{hitung.format_angka(baris['kapasitas_it_mw'], 1)} MW")
    c2.metric("Listrik / tahun", f"{hitung.format_angka(baris['listrik_gwh_tahun'])} GWh")
    c3.metric("Air / hari", f"{hitung.format_ringkas(baris['air_liter_hari'])} liter")
    c4.metric("Air / tahun", f"{hitung.format_ringkas(baris['air_m3_tahun'])} m³")

    st.markdown("#### Setara dengan...")
    e1, e2, e3, e4 = st.columns(4)
    e1.metric("⚡ Listrik: setara orang", hitung.format_ringkas(baris['setara_orang_listrik']))
    e2.metric("🏠 Listrik: setara rumah tangga", hitung.format_ringkas(baris['setara_rumah_tangga_listrik']),
              help=f"Asumsi {orang_per_rt} orang per rumah tangga.")
    e3.metric("💧 Air: setara orang", hitung.format_ringkas(baris['setara_orang_air']))
    e4.metric("🚛 Truk tangki 5.000 L per hari", hitung.format_angka(baris['air_liter_hari'] / 5000))

    # Grafik perbandingan: fasilitas ini vs 1 rumah tangga vs 1 RW (±250 RT) vs 1 kelurahan (±2.500 RT)
    st.markdown("#### Skala perbandingan listrik per tahun")
    kwh_rt = kwh_per_kapita * orang_per_rt
    banding = pd.DataFrame({
        "Pembanding": ["1 rumah tangga", "1 RW (±250 RT)", "1 kelurahan (±2.500 RT)",
                       "1 kecamatan (±25.000 RT)", f"{baris['nama'][:28]}"],
        "kwh": [kwh_rt, kwh_rt * 250, kwh_rt * 2500, kwh_rt * 25000, baris["listrik_gwh_tahun"] * 1e6],
    })
    banding["jenis"] = ["Warga"] * 4 + ["Data center"]
    fig_banding = px.bar(
        banding, x="kwh", y="Pembanding", orientation="h", color="jenis",
        color_discrete_map={"Warga": "#898781", "Data center": WARNA_STATUS["beroperasi"]},
        text=banding["kwh"].map(lambda v: f"{hitung.format_ringkas(v)} kWh"),
        labels={"kwh": "kWh per tahun (skala logaritmik)", "Pembanding": ""},
        log_x=True,
    )
    fig_banding.update_traces(textposition="outside", marker_line_width=0, width=0.6)
    rapikan(fig_banding, 360)
    fig_banding.update_xaxes(range=[3, 9.6])  # sumbu log: 10^3 .. 10^9.6 kWh
    st.plotly_chart(fig_banding, use_container_width=True)
    st.caption(
        "Sumbu X logaritmik: tiap garis grid = 10x lipat. Jumlah RT per RW/kelurahan/kecamatan hanya "
        "pembulatan kasar agar skalanya mudah dibayangkan."
    )

    st.markdown("#### Pertumbuhan kapasitas dari waktu ke waktu")
    garis = (
        df_mentah.dropna(subset=["tahun"])
        .groupby(["tahun", "status"], observed=True)["kapasitas_it_mw"].sum().reset_index()
    )
    garis = garis.sort_values("tahun")
    garis["kumulatif_mw"] = garis.groupby("status", observed=True)["kapasitas_it_mw"].cumsum()
    garis["status_label"] = garis["status"].map(LABEL_STATUS).astype(str)
    fig_garis = px.line(
        garis, x="tahun", y="kumulatif_mw", color="status_label", markers=True,
        color_discrete_map={LABEL_STATUS[k]: v for k, v in WARNA_STATUS.items()},
        category_orders={"status_label": list(LABEL_STATUS.values())},
        labels={"tahun": "Tahun (mulai) operasi", "kumulatif_mw": "Kapasitas kumulatif (MW)"},
        title="Kapasitas kumulatif menurut tahun mulai operasi (tahun rencana = perkiraan)",
        line_shape="hv",
    )
    fig_garis.update_traces(line=dict(width=2), marker=dict(size=8))
    fig_garis.update_yaxes(showgrid=True, gridcolor="#e1e0d9")
    fig_garis.update_xaxes(showgrid=False, dtick=2)
    rapikan(fig_garis, 380)
    st.plotly_chart(fig_garis, use_container_width=True)

    if mode_belajar:
        with st.expander("🎓 Mengambil satu baris & membuat tabel pembanding"):
            st.code(
                'baris = df[df["nama"] == pilihan].iloc[0]   # satu baris -> Series\n'
                'baris["listrik_gwh_tahun"]                    # akses kolom seperti dict\n\n'
                'banding = pd.DataFrame({"Pembanding": [...], "kwh": [...]})  # tabel kecil buatan sendiri\n'
                'px.bar(banding, x="kwh", y="Pembanding", log_x=True)         # sumbu log',
                language="python",
            )
            st.markdown(
                "Kenapa sumbu **logaritmik**? Karena 1 rumah tangga (~5.600 kWh) vs data center "
                "(ratusan juta kWh) bedanya 100.000x. Di sumbu biasa, batang rumah tangga tidak akan terlihat."
            )
            st.markdown("**Latihan:** tambahkan pembanding '1 RT (±50 rumah)' ke tabel `banding`.")

# ----------------------------------------------------------------------------
# TAB 5: PREDIKSI ML (PUE & WUE dari iklim)
# ----------------------------------------------------------------------------
with tab_ml:
    st.subheader("Bisakah iklim lokasi menebak seberapa boros pendingin data center?")
    st.caption(
        "Model dilatih dari **data nyata**: PUE kuartalan tiap kampus Google (2016-sekarang) dan "
        "listrik + air tahunan tiap situs Meta (2020-2024), digabung dengan iklim lokasi masing-masing (NASA POWER). "
        "Lalu dipakai untuk menebak PUE/WUE kelas hyperscale di iklim lokasi data center Indonesia."
    )

    if not ADA_MODEL:
        st.warning("Model belum dilatih. Jalankan `python scripts/pipeline.py` lalu muat ulang halaman.")
    else:
        info_pue = METRIK["model"]["pue"]
        info_wue = METRIK["model"]["wue"]
        ev_pue = info_pue["evaluasi"]
        terpilih = info_pue["terpilih"]

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Data latih PUE", f"{info_pue['n_baris']} kuartal", help=f"{info_pue['n_grup']} kampus Google")
        m2.metric("MAE model (CV)", f"{ev_pue[terpilih]['mae_cv']:.4f}",
                  delta=f"{(ev_pue[terpilih]['mae_cv'] / ev_pue['baseline_rata_rata']['mae_cv'] - 1):+.0%} vs baseline",
                  delta_color="inverse", help="Rata-rata selisih absolut prediksi vs PUE sebenarnya, diuji pada kampus yang disembunyikan saat latih.")
        m3.metric("R² (CV per kampus)", f"{ev_pue[terpilih]['r2_cv']:.2f}",
                  help="1 = sempurna, 0 = sama dengan menebak rata-rata. Diuji pada kampus yang tidak ikut dilatih.")
        m4.metric("Model terpilih", terpilih.replace("_", " "), help=info_pue["alasan"])

        kol_a, kol_b = st.columns([3, 2])
        with kol_a:
            oof = pd.read_csv("data/evaluasi_pue_oof.csv")
            fig_oof = px.scatter(
                oof, x="pue_kuartalan", y="pue_prediksi_oof", color="bola_basah_rata",
                color_continuous_scale=WARNA_BIRU_SEKUENSIAL, hover_name="kampus",
                hover_data={"tahun": True, "kuartal": True, "pue_kuartalan": ":.3f", "pue_prediksi_oof": ":.3f", "bola_basah_rata": ":.1f"},
                labels={"pue_kuartalan": "PUE sebenarnya (Google)", "pue_prediksi_oof": "PUE prediksi (out-of-fold)",
                        "bola_basah_rata": "Bola basah (°C)"},
                title="Observasi vs prediksi: tiap titik = satu kampus x satu kuartal",
            )
            batas = [oof["pue_kuartalan"].min() - 0.01, oof["pue_kuartalan"].max() + 0.01]
            fig_oof.add_shape(type="line", x0=batas[0], y0=batas[0], x1=batas[1], y1=batas[1],
                              line=dict(color="#898781", dash="dash"))
            fig_oof.update_traces(marker=dict(size=7, opacity=0.7))
            fig_oof.update_yaxes(showgrid=True, gridcolor="#e1e0d9")
            rapikan(fig_oof, 460)
            st.plotly_chart(fig_oof, use_container_width=True)
            st.caption("Prediksi *out-of-fold*: saat kampus X diuji, semua kuartal kampus X disembunyikan dari pelatihan. "
                       "Garis putus-putus = prediksi sempurna.")

        with kol_b:
            tabel_ev = pd.DataFrame(ev_pue).T.reset_index().rename(columns={"index": "model"})
            tabel_ev["model"] = tabel_ev["model"].str.replace("_", " ")
            st.markdown("**Perbandingan kandidat model (PUE)**")
            st.dataframe(
                tabel_ev[["model", "mae_cv", "rmse_cv", "r2_cv", "mae_waktu", "r2_waktu"]],
                hide_index=True, use_container_width=True,
                column_config={
                    "mae_cv": st.column_config.NumberColumn("MAE CV", format="%.4f"),
                    "rmse_cv": st.column_config.NumberColumn("RMSE CV", format="%.4f"),
                    "r2_cv": st.column_config.NumberColumn("R² CV", format="%.2f"),
                    "mae_waktu": st.column_config.NumberColumn("MAE uji ≥2024", format="%.4f"),
                    "r2_waktu": st.column_config.NumberColumn("R² uji ≥2024", format="%.2f"),
                },
            )
            penting = pd.DataFrame(
                {"fitur": list(info_pue["pentingnya_fitur"]), "nilai": list(info_pue["pentingnya_fitur"].values())}
            ).sort_values("nilai")
            fig_penting = px.bar(penting, x="nilai", y="fitur", orientation="h",
                                 labels={"nilai": "Kenaikan MAE kalau fitur diacak", "fitur": ""},
                                 title="Fitur mana yang paling menentukan?")
            fig_penting.update_traces(marker_color=WARNA_STATUS["beroperasi"], marker_line_width=0)
            rapikan(fig_penting, 300)
            st.plotly_chart(fig_penting, use_container_width=True)

        st.markdown("#### Diterapkan ke lokasi data center Indonesia")
        kol_c, kol_d = st.columns([3, 2])
        with kol_c:
            per_lokasi = (
                df_prediksi.groupby("kabupaten_kota")
                .agg(pue=("pue_prediksi", "mean"), pue_min=("pue_q1", "min"), pue_maks=("pue_q3", "max"),
                     bola_basah=("bola_basah_rata", "mean"))
                .reset_index().sort_values("pue")
            )
            q_cols = [c for c in df_prediksi.columns if c.startswith("pue_q")]
            rentang = df_prediksi.groupby("kabupaten_kota")[q_cols].agg(["min", "max"])
            per_lokasi["q_min"] = per_lokasi["kabupaten_kota"].map(rentang.xs("min", axis=1, level=1).min(axis=1))
            per_lokasi["q_maks"] = per_lokasi["kabupaten_kota"].map(rentang.xs("max", axis=1, level=1).max(axis=1))
            fig_lok = px.bar(
                per_lokasi, x="pue", y="kabupaten_kota", orientation="h",
                color="bola_basah", color_continuous_scale=WARNA_BIRU_SEKUENSIAL,
                text=per_lokasi["pue"].map(lambda v: f"{v:.3f}"),
                error_x=per_lokasi["q_maks"] - per_lokasi["pue"], error_x_minus=per_lokasi["pue"] - per_lokasi["q_min"],
                labels={"pue": "PUE prediksi (rata-rata 4 kuartal)", "kabupaten_kota": "", "bola_basah": "Bola basah (°C)"},
                title=f"PUE prediksi per lokasi, iklim tahun {int(df_prediksi['tahun_iklim'].iloc[0])}",
            )
            fig_lok.update_traces(textposition="outside", marker_line_width=0)
            fig_lok.update_xaxes(range=[per_lokasi["q_min"].min() - 0.02, per_lokasi["q_maks"].max() + 0.03])
            rapikan(fig_lok, 420)
            st.plotly_chart(fig_lok, use_container_width=True)
            st.caption("Garis tipis = rentang prediksi antar kuartal (musim). Semua lokasi Indonesia panas-lembap sepanjang tahun, "
                       "jadi rentangnya sempit; bedanya ada pada kelembapan pesisir (Batam) vs pedalaman (Bekasi-Karawang).")

        with kol_d:
            pembanding = jalankan_sql_cache("""
                SELECT g.kampus AS nama, l.negara, AVG(g.pue_kuartalan) AS pue, AVG(i.bola_basah_rata) AS bola_basah, 'Google (observasi)' AS jenis
                FROM pue_google g
                JOIN lokasi_kampus l ON l.kampus = g.kampus AND l.perusahaan = 'google'
                JOIN iklim i ON i.lokasi_id = l.lokasi_id AND i.tahun = g.tahun AND i.kuartal = g.kuartal
                WHERE g.tahun >= 2022 GROUP BY 1, 2
            """)
            indo = per_lokasi.rename(columns={"kabupaten_kota": "nama"}).assign(negara="Indonesia", jenis="Indonesia (prediksi)")
            gabung = pd.concat([pembanding, indo[["nama", "negara", "pue", "bola_basah", "jenis"]]], ignore_index=True)
            fig_iklim = px.scatter(
                gabung, x="bola_basah", y="pue", color="jenis", hover_name="nama", hover_data={"negara": True, "pue": ":.3f", "bola_basah": ":.1f"},
                color_discrete_map={"Google (observasi)": "#898781", "Indonesia (prediksi)": WARNA_STATUS["dibangun"]},
                labels={"bola_basah": "Suhu bola basah rata-rata (°C)", "pue": "PUE", "jenis": ""},
                title="PUE vs bola basah: Google (observasi) vs Indonesia (prediksi)",
            )
            fig_iklim.update_traces(marker=dict(size=10, opacity=0.85))
            fig_iklim.update_yaxes(showgrid=True, gridcolor="#e1e0d9")
            rapikan(fig_iklim, 420)
            st.plotly_chart(fig_iklim, use_container_width=True)

        st.info(
            f"💡 **Yang bisa disimpulkan:** model menebak PUE kelas hyperscale di Indonesia sekitar "
            f"**{METRIK['prediksi_indonesia']['pue_min']:.2f}-{METRIK['prediksi_indonesia']['pue_maks']:.2f}**, mirip kampus Google "
            f"Singapura (observasi ~1,12-1,15). Itu *batas bawah* yang realistis untuk iklim tropis; fasilitas kolokasi biasa di "
            f"Indonesia umumnya masih di 1,4-1,7, jadi asumsi default dashboard (1,5) tetap masuk akal. Nyalakan toggle "
            f"**PUE from climate model** di sidebar untuk melihat skenario 'kalau semua fasilitas sekelas hyperscale'."
        )

        st.markdown("#### Dan air? Hasilnya jujur: iklim saja tidak cukup")
        kol_e, kol_f = st.columns([2, 3])
        with kol_e:
            ev_wue = info_wue["evaluasi"]
            tabel_wue = pd.DataFrame(ev_wue).T.reset_index().rename(columns={"index": "model"})
            tabel_wue["model"] = tabel_wue["model"].str.replace("_", " ")
            st.dataframe(
                tabel_wue[["model", "mae_cv", "r2_cv"]], hide_index=True, use_container_width=True,
                column_config={"mae_cv": st.column_config.NumberColumn("MAE CV (L/kWh)", format="%.3f"),
                               "r2_cv": st.column_config.NumberColumn("R² CV", format="%.2f")},
            )
            if info_wue["layak"]:
                st.success(f"Model WUE terpilih: **{info_wue['terpilih']}**. {info_wue['alasan']}")
            else:
                st.warning(
                    f"**Tidak ada model yang lolos gerbang kelayakan** (R² CV ≥ 0,2 dan MAE ≤ 85% baseline). "
                    f"Pipeline otomatis memilih baseline rata-rata (**{info_wue['rata_rata_target']:.2f} L/kWh**) "
                    f"supaya dashboard tidak memamerkan 'prediksi' yang tidak lebih baik dari menebak. "
                    f"Data latih: {info_wue['n_baris']} situs-tahun dari {info_wue['n_grup']} situs Meta."
                )
        with kol_f:
            meta_air = jalankan_sql_cache("""
                SELECT situs, negara, AVG(liter_per_kwh) AS liter_per_kwh, AVG(i.bola_basah_rata) AS bola_basah
                FROM v_meta_intensitas_air m JOIN iklim i ON i.lokasi_id = m.lokasi_id AND i.tahun = m.tahun AND i.kuartal = 0
                GROUP BY 1, 2 ORDER BY 3
            """)
            fig_meta = px.bar(
                meta_air, x="liter_per_kwh", y="situs", orientation="h", color="bola_basah",
                color_continuous_scale=WARNA_BIRU_SEKUENSIAL, text=meta_air["liter_per_kwh"].map(lambda v: f"{v:.2f}"),
                labels={"liter_per_kwh": "Liter air per kWh listrik (rata-rata 2020-2024)", "situs": "", "bola_basah": "Bola basah (°C)"},
                title="Intensitas air situs Meta: yang paling boros justru di iklim sejuk",
            )
            fig_meta.update_traces(textposition="outside", marker_line_width=0)
            ruang_label(fig_meta, meta_air["liter_per_kwh"].max(), 1.2)
            rapikan(fig_meta, 460)
            st.plotly_chart(fig_meta, use_container_width=True)
            st.caption("Clonee (Irlandia) dan Odense (Denmark) memakai air paling banyak per kWh padahal iklimnya dingin. "
                       "Artinya **teknologi pendingin dan sumber air** yang menentukan, bukan cuaca. Itu sebabnya WUE di dashboard "
                       "ini tetap berupa skenario yang kamu pilih sendiri (slider), bukan hasil model.")

    if mode_belajar:
        with st.expander("🎓 Bagaimana model ini dilatih dan dievaluasi?"):
            st.markdown(
                """
1. **Data latih** dibuat dengan `JOIN` di DuckDB: PUE Google per kampus per kuartal ⟷ iklim lokasi kampus itu pada kuartal yang sama
   (`sql/06_pue_vs_iklim.sql` menunjukkan JOIN-nya).
2. **Fitur** = ringkasan iklim (suhu, kelembapan, bola basah, cooling degree days, hari panas-lembap) + umur kampus + tahun.
3. **Empat kandidat** diuji: baseline rata-rata, Ridge (linear), Random Forest, Gradient Boosting.
4. **Cross-validation menurut kampus** (`GroupKFold`): kampus yang diuji tidak pernah dilihat saat latih. Ini meniru kasus kita:
   memprediksi lokasi baru (Indonesia).
5. **Gerbang kelayakan**: model hanya dipakai kalau MAE ≤ 85% baseline dan R² ≥ 0,2. Kalau tidak, baseline yang disimpan.
   Model WUE gagal di gerbang ini, dan itu hasil yang tetap berguna: ia membantah hipotesis "iklim menentukan pemakaian air".
                """
            )
            st.code(
                "for latih, uji in GroupKFold(n_splits=5).split(X, y, grup=kampus):\n"
                "    model.fit(X.iloc[latih], y.iloc[latih])\n"
                "    pred.iloc[uji] = model.predict(X.iloc[uji])   # prediksi out-of-fold\n"
                "mae = mean_absolute_error(y, pred)",
                language="python",
            )
            st.markdown("**Latihan:** di `scripts/latih_model.py`, tambahkan kandidat `KNeighborsRegressor` dan lihat apakah lolos gerbang.")

# ----------------------------------------------------------------------------
# TAB 6: SQL EXPLORER (DuckDB)
# ----------------------------------------------------------------------------
with tab_sql:
    st.subheader("Tanya datanya langsung dengan SQL")
    st.caption(
        "Semua data dashboard ini tersimpan di satu file database **DuckDB** (`data/dc_impact.duckdb`), "
        "dibangun ulang oleh pipeline tiap minggu. Pilih query siap pakai atau tulis `SELECT` sendiri (hanya-baca)."
    )
    daftar_q = db.query_tersimpan()
    kol_q, kol_s = st.columns([3, 1])
    with kol_q:
        judul_ke_q = {q["judul"]: q for q in daftar_q}
        pilih_q = st.selectbox("Saved query", options=list(judul_ke_q), index=0)
        q_terpilih = judul_ke_q[pilih_q]
        if q_terpilih["deskripsi"]:
            st.caption(q_terpilih["deskripsi"])
        sql_teks = st.text_area("SQL", value=q_terpilih["sql"], height=220, key=f"sql_{q_terpilih['file']}",
                                label_visibility="collapsed")
        jalankan_btn = st.button("▶ Run query", type="primary")
    with kol_s:
        st.markdown("**Tables & views**")
        tabel_df = db.daftar_tabel()
        st.dataframe(tabel_df, hide_index=True, use_container_width=True, height=250)
        tabel_pilih = st.selectbox("Columns of", options=tabel_df["tabel"].tolist(), index=int((tabel_df["tabel"] == "fasilitas").idxmax()))
        st.dataframe(db.skema(tabel_pilih), hide_index=True, use_container_width=True, height=220)

    sql_jalan = sql_teks if jalankan_btn else q_terpilih["sql"]
    if not db.sql_aman(sql_jalan):
        st.error("Hanya satu pernyataan SELECT/WITH yang diizinkan (INSERT/UPDATE/DROP ditolak).")
    else:
        try:
            hasil_sql = jalankan_sql_cache(sql_jalan)
        except Exception as e:
            st.error(f"SQL gagal: {e}")
            hasil_sql = pd.DataFrame()
        if not hasil_sql.empty:
            st.markdown(f"**{len(hasil_sql)} baris**")
            st.dataframe(hasil_sql, hide_index=True, use_container_width=True)
            kolom_angka = hasil_sql.select_dtypes("number").columns.tolist()
            kolom_teks = [k for k in hasil_sql.columns if k not in kolom_angka]
            if kolom_angka and kolom_teks and len(hasil_sql) <= 60:
                with st.expander("📊 Grafik cepat dari hasil query", expanded=True):
                    g1, g2 = st.columns(2)
                    sumbu_y = g1.selectbox("Kategori", kolom_teks, key="sql_kat")
                    sumbu_x = g2.selectbox("Nilai", kolom_angka, key="sql_nilai")
                    fig_sql = px.bar(hasil_sql.sort_values(sumbu_x), x=sumbu_x, y=sumbu_y, orientation="h",
                                     labels={sumbu_x: sumbu_x, sumbu_y: ""})
                    fig_sql.update_traces(marker_color=WARNA_STATUS["beroperasi"], marker_line_width=0)
                    rapikan(fig_sql, min(600, 120 + 24 * len(hasil_sql)))
                    st.plotly_chart(fig_sql, use_container_width=True)
            st.download_button("⬇️ Download hasil (CSV)", data=hasil_sql.to_csv(index=False).encode("utf-8"),
                               file_name="hasil_query.csv", mime="text/csv")

    if mode_belajar:
        with st.expander("🎓 Kenapa DuckDB, dan apa bedanya dengan pandas?"):
            st.markdown(
                """
- **pandas** enak untuk mengolah satu tabel di Python. **SQL** enak untuk *pertanyaan* lintas tabel:
  `JOIN` dua tabel, `GROUP BY`, `SUM() OVER (...)` (window function), semuanya satu kalimat.
- **DuckDB** = database analitik dalam satu file, tanpa server. Dibaca langsung oleh Streamlit, FastAPI, dan tes.
- Skema dibangun di `scripts/bangun_db.py`; VIEW `v_estimasi` menulis rumus `src/hitung.py` dalam SQL,
  dan tes memastikan keduanya memberi angka yang sama.
                """
            )
            st.code(
                "import duckdb\n"
                "kon = duckdb.connect('data/dc_impact.duckdb', read_only=True)\n"
                "kon.execute('SELECT provinsi, SUM(kapasitas_it_mw) FROM fasilitas GROUP BY 1').df()",
                language="python",
            )
            st.markdown("**Latihan:** tulis query yang menghitung rata-rata PUE Google per **tahun** untuk kampus Singapura saja.")

# ----------------------------------------------------------------------------
# TAB 7: API (FastAPI)
# ----------------------------------------------------------------------------
with tab_api:
    st.subheader("Angka yang sama, lewat HTTP")
    st.caption(
        "Folder `api/` berisi layanan **FastAPI** di atas database dan model yang sama. Program lain "
        "(notebook, spreadsheet, chatbot) bisa menarik data tanpa membuka dashboard. Di bawah ini API dijalankan "
        "*di dalam proses* Streamlit supaya bisa dicoba langsung."
    )
    endpoint_info = pd.DataFrame([
        ("GET", "/fasilitas", "Daftar data center, filter status/provinsi/keyakinan/min_mw"),
        ("GET", "/fasilitas/{id}", "Satu fasilitas"),
        ("GET", "/ringkasan", "Total per provinsi dengan asumsi utilisasi/pue/wue dari query string"),
        ("GET", "/estimasi", "Listrik & air satu fasilitas hipotetis (kapasitas_it_mw, pue, wue, utilisasi)"),
        ("GET", "/prediksi/lokasi", "Prediksi PUE/WUE per lokasi Indonesia (hasil pipeline)"),
        ("POST", "/prediksi/pue", "Prediksi PUE dari ringkasan iklim yang kamu kirim"),
        ("POST", "/prediksi/wue", "Prediksi WUE dari ringkasan iklim (plus status kelayakan model)"),
        ("GET", "/model/metrik", "Semua metrik evaluasi model"),
        ("GET", "/sql/tersimpan", "Query SQL siap pakai"),
        ("POST", "/sql", "Jalankan SELECT bebas (hanya-baca)"),
    ], columns=["Metode", "Path", "Keterangan"])
    st.dataframe(endpoint_info, hide_index=True, use_container_width=True)

    kol_t, kol_h = st.columns([2, 3])
    with kol_t:
        st.markdown("**Coba langsung**")
        pilih_ep = st.selectbox("Endpoint", options=[
            "GET /estimasi?kapasitas_it_mw=10&pue=1.5&wue=1.8",
            "GET /fasilitas?status=beroperasi&min_mw=20",
            "GET /fasilitas/1",
            "GET /ringkasan?pue=1.2&status=beroperasi",
            "GET /prediksi/lokasi",
            "POST /prediksi/pue (iklim Jakarta)",
            "GET /model/metrik",
            "POST /sql (kapasitas per provinsi)",
        ])
        st.code(
            "# Python\nimport requests\n"
            "r = requests.get('http://localhost:8000/estimasi', params={'kapasitas_it_mw': 10})\n"
            "r.json()['listrik_gwh_tahun']   # 78.84\n\n"
            "# curl\ncurl 'http://localhost:8000/ringkasan?pue=1.2'",
            language="python",
        )
        st.markdown(
            "Jalankan sendiri: `uvicorn api.main:app --reload` lalu buka `http://127.0.0.1:8000/docs` "
            "(dokumentasi interaktif otomatis), atau `docker build -t dc-impact-api . && docker run -p 8000:8000 dc-impact-api`."
        )
    with kol_h:
        try:
            from fastapi.testclient import TestClient

            from api.main import app as api_app

            klien = TestClient(api_app)
            iklim_jakarta = {"suhu_rata": 27.6, "suhu_maks_rata": 32.0, "rh_rata": 83.0, "titik_embun_rata": 24.0,
                             "bola_basah_rata": 26.0, "bola_basah_p90": 27.0, "hari_panas_lembap": 92, "cdd18": 880}
            if pilih_ep.startswith("POST /prediksi/pue"):
                resp = klien.post("/prediksi/pue", json={"iklim": iklim_jakarta, "tahun": 2026})
            elif pilih_ep.startswith("POST /sql"):
                resp = klien.post("/sql", json={"sql": "SELECT provinsi, SUM(kapasitas_it_mw) AS mw FROM fasilitas GROUP BY 1 ORDER BY 2 DESC"})
            else:
                resp = klien.get(pilih_ep.split(" ", 1)[1])
            st.markdown(f"`{pilih_ep}` → status **{resp.status_code}**")
            isi = resp.json()
            if isinstance(isi, dict) and "fasilitas" in isi and isinstance(isi["fasilitas"], list):
                isi = {**isi, "fasilitas": isi["fasilitas"][:3] + (["..."] if len(isi["fasilitas"]) > 3 else [])}
            if isinstance(isi, dict) and "lokasi" in isi:
                isi = {**isi, "lokasi": isi["lokasi"][:3] + ["..."]}
            st.json(isi, expanded=3)
        except Exception as e:
            st.warning(f"API tidak bisa dijalankan di sini: {e}")

    if mode_belajar:
        with st.expander("🎓 Apa itu API dan kenapa FastAPI?"):
            st.markdown(
                """
- **API** = pintu untuk program lain. Dashboard ini membaca `src/hitung.py`; API membaca file yang sama.
  Satu logika, dua pintu (manusia & mesin). Kalau rumus berubah, dua-duanya ikut berubah.
- **FastAPI** memvalidasi input otomatis (coba `kapasitas_it_mw=-1`, hasilnya error 422 yang jelas) dan
  membuat dokumentasi interaktif di `/docs` dari *type hint* Python.
- Tes di `tests/test_api.py` memanggil endpoint lewat `TestClient` tanpa server sungguhan.
                """
            )
            st.code(
                '@app.get("/estimasi")\n'
                'def estimasi(kapasitas_it_mw: float = Query(..., gt=0), pue: float = Query(1.5, ge=1)):\n'
                '    return {"listrik_gwh_tahun": hitung.listrik_tahunan_gwh(kapasitas_it_mw, 0.6, pue)}',
                language="python",
            )
            st.markdown("**Latihan:** tambahkan endpoint `GET /operator` yang mengembalikan total MW per operator (pakai `db.jalankan`).")

# ----------------------------------------------------------------------------
# TAB 8: DATA & SUMBER
# ----------------------------------------------------------------------------
with tab_data:
    st.subheader("Data mentah, sumber, dan kejujuran soal estimasi")
    st.markdown(
        "- **tinggi** = angka dari operator / liputan langsung yang kami temukan URL-nya.\n"
        "- **sedang** = direktori industri atau sumber sekunder.\n"
        "- **rendah** = kapasitas tidak dipublikasikan; angka adalah **estimasi kasar kami** "
        "(ditulis jelas di kolom catatan). Koordinat semua titik adalah perkiraan area, bukan alamat persis."
    )

    kolom_tampil = ["nama", "operator", "kabupaten_kota", "provinsi", "status_label", "tahun",
                    "kapasitas_it_mw", "listrik_gwh_tahun", "air_m3_tahun", "setara_orang_listrik",
                    "keyakinan", "sumber", "url_sumber", "catatan"]
    st.dataframe(
        df[kolom_tampil].sort_values("kapasitas_it_mw", ascending=False),
        use_container_width=True, hide_index=True,
        column_config={
            "url_sumber": st.column_config.LinkColumn("Sumber (URL)", display_text="buka"),
            "kapasitas_it_mw": st.column_config.NumberColumn("MW", format="%.1f"),
            "listrik_gwh_tahun": st.column_config.NumberColumn("GWh/thn", format="%.0f"),
            "air_m3_tahun": st.column_config.NumberColumn("Air m³/thn", format="%.0f"),
            "setara_orang_listrik": st.column_config.NumberColumn("Setara orang (listrik)", format="%.0f"),
            "status_label": "Status", "tahun": st.column_config.NumberColumn("Tahun", format="%d"),
        },
    )
    st.download_button(
        "⬇️ Download data + estimasi (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="estimasi_data_center_indonesia.csv", mime="text/csv",
    )

    st.markdown("#### Parameter & asumsi")
    st.dataframe(
        df_param, use_container_width=True, hide_index=True,
        column_config={"url_sumber": st.column_config.LinkColumn("Sumber (URL)", display_text="buka")},
    )

    st.markdown("#### Keterbatasan yang harus diingat")
    st.markdown(
        "1. **Kapasitas IT ≠ pemakaian nyata.** Kami pakai utilisasi (slider) untuk mendekati pemakaian.\n"
        "2. **PUE & WUE Indonesia tidak dipublikasikan** per fasilitas; kami pakai rata-rata industri. "
        "Iklim tropis biasanya membuat PUE/WUE lebih tinggi dari rata-rata global.\n"
        "3. **Per kapita listrik ESDM** termasuk industri & bisnis, jadi 'setara N orang' bersifat ilustratif.\n"
        "4. Dataset ini **bukan daftar lengkap**; ada puluhan fasilitas kecil (enterprise/edge) yang tidak masuk.\n"
        "5. Dampak ke warga tidak hanya volume: **sumber air** (air tanah vs PDAM vs daur ulang) dan "
        "**sumber listrik** (PLTU batu bara vs terbarukan) menentukan siapa yang terkena."
    )

# ----------------------------------------------------------------------------
# TAB 9: CARA KERJA (diagram alur)
# ----------------------------------------------------------------------------
with tab_cara:
    st.subheader("Bagaimana dashboard ini bekerja?")
    st.graphviz_chart(
        """
        digraph G {
          rankdir=TB; node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11];
          edge [color="#898781"];
          subgraph cluster_sumber { label="Sumber data"; style="rounded"; color="#e1e0d9";
            csv1 [label="data_center_indonesia.csv\n(27 fasilitas, dikurasi manual)", fillcolor="#cde2fb"];
            google [label="Google: PUE kuartalan\nper kampus (diunduh)", fillcolor="#cde2fb"];
            meta [label="Meta: listrik & air\nper situs (CSV)", fillcolor="#cde2fb"];
            nasa [label="NASA POWER: iklim\n72 lokasi (diunduh)", fillcolor="#cde2fb"];
          }
          pipe [label="scripts/pipeline.py\nunduh -> validasi -> latih -> bangun DB\n(GitHub Actions tiap minggu)", fillcolor="#fde7dc"];
          model [label="models/*.joblib\nmodel PUE & WUE + metrik", fillcolor="#f0efec"];
          duck [label="data/dc_impact.duckdb\n8 tabel + view SQL", fillcolor="#f0efec", shape=cylinder];
          hit  [label="src/hitung.py\nlistrik = MW x util x PUE x 8760\nair = kWh server x WUE", fillcolor="#f0efec"];
          side [label="Sidebar\nfilter + slider + toggle model", fillcolor="#fde7dc"];
          app  [label="Streamlit\npeta, grafik, SQL Explorer, ML", fillcolor="#d6f3e8"];
          api  [label="FastAPI\n/fasilitas /estimasi /prediksi /sql", fillcolor="#d6f3e8"];
          csv1 -> pipe; google -> pipe; meta -> pipe; nasa -> pipe;
          pipe -> model; pipe -> duck;
          duck -> hit; model -> hit; side -> hit;
          hit -> app; duck -> app; duck -> api; model -> api;
        }
        """
    )
    st.markdown(
        """
**Bacanya dari kiri ke kanan:**
1. **Sumber data.** Daftar fasilitas Indonesia dikurasi manual (CSV). Tiga sumber lain diambil otomatis atau disalin dari
   laporan resmi: PUE kuartalan Google, listrik & air tahunan Meta, dan iklim NASA POWER untuk tiap lokasi.
2. **Pipeline** (`scripts/pipeline.py`) mengunduh, memvalidasi, melatih model, lalu membangun database DuckDB.
   GitHub Actions menjalankannya tiap Senin dan membuat commit kalau ada data baru.
3. **Database + model** adalah dua artefak hasil pipeline. Keduanya dibaca oleh dashboard ini dan oleh API.
4. **Sidebar** mengubah parameter; `hitung.py` mengubah parameter + data jadi estimasi. Toggle *PUE from climate model*
   mengganti PUE tunggal dengan PUE hasil model per lokasi.
5. Streamlit menjalankan ulang seluruh `app.py` dari atas setiap kali slider digeser. Itu kenapa semua grafik
   ikut berubah tanpa kode "update" khusus. Konsep ini namanya *reactive rerun*.

Penjelasan lengkap tiap langkah + latihan: lihat `docs/BELAJAR.md` dan `docs/LATIHAN.md` di repo.
        """
    )
