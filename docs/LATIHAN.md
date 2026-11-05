# 🏋️ Latihan

Diurutkan dari mudah ke sulit. Tiap latihan ada petunjuk, dan kunci jawaban di bagian yang bisa dibuka.
Usahakan mencoba minimal 10 menit sebelum membuka kunci. Setelah tiap latihan: jalankan `python -m pytest tests/`
dan `streamlit run app.py`.

---

### Latihan 1 — Tambah satu data center (edit CSV saja) ⭐

Tambahkan baris baru ke `data/data_center_indonesia.csv` untuk fasilitas fiktif:
**"Latihan DC Bandung"**, operator "Kamu", Kota Bandung, Jawa Barat, lat `-6.9175`, lon `107.6191`,
10 MW, status `rencana`, tahun 2028, tipe `kolokasi`, keyakinan `rendah`.

Lalu buka dashboard, centang status "Rencana", dan cari titiknya di peta.

<details><summary>Petunjuk</summary>
Salin baris terakhir, ganti nilainya. Kolom yang mengandung koma harus dibungkus tanda kutip. Kolom `url_sumber` boleh kosong.
</details>

<details><summary>Kunci</summary>

```
28,Latihan DC Bandung,Kamu,Bandung,Kota Bandung,Jawa Barat,-6.9175,107.6191,10,rencana,2028,kolokasi,rendah,Latihan,,"Fasilitas fiktif untuk latihan."
```
Kalau tes `test_dataset_bisa_dimuat_dan_valid` masih hijau, berarti koordinatmu valid.
</details>

---

### Latihan 2 — Ganti angka pembanding ⭐

Di tab Dampak ke Warga, pembanding "1 kecamatan" pakai ±25.000 rumah tangga. Ubah jadi ±20.000 dan
tambahkan satu baris pembanding baru: **"1 RT (±50 rumah)"**.

<details><summary>Petunjuk</summary>
Cari `banding = pd.DataFrame({` di `app.py`. Ada dua list sejajar: `Pembanding` dan `kwh`. Tambahkan elemen di posisi yang sama di keduanya. Jangan lupa panjang list `jenis` harus ikut bertambah.
</details>

<details><summary>Kunci</summary>

```python
banding = pd.DataFrame({
    "Pembanding": ["1 rumah tangga", "1 RT (±50 rumah)", "1 RW (±250 RT)", "1 kelurahan (±2.500 RT)",
                   "1 kecamatan (±20.000 RT)", f"{baris['nama'][:28]}"],
    "kwh": [kwh_rt, kwh_rt * 50, kwh_rt * 250, kwh_rt * 2500, kwh_rt * 20000, baris["listrik_gwh_tahun"] * 1e6],
})
banding["jenis"] = ["Warga"] * 5 + ["Data center"]
```
</details>

---

### Latihan 3 — Skenario ke-4: tanpa air ⭐⭐

Di tab Air, grafik skenario punya 3 batang. Tambahkan skenario **"Tanpa air (0,0)"** dengan WUE 0.
Apa yang terjadi pada batangnya? Kenapa batangnya tetap ada walau tingginya 0?

<details><summary>Kunci</summary>

```python
skenario = pd.DataFrame({
    "Skenario": ["Tanpa air (0,0)", "Hyperscaler efisien (0,3)", "Rata-rata industri (1,8)", "Boros / tropis (3,5)"],
    "wue": [0.0, 0.3, 1.8, 3.5],
})
```
Batangnya tingginya 0 jadi tidak terlihat, tapi labelnya "0 m³" tetap muncul. Itu justru pesan yang bagus:
teknologi pendingin tanpa air itu ada (closed-loop / udara), tapi biasanya butuh listrik lebih banyak (PUE naik).
</details>

---

### Latihan 4 — Grafik per provinsi ⭐⭐

Di tab Listrik, grafik kanan menjumlahkan per `kabupaten_kota`. Buat grafik serupa tapi per `provinsi`,
taruh di bawahnya.

<details><summary>Petunjuk</summary>
Salin blok `per_kota = (...)` sampai `st.plotly_chart(fig_kota ...)`. Ganti `kabupaten_kota` jadi `provinsi` dan ganti nama variabel supaya tidak bentrok (`per_prov`, `fig_prov`).
</details>

<details><summary>Kunci</summary>

```python
per_prov = (df.groupby("provinsi", observed=True)["listrik_gwh_tahun"]
            .sum().sort_values(ascending=False).reset_index())
fig_prov = px.bar(per_prov, x="listrik_gwh_tahun", y="provinsi", orientation="h",
                  labels={"listrik_gwh_tahun": "GWh per tahun", "provinsi": ""},
                  title="Total per provinsi",
                  color="listrik_gwh_tahun", color_continuous_scale=WARNA_BIRU_SEKUENSIAL)
fig_prov.update_layout(coloraxis_showscale=False, yaxis=dict(autorange="reversed"))
fig_prov.update_traces(marker_line_width=0, text=per_prov["listrik_gwh_tahun"].map(lambda v: hitung.format_angka(v)),
                       textposition="outside")
ruang_label(fig_prov, per_prov["listrik_gwh_tahun"].max())
rapikan(fig_prov, 300)
st.plotly_chart(fig_prov, use_container_width=True)
```
</details>

---

### Latihan 5 — Fungsi baru + tes ⭐⭐

Tambahkan fungsi `emisi_co2_ton(listrik_gwh, faktor_emisi_kg_per_kwh=0.85)` di `src/hitung.py`
(faktor emisi grid Jawa-Bali ≈ 0,85 kg CO₂/kWh; cek angka terbaru di laporan ESDM). Lalu tulis
satu tes di `tests/test_hitung.py`.

<details><summary>Kunci</summary>

```python
# src/hitung.py
def emisi_co2_ton(listrik_gwh: float, faktor_emisi_kg_per_kwh: float = 0.85) -> float:
    """Estimasi emisi CO2 per tahun (ton). 1 GWh = 1.000.000 kWh; 1 ton = 1000 kg."""
    return listrik_gwh * 1_000_000 * faktor_emisi_kg_per_kwh / 1000

# tests/test_hitung.py
def test_emisi_co2():
    # 1 GWh x 0.85 kg/kWh = 850.000 kg = 850 ton
    assert hitung.emisi_co2_ton(1, 0.85) == pytest.approx(850)
```
Tantangan lanjutan: tampilkan sebagai `st.metric` baru di tab Dampak ke Warga.
</details>

---

### Latihan 6 — Tombol reset asumsi ⭐⭐⭐

Tambahkan tombol "Reset asumsi" di sidebar yang mengembalikan semua slider ke nilai default.

<details><summary>Petunjuk</summary>
Streamlit menyimpan nilai widget di `st.session_state` kalau widget diberi `key=`. Beri setiap slider `key="pue"` dst. Tombol: `if st.button("Reset"): st.session_state["pue"] = PARAM["pue"]; ... ; st.rerun()`. Tombolnya harus dibuat SEBELUM slider dirender, atau pakai `on_click=`.
</details>

<details><summary>Kunci</summary>

```python
def reset_asumsi():
    st.session_state["utilisasi"] = float(PARAM["utilisasi"])
    st.session_state["pue"] = float(PARAM["pue"])
    st.session_state["wue"] = float(PARAM["wue"])

st.button("↩️ Reset asumsi", on_click=reset_asumsi)
utilisasi = st.slider("Utilisasi server", 0.1, 1.0, float(PARAM["utilisasi"]), 0.05, key="utilisasi")
pue = st.slider("PUE (efisiensi listrik)", 1.1, 2.5, float(PARAM["pue"]), 0.05, key="pue")
wue = st.slider("WUE (liter air per kWh server)", 0.0, 4.0, float(PARAM["wue"]), 0.1, key="wue")
```
`on_click` dijalankan sebelum skrip rerun, jadi aman mengubah session_state di situ.
</details>

---

### Latihan 7 — Peta: warna menurut keyakinan ⭐⭐⭐

Tambahkan radio button di tab Peta: "Warnai menurut: Status / Keyakinan data". Kalau "Keyakinan"
dipilih, warna lingkaran mengikuti kolom `keyakinan` (tinggi/sedang/rendah) dengan palet sendiri.

<details><summary>Kunci</summary>

```python
WARNA_KEYAKINAN = {"tinggi": "#2a78d6", "sedang": "#eda100", "rendah": "#898781"}
mode_warna = st.radio("Warnai menurut", ["Status", "Keyakinan data"], horizontal=True)
if mode_warna == "Status":
    kolom_warna, peta_warna, urutan = "status_label", {LABEL_STATUS[k]: v for k, v in WARNA_STATUS.items()}, list(LABEL_STATUS.values())
else:
    df["keyakinan_str"] = df["keyakinan"].astype(str)
    kolom_warna, peta_warna, urutan = "keyakinan_str", WARNA_KEYAKINAN, ["tinggi", "sedang", "rendah"]

fig_peta = px.scatter_map(df, lat="lat", lon="lon", size="kapasitas_it_mw", size_max=45,
                          color=kolom_warna, color_discrete_map=peta_warna,
                          category_orders={kolom_warna: urutan}, hover_name="nama", ...)
```
Pelajaran: Plotly hanya butuh *nama kolom*; ganti nama kolom = ganti pengelompokan.
</details>

---

### Latihan 8 — Mini riset (tanpa kode) ⭐⭐⭐

Pilih satu fasilitas berkeyakinan `rendah`. Cari di internet (siaran pers operator, laporan tahunan,
berita, dokumen AMDAL) angka kapasitas yang lebih bisa dipercaya. Perbarui baris CSV-nya: angka,
`keyakinan`, `sumber`, `url_sumber`. Tulis 3 kalimat di `data/SUMBER_DATA.md` tentang apa yang kamu
temukan dan apa yang masih tidak diketahui.

Ini latihan paling berharga: **skill mencari dan menilai sumber**. Kalau ketemu angka
pemakaian air aktual satu fasilitas pun, itu sudah temuan.

---

### Latihan 9 — Query SQL baru ⭐⭐

Buat file `sql/09_pue_singapura_per_tahun.sql` yang menghitung rata-rata PUE kuartalan kampus Singapura
per tahun. Baris komentar pertama jadi judul di tab SQL Explorer.

<details><summary>Kunci jawaban</summary>

```sql
-- PUE rata-rata kampus Singapura per tahun
SELECT tahun, ROUND(AVG(pue_kuartalan), 3) AS pue_rata, COUNT(*) AS kuartal
FROM pue_google
WHERE kampus LIKE 'Singapore%'
GROUP BY tahun
ORDER BY tahun;
```

Jalankan `python -m pytest tests/test_db.py -q`: tes `test_semua_query_tersimpan_jalan` otomatis memeriksa file barumu.
</details>

---

### Latihan 10 — Validasi tambahan di pipeline ⭐⭐

Tambahkan satu pemeriksaan di `langkah_validasi()` (`scripts/pipeline.py`): kolom `tahun` fasilitas harus
antara 2000 dan 2035. Jalankan `python scripts/pipeline.py --langkah validasi`, lalu sengaja ubah satu
tahun di CSV jadi 1900 dan pastikan pipeline berhenti dengan pesan yang jelas. Kembalikan CSV-nya.

<details><summary>Kunci jawaban</summary>

```python
assert fasilitas["tahun"].dropna().between(2000, 2035).all(), "Tahun fasilitas di luar rentang wajar"
```
</details>

---

### Latihan 11 — Kandidat model baru ⭐⭐⭐

Di `scripts/latih_model.py`, tambahkan `KNeighborsRegressor` (dari `sklearn.neighbors`) ke `kandidat()`.
Jalankan `python scripts/latih_model.py`. Apakah ia lolos gerbang kelayakan? Apakah mengalahkan Ridge?
Tulis jawabanmu di satu kalimat komentar di atas fungsi `kandidat()`.

<details><summary>Petunjuk</summary>

```python
from sklearn.neighbors import KNeighborsRegressor
"knn": make_pipeline(StandardScaler(), KNeighborsRegressor(n_neighbors=15)),
```

KNN sangat bergantung pada skala fitur, jadi `StandardScaler` wajib. Perhatikan juga kolom `mae_waktu`:
model yang bagus di cross-validation tapi buruk di uji waktu biasanya "menghafal" tahun.
</details>

---

### Latihan 12 — Endpoint baru di API ⭐⭐⭐

Tambahkan `GET /operator` di `api/main.py` yang mengembalikan total MW dan jumlah fasilitas per operator,
diurutkan dari yang terbesar. Tulis satu tes di `tests/test_api.py`.

<details><summary>Kunci jawaban</summary>

```python
@app.get("/operator", tags=["data"])
def per_operator():
    df = db.jalankan(
        "SELECT operator, COUNT(*) AS fasilitas, SUM(kapasitas_it_mw) AS kapasitas_it_mw "
        "FROM fasilitas GROUP BY operator ORDER BY kapasitas_it_mw DESC"
    )
    return {"jumlah": len(df), "operator": _rapikan(df)}
```

```python
def test_per_operator(klien):
    r = klien.get("/operator").json()
    assert r["jumlah"] > 5 and r["operator"][0]["kapasitas_it_mw"] >= r["operator"][1]["kapasitas_it_mw"]
```
</details>

---

## Sudah selesai semua?

Push ke GitHub. Kalau Latihan 9–12 beres, kamu sudah menyentuh empat hal yang biasanya ditanya saat wawancara
data engineer: SQL, validasi data, evaluasi model, dan API.
