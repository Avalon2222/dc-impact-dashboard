# Sumber data & catatan metodologi

Dikompilasi 31 Oktober 2026. Semua angka kapasitas adalah **kapasitas IT (MW)** yang
dipublikasikan atau diestimasi, bukan pemakaian listrik aktual.

## Cara membaca kolom `keyakinan`

| Nilai | Arti | Contoh |
|---|---|---|
| tinggi | Angka dari operator atau liputan langsung, URL ada di kolom `url_sumber` | DCI H1 83 MW, DayOne Batam 28 MW, BDx CGK3 2 MW, NeutraDC Batam 17/51 MW |
| sedang | Direktori industri (Baxtel, Datacentermap) atau sumber sekunder | Equinix JK1 16 MW, EdgeConneX JKT02 57 MW, PDG JC2 22 MW |
| rendah | Kapasitas tidak dipublikasikan atau belum sempat diverifikasi ulang; angka = estimasi kasar | AWS, Microsoft, Google, NeutraDC enterprise, Biznet |

Kolom `catatan` selalu menjelaskan kalau angkanya estimasi. Koordinat (`lat`, `lon`) adalah
perkiraan area kawasan/kota, **bukan alamat persis**, dan cukup untuk peta skala nasional.

## Sumber utama per fasilitas

Lihat kolom `sumber` dan `url_sumber` di `data_center_indonesia.csv`. Ringkasnya:

- **DCI Indonesia** – liputan peluncuran JK5 (Southeast Asia Infrastructure), direktori Baxtel untuk kampus H2 Karawang dan rencana Bintan.
- **Batam** – DatacenterDynamics (NeutraDC Nxera 17 MW fase awal / 51 MW), W.Media (GDS/DayOne 28 MW), Baxtel (PDG BT1), The Jakarta Post (kesepakatan 450 MW BP Batam-PLN, April 2026).
- **Hyperscaler** – siaran pers Microsoft (Indonesia Central, Mei 2025), Baxtel (AWS Sukamahi), DatacenterDynamics (Google Jakarta). Ketiganya tidak mengumumkan MW; angka di dataset adalah estimasi kasar.
- **Lainnya** – Baxtel (Equinix JK1, Digital Edge EDGE2, tabel pasar Jakarta untuk EdgeConneX), Datacentermap (Bekasi, Jakarta), BDx (situs resmi), Data Centre Magazine (PDG JC2), TelecomTalk (Edgnex 15 MW), CNBC Indonesia (Telkom/NeutraDC Cikarang).

## Angka pembanding nasional

| Angka | Nilai | Sumber |
|---|---|---|
| Kapasitas DC terpasang Indonesia 1H 2026 | ~580 MW (55% di Jakarta) | Brights / Cushman & Wakefield |
| Pipeline Jakarta | 709 MW (H1 2025) | Real Estate Asia (Cushman & Wakefield) |
| Listrik per kapita Indonesia 2024 | 1.411 kWh | Kementerian ESDM via Kontan |
| Kebutuhan air domestik | 150 L/orang/hari (kota besar), minimum 60 L | SNI 03-6981-2004; Permen PU 122/2015 |
| WUE rata-rata industri | 1,8 L/kWh | US DOE via AKCP / Data Center Knowledge |
| Konsumsi listrik DC global 2024 → 2030 | 415 TWh → 945 TWh | IEA, Energy and AI (April 2025) |

## Data untuk model prediksi (ditambahkan November 2026)

| File | Isi | Sumber | Cara diperbarui |
|---|---|---|---|
| `pue_google_kuartalan.csv` | PUE kuartalan & TTM per kampus Google, 2008–sekarang (per kampus sejak Q2 2016) | [Google Data Center Efficiency](https://www.google.com/about/datacenters/efficiency/) | otomatis, `scripts/ambil_pue_google.py` |
| `meta_listrik_air_tahunan.csv` | Listrik (MWh) dan air yang diambil (megaliter) per situs Meta, 2020–2024 | [Meta 2025 Environmental Data Index](https://sustainability.atmeta.com/asset/2025-environmental-data-index/), bagian 2.1 dan 3.1 | manual, disalin dari PDF |
| `lokasi_kampus.csv` | Koordinat perkiraan kampus Google & situs Meta | kompilasi dari pengumuman lokasi masing-masing | manual |
| `iklim_kuartalan.csv` | Ringkasan iklim per lokasi per kuartal & tahun (suhu, RH, titik embun, bola basah, cooling degree days) | [NASA POWER Daily API](https://power.larc.nasa.gov/) (reanalisis MERRA-2, ~0,5°) | otomatis, `scripts/ambil_iklim.py` |
| `prediksi_lokasi.csv`, `evaluasi_*_oof.csv` | Keluaran model | `scripts/latih_model.py` | otomatis |
| `dc_impact.duckdb` | Semua tabel di atas dalam satu database | `scripts/bangun_db.py` | otomatis |

Catatan kejujuran untuk bagian ini:

- Intensitas air Meta dihitung sebagai **liter per kWh listrik total** fasilitas (air ÷ listrik), bukan WUE resmi
  (per kWh listrik IT). Dengan PUE Meta ≈ 1,08 selisihnya kecil, tetapi tetap bukan angka yang sama persis.
- Angka Meta 2020 dibulatkan oleh Meta sendiri (ribuan). Situs dengan listrik < 50 GWh/tahun dikeluarkan dari data
  latih karena masih fase pembangunan.
- Koordinat kampus Google/Meta adalah perkiraan kota/kawasan, cukup untuk mengambil iklim pada resolusi ~0,5°.
- Nama kampus Google yang berubah antar laporan disamakan di `ambil_pue_google.py` (misalnya "Lowcountry" →
  "Berkeley County"). Baris placeholder ("RLF- New Campus") dibuang.
- Prediksi PUE untuk Indonesia adalah perkiraan **kelas hyperscale** (seperti Google) di iklim lokasi itu. Fasilitas
  kolokasi biasa umumnya lebih tinggi. Model WUE tidak lolos gerbang kelayakan, jadi `wue_prediksi` hanyalah rata-rata
  situs Meta; lihat `models/metrik.json`.

## Yang sengaja TIDAK dilakukan

- Tidak mengklaim pemakaian air aktual fasilitas manapun; semua angka air adalah skenario WUE.
- Tidak memasukkan fasilitas yang hanya rumor.
- Tidak menghitung emisi CO₂ (butuh bauran listrik per wilayah; ada di rencana berikutnya).

## Cara memperbarui

1. Tambah/ubah baris di `data_center_indonesia.csv`. Kolom wajib: `nama, operator, kabupaten_kota, provinsi, lat, lon, kapasitas_it_mw, status, tahun, keyakinan`.
2. Jalankan `python scripts/pipeline.py --tanpa-unduh` — validasi menolak koordinat di luar Indonesia atau kapasitas ≤ 0,
   lalu model dilatih ulang dan database dibangun ulang.
3. Jalankan `python -m pytest tests/` dan `streamlit run app.py`, cek petanya.
4. Untuk memperbarui PUE Google dan iklim, jalankan pipeline tanpa `--tanpa-unduh` (atau tunggu GitHub Actions hari Senin).
