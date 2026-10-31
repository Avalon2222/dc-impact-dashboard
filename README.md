# 🏭 Dashboard Dampak Data Center Indonesia

> Peta interaktif dan estimasi konsumsi **listrik** dan **air** data center di Indonesia,
> dibandingkan dengan kebutuhan **warga**. Dibangun dengan Python, pandas, Plotly, dan Streamlit.

*An interactive dashboard estimating the electricity and water footprint of Indonesian data
centers, compared against residents' needs. Built with Python, pandas, Plotly and Streamlit.*

![Peta data center Indonesia](docs/screenshots/01_peta.png)

## Kenapa project ini ada?

Indonesia sedang jadi tujuan investasi data center (koridor Bekasi-Cikarang-Karawang dan Batam).
Data center butuh listrik besar dan, tergantung teknologi pendinginnya, air dalam jumlah besar.
Dua kebutuhan itu bersaing dengan kebutuhan warga di daerah yang sama. Dashboard ini mencoba
menjawab pertanyaan sederhana secara visual:

1. **Di mana** data center Indonesia berada, dan seberapa besar?
2. **Berapa listrik dan air** yang kira-kira mereka pakai?
3. **Setara berapa orang / rumah tangga** kebutuhan itu?
4. Apa yang berubah kalau **asumsi** (PUE, WUE, utilisasi) diubah?

Project ini lahir dari rasa penasaran pribadi setelah membaca berita investasi data center di Bekasi dan Batam.

## Fitur

| Tab | Isi |
|---|---|
| 🗺️ Peta | Scatter map: ukuran = kapasitas IT (MW), warna = status (beroperasi / dibangun / rencana) |
| ⚡ Listrik | 15 fasilitas terboros, total per kabupaten/kota, kapasitas beroperasi vs pipeline |
| 💧 Air | Estimasi air pendingin per fasilitas + 3 skenario teknologi pendingin (WUE 0,3 / 1,8 / 3,5) |
| 🏘️ Dampak ke Warga | Pilih satu fasilitas → setara berapa orang, rumah tangga, truk tangki; skala log vs RW/kelurahan/kecamatan |
| 📋 Data & Sumber | Tabel lengkap + link sumber + tingkat keyakinan + unduh CSV + daftar keterbatasan |
| 🧭 Cara Kerja | Diagram alur data → rumus → grafik |
| 🎓 Mode belajar | Toggle di sidebar: tiap grafik dapat expander berisi rumus, potongan kode, dan latihan |

Semua asumsi bisa digeser lewat slider di sidebar dan seluruh dashboard langsung menghitung ulang.

![Tab listrik](docs/screenshots/02_listrik.png)
![Tab dampak ke warga](docs/screenshots/04_warga.png)

## Cara menjalankan

```bash
git clone <url-repo-ini>
cd dc-impact-dashboard
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Buka `http://localhost:8501`. Jalankan tes dengan `python -m pytest tests/ -v`.

## Cara kerja (ringkas)

```mermaid
flowchart LR
    A[data/data_center_indonesia.csv] --> C[src/muat_data.py]
    B[data/parameter_asumsi.csv] --> C
    C --> D[src/hitung.py<br/>listrik = MW × util × PUE × 8760<br/>air = kWh server × WUE]
    S[Sidebar: filter + slider] --> D
    D --> E[Angka ringkasan]
    D --> F[Peta Plotly]
    D --> G[Grafik listrik & air]
    D --> H[Perbandingan ke warga]
```

Rumus utama (semua ada di `src/hitung.py`, lengkap dengan docstring dan contoh angka):

| Besaran | Rumus | Default |
|---|---|---|
| Listrik per tahun (GWh) | kapasitas IT (MW) × utilisasi × PUE × 8.760 jam ÷ 1.000 | utilisasi 0,6; PUE 1,5 |
| Air per tahun (m³) | kapasitas IT (MW) × utilisasi × 8.760 × 1.000 × WUE ÷ 1.000 | WUE 1,8 L/kWh |
| Setara orang (listrik) | GWh × 1.000.000 ÷ 1.411 kWh/orang/tahun | ESDM 2024 |
| Setara orang (air) | m³ × 1.000 ÷ (150 L/orang/hari × 365) | SNI kota besar |

## Data dan kejujuran soal estimasi

Dataset (`data/data_center_indonesia.csv`) berisi **27 fasilitas** yang dikumpulkan dari sumber publik
(siaran pers operator, liputan media, direktori industri) per Oktober 2026. Setiap baris punya
kolom `keyakinan`:

- **tinggi** – angka dari operator / liputan langsung, URL tercantum.
- **sedang** – direktori industri atau sumber sekunder.
- **rendah** – kapasitas **tidak dipublikasikan** (misalnya AWS, Microsoft, Google); angka adalah
  estimasi kasar kami dan ditulis terang-terangan di kolom `catatan`.

Koordinat adalah perkiraan area, bukan alamat persis. Daftar sumber dan alasan tiap angka ada di
[`data/SUMBER_DATA.md`](data/SUMBER_DATA.md). Dataset ini bukan daftar lengkap; mohon buka *issue*
atau *pull request* kalau punya angka yang lebih baik.

Keterbatasan penting: PUE dan WUE per fasilitas di Indonesia hampir tidak pernah dipublikasikan,
jadi semua angka air adalah **skenario**, bukan pengukuran. Itu justru pertanyaan lanjutan yang menarik.

## Struktur repo

```
dc-impact-dashboard/
├── app.py                  # tampilan Streamlit (baca dari atas ke bawah)
├── src/
│   ├── muat_data.py        # baca & rapikan CSV
│   └── hitung.py           # rumus estimasi (murni Python, mudah dites)
├── data/
│   ├── data_center_indonesia.csv
│   ├── parameter_asumsi.csv
│   └── SUMBER_DATA.md
├── tests/test_hitung.py    # 9 tes pytest
├── docs/
│   ├── BELAJAR.md          # panduan belajar step by step
│   ├── LATIHAN.md          # latihan kecil + kunci jawaban
│   └── screenshots/
└── requirements.txt
```

## Belajar dari project ini

Jika kamu baru mulai Python/data, baca [`docs/BELAJAR.md`](docs/BELAJAR.md) dulu (alur, konsep
pandas & Streamlit, kenapa kodenya dipisah begini), lalu kerjakan [`docs/LATIHAN.md`](docs/LATIHAN.md).
Nyalakan **Mode belajar** di sidebar supaya tiap grafik menunjukkan kode di baliknya.

## Rencana berikutnya

- [ ] Verifikasi ulang fasilitas berkeyakinan rendah; tambah fasilitas kecil (enterprise/edge).
- [ ] Tambah sumber listrik per wilayah (bauran PLTU vs terbarukan) → estimasi emisi CO₂.
- [ ] Tambah lapisan ketersediaan air (cekungan air tanah kritis, wilayah PDAM) untuk konteks dampak.
- [ ] Deploy ke Streamlit Community Cloud.

## Lisensi

Kode: MIT. Data: kompilasi dari sumber publik yang disebutkan; gunakan dengan menyebut sumber aslinya.
