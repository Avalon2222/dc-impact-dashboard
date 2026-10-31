"""
app.py - Dashboard Dampak Data Center Indonesia
=================================================
Jalankan dengan:   streamlit run app.py

Alur besar file ini (baca dari atas ke bawah):
  1. Import library
  2. Muat data (CSV) + parameter asumsi
  3. Sidebar: filter + slider asumsi
  4. Hitung estimasi listrik & air
  5. Tampilkan: angka ringkasan -> tab peta / listrik / air / warga / data / cara kerja

Catatan gaya: setiap bagian punya komentar "APA" dan "KENAPA". Kalau ada
istilah yang asing, cek docs/BELAJAR.md.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import hitung
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


df_mentah, PARAM, df_param = ambil_data()

# ----------------------------------------------------------------------------
# 2. SIDEBAR: filter + asumsi
# ----------------------------------------------------------------------------
with st.sidebar:
    st.title("🏭 Dampak Data Center")
    st.caption("Dashboard estimasi konsumsi listrik & air data center di Indonesia.")

    mode_belajar = st.toggle("🎓 Mode belajar", value=False,
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

    st.subheader("Asumsi (geser untuk uji skenario)")
    utilisasi = st.slider("Utilisasi server", 0.1, 1.0, float(PARAM["utilisasi"]), 0.05,
                          help="Seberapa penuh kapasitas IT terpakai rata-rata. 0,6 = 60%.")
    pue = st.slider("PUE (efisiensi listrik)", 1.1, 2.5, float(PARAM["pue"]), 0.05,
                    help="Listrik total / listrik server. Makin dekat 1 makin efisien.")
    wue = st.slider("WUE (liter air per kWh server)", 0.0, 4.0, float(PARAM["wue"]), 0.1,
                    help="0 = pendingin tanpa air. Rata-rata industri ~1,8. Hyperscaler efisien 0,2-0,6.")
    kwh_per_kapita = st.number_input("Listrik per kapita (kWh/orang/tahun)",
                                     value=int(PARAM["listrik_per_kapita_kwh_tahun"]), step=50,
                                     help="ESDM 2024: 1.411 kWh/kapita.")
    liter_per_orang = st.number_input("Kebutuhan air (liter/orang/hari)",
                                      value=int(PARAM["air_per_orang_liter_hari"]), step=10,
                                      help="SNI kota besar 150 L; kebutuhan pokok minimum 60 L.")
    orang_per_rt = int(PARAM["orang_per_rumah_tangga"])

    st.caption("Sumber & catatan tiap angka ada di tab **Data & Sumber**.")

# ----------------------------------------------------------------------------
# 3. FILTER + HITUNG
# ----------------------------------------------------------------------------
df = df_mentah[
    df_mentah["status"].isin(pilih_status)
    & df_mentah["provinsi"].isin(pilih_provinsi)
    & df_mentah["keyakinan"].isin(pilih_keyakinan)
].copy()

df = hitung.tambah_kolom_estimasi(
    df, utilisasi=utilisasi, pue=pue, wue=wue,
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
          help="Kapasitas x utilisasi x PUE x 8.760 jam.")
k4.metric("Air / tahun", f"{hitung.format_ringkas(total_air_m3)} m³",
          help="kWh server x WUE.")
k5.metric("Setara listrik (orang)", hitung.format_ringkas(total_orang_listrik),
          help=f"Dibagi {hitung.format_angka(kwh_per_kapita)} kWh/orang/tahun.")

st.caption(
    f"💧 Air sebanyak itu setara kebutuhan harian **{hitung.format_ringkas(total_orang_air)} orang** "
    f"({liter_per_orang} L/orang/hari). Data: {len(df_mentah)} fasilitas dari sumber publik; "
    f"{(df_mentah['keyakinan'] == 'rendah').sum()} di antaranya kapasitasnya estimasi kasar."
)

tab_peta, tab_listrik, tab_air, tab_warga, tab_data, tab_cara = st.tabs(
    ["🗺️ Peta", "⚡ Listrik", "💧 Air", "🏘️ Dampak ke Warga", "📋 Data & Sumber", "🧭 Cara Kerja"]
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
                "Peta ini cuma **scatter plot** (titik-titik) yang ditempel di atas peta dunia. "
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
            st.markdown(
                f"Dengan slider sekarang (utilisasi **{utilisasi:.2f}**, PUE **{pue:.2f}**), "
                f"fasilitas 10 MW ≈ **{hitung.listrik_tahunan_gwh(10, utilisasi, pue):.1f} GWh/tahun**. "
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

    pilihan = st.selectbox("Pilih fasilitas", options=df.sort_values("kapasitas_it_mw", ascending=False)["nama"])
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
# TAB 5: DATA & SUMBER
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
        "⬇️ Unduh data + estimasi (CSV)",
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
# TAB 6: CARA KERJA (diagram alur)
# ----------------------------------------------------------------------------
with tab_cara:
    st.subheader("Bagaimana dashboard ini bekerja?")
    st.graphviz_chart(
        """
        digraph G {
          rankdir=LR; node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11];
          edge [color="#898781"];
          csv1 [label="data/data_center_indonesia.csv\\n(27 fasilitas)", fillcolor="#cde2fb"];
          csv2 [label="data/parameter_asumsi.csv\\n(PUE, WUE, per kapita...)", fillcolor="#cde2fb"];
          muat [label="src/muat_data.py\\nbaca & rapikan tipe data", fillcolor="#f0efec"];
          side [label="Sidebar\\nfilter + slider asumsi", fillcolor="#fde7dc"];
          hit  [label="src/hitung.py\\nlistrik = MW x util x PUE x 8760\\nair = kWh server x WUE", fillcolor="#f0efec"];
          kpi  [label="Angka ringkasan", fillcolor="#d6f3e8"];
          peta [label="Peta (Plotly)", fillcolor="#d6f3e8"];
          graf [label="Grafik listrik & air", fillcolor="#d6f3e8"];
          warga[label="Perbandingan ke warga", fillcolor="#d6f3e8"];
          csv1 -> muat; csv2 -> muat; muat -> hit; side -> hit;
          hit -> kpi; hit -> peta; hit -> graf; hit -> warga;
        }
        """
    )
    st.markdown(
        """
**Bacanya dari kiri ke kanan:**
1. Dua file CSV adalah *sumber kebenaran*. Mau menambah data center? Tambah satu baris di CSV, selesai.
2. `muat_data.py` membaca CSV dan memastikan tipe datanya benar (angka jadi angka, kategori jadi kategori).
3. Sidebar mengubah **parameter**; `hitung.py` mengubah parameter + data jadi **estimasi**.
4. Streamlit menjalankan ulang seluruh `app.py` dari atas setiap kali slider digeser. Itu kenapa semua grafik
   ikut berubah tanpa kode "update" khusus. Konsep ini namanya *reactive rerun*.

Penjelasan lengkap tiap langkah + latihan: lihat `docs/BELAJAR.md` dan `docs/LATIHAN.md` di repo.
        """
    )
