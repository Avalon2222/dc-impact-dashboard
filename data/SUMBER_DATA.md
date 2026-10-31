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

## Yang sengaja TIDAK dilakukan

- Tidak mengklaim pemakaian air aktual fasilitas manapun; semua angka air adalah skenario WUE.
- Tidak memasukkan fasilitas yang hanya rumor.
- Tidak menghitung emisi CO₂ (butuh bauran listrik per wilayah; ada di rencana berikutnya).

## Cara memperbarui

1. Tambah/ubah baris di `data_center_indonesia.csv`. Kolom wajib: `nama, operator, kabupaten_kota, provinsi, lat, lon, kapasitas_it_mw, status, tahun, keyakinan`.
2. Jalankan `python -m pytest tests/` — tes akan menolak koordinat di luar Indonesia atau kapasitas ≤ 0.
3. Jalankan `streamlit run app.py` dan cek petanya.
