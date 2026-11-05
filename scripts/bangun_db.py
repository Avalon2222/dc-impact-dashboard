"""
bangun_db.py - Membangun database DuckDB dari semua file CSV di folder data/.

Mengapa pakai database kalau CSV sudah cukup?
  1. Query SQL (JOIN, GROUP BY, window function) jauh lebih ringkas daripada
     pandas untuk pertanyaan analitis seperti "total kapasitas per provinsi
     menurut status" atau "PUE rata-rata per kuartal per kampus".
  2. DuckDB hanya satu file (data/dc_impact.duckdb), tidak perlu server,
     dan tetap bisa dibaca di Streamlit Cloud maupun lewat API.
  3. Semua tabel punya skema yang jelas, jadi kesalahan tipe data ketahuan
     saat database dibangun, bukan saat grafik sudah tampil.

Skema (lihat juga src/db.py):
  fasilitas            1 baris = 1 data center Indonesia (dari data_center_indonesia.csv)
  parameter            asumsi PUE, WUE, dll
  pue_google           PUE kuartalan per kampus Google 2008-2026
  meta_situs           listrik (MWh) & air (megaliter) tahunan per situs Meta 2020-2024
  lokasi_kampus        koordinat kampus Google & situs Meta
  iklim                ringkasan iklim per lokasi x tahun x kuartal (kuartal 0 = setahun)
  prediksi_lokasi      hasil model PUE/WUE untuk lokasi Indonesia (kalau model sudah dilatih)
  metrik_model         metrik evaluasi model (kalau model sudah dilatih)

Jalankan:  python scripts/bangun_db.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MODELS = ROOT / "models"
PATH_DB = DATA / "dc_impact.duckdb"


def kunci_lokasi(lat: float, lon: float) -> str:
    return f"{lat:.2f},{lon:.2f}"


def muat_tabel() -> dict[str, pd.DataFrame]:
    """Baca semua CSV, tambahkan kolom lokasi_id supaya bisa di-JOIN dengan tabel iklim."""
    fasilitas = pd.read_csv(DATA / "data_center_indonesia.csv")
    fasilitas["lokasi_id"] = [kunci_lokasi(a, b) for a, b in zip(fasilitas["lat"], fasilitas["lon"])]

    lokasi_kampus = pd.read_csv(DATA / "lokasi_kampus.csv")
    lokasi_kampus["lokasi_id"] = [kunci_lokasi(a, b) for a, b in zip(lokasi_kampus["lat"], lokasi_kampus["lon"])]

    tabel = {
        "fasilitas": fasilitas,
        "parameter": pd.read_csv(DATA / "parameter_asumsi.csv"),
        "pue_google": pd.read_csv(DATA / "pue_google_kuartalan.csv"),
        "meta_situs": pd.read_csv(DATA / "meta_listrik_air_tahunan.csv"),
        "lokasi_kampus": lokasi_kampus,
        "iklim": pd.read_csv(DATA / "iklim_kuartalan.csv"),
    }

    prediksi = DATA / "prediksi_lokasi.csv"
    if prediksi.exists():
        tabel["prediksi_lokasi"] = pd.read_csv(prediksi)

    metrik = MODELS / "metrik.json"
    if metrik.exists():
        isi = json.loads(metrik.read_text())
        baris = []
        for target, info in isi["model"].items():
            for nama_model, m in info["evaluasi"].items():
                baris.append({"target": target, "model": nama_model, "terpilih": nama_model == info["terpilih"], **m})
        tabel["metrik_model"] = pd.DataFrame(baris)
    return tabel


def bangun(koneksi: duckdb.DuckDBPyConnection, tabel: dict[str, pd.DataFrame]) -> None:
    """Tulis setiap DataFrame jadi tabel, lalu buat VIEW yang sering dipakai."""
    for nama, df in tabel.items():
        koneksi.register(f"_{nama}", df)
        koneksi.execute(f"CREATE OR REPLACE TABLE {nama} AS SELECT * FROM _{nama}")
        koneksi.unregister(f"_{nama}")

    # VIEW estimasi dengan parameter default: rumus yang sama dengan src/hitung.py, ditulis dalam SQL.
    koneksi.execute("""
        CREATE OR REPLACE VIEW v_estimasi AS
        WITH p AS (
            SELECT
                MAX(CASE WHEN parameter = 'utilisasi' THEN nilai END) AS utilisasi,
                MAX(CASE WHEN parameter = 'pue' THEN nilai END) AS pue,
                MAX(CASE WHEN parameter = 'wue' THEN nilai END) AS wue,
                MAX(CASE WHEN parameter = 'listrik_per_kapita_kwh_tahun' THEN nilai END) AS kwh_per_kapita,
                MAX(CASE WHEN parameter = 'air_per_orang_liter_hari' THEN nilai END) AS liter_per_orang
            FROM parameter
        )
        SELECT
            f.id, f.nama, f.operator, f.kabupaten_kota, f.provinsi, f.status, f.tahun, f.keyakinan,
            f.lokasi_id, f.kapasitas_it_mw,
            f.kapasitas_it_mw * p.utilisasi * p.pue * 8760 / 1000            AS listrik_gwh_tahun,
            f.kapasitas_it_mw * p.utilisasi * 8760 * p.wue                   AS air_m3_tahun,
            f.kapasitas_it_mw * p.utilisasi * p.pue * 8760 * 1000 / p.kwh_per_kapita AS setara_orang_listrik,
            f.kapasitas_it_mw * p.utilisasi * 8760 * p.wue * 1000 / (p.liter_per_orang * 365) AS setara_orang_air
        FROM fasilitas f CROSS JOIN p
    """)

    # VIEW intensitas air Meta: liter per kWh listrik total (mendekati WUE).
    koneksi.execute("""
        CREATE OR REPLACE VIEW v_meta_intensitas_air AS
        SELECT m.situs, m.tahun, m.listrik_mwh, m.air_megaliter,
               m.air_megaliter * 1e6 / (m.listrik_mwh * 1e3) AS liter_per_kwh,
               l.lokasi_id, l.negara
        FROM meta_situs m
        JOIN lokasi_kampus l ON l.kampus = m.situs AND l.perusahaan = 'meta'
        WHERE m.listrik_mwh > 50000
    """)


def main() -> int:
    tabel = muat_tabel()
    if PATH_DB.exists():
        PATH_DB.unlink()
    with duckdb.connect(str(PATH_DB)) as koneksi:
        bangun(koneksi, tabel)
        ringkasan = koneksi.execute(
            "SELECT table_name, estimated_size FROM duckdb_tables() ORDER BY table_name"
        ).fetchall()
    for nama, n in ringkasan:
        print(f"  {nama:<18} {n:>6} baris")
    print(f"Database tersimpan -> {PATH_DB.relative_to(ROOT)} ({PATH_DB.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
