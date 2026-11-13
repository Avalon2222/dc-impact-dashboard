"""
pipeline.py - Menjalankan seluruh alur data dari ujung ke ujung.

    ambil PUE Google  ─┐
    ambil iklim NASA  ─┼─> validasi CSV ─> latih model ─> bangun DuckDB
    data Meta (CSV)   ─┘

Setiap langkah adalah fungsi kecil yang bisa dijalankan sendiri-sendiri:

    python scripts/pipeline.py                 # semua langkah
    python scripts/pipeline.py --tanpa-unduh   # lewati langkah yang butuh internet
    python scripts/pipeline.py --langkah validasi model db

GitHub Actions (.github/workflows/perbarui-data.yml) menjalankan skrip ini
tiap minggu dan membuat commit kalau ada data yang berubah.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PYTHON = sys.executable

KOLOM_WAJIB_FASILITAS = ["nama", "operator", "kabupaten_kota", "provinsi", "lat", "lon",
                         "kapasitas_it_mw", "status", "tahun", "keyakinan"]


def jalankan_skrip(nama: str) -> None:
    """Jalankan skrip lain di folder scripts/ sebagai proses terpisah (supaya bisa dites sendiri)."""
    subprocess.run([PYTHON, str(ROOT / "scripts" / nama)], check=True, cwd=ROOT)


class DataTidakValid(ValueError):
    """Data gagal validasi. Pipeline berhenti supaya data rusak tidak ikut dipakai model dan dashboard."""


def _pastikan(kondisi, pesan: str) -> None:
    # Bukan `assert`: assert hilang kalau Python dijalankan dengan -O, padahal validasi ini wajib.
    if not kondisi:
        raise DataTidakValid(pesan)


def langkah_unduh_pue() -> None:
    jalankan_skrip("ambil_pue_google.py")


def langkah_unduh_iklim() -> None:
    jalankan_skrip("ambil_iklim.py")


def langkah_validasi() -> None:
    """Periksa kualitas data sebelum dipakai: kolom wajib ada, nilai masuk akal, tidak ada duplikat."""
    fasilitas = pd.read_csv(DATA / "data_center_indonesia.csv")
    hilang = [k for k in KOLOM_WAJIB_FASILITAS if k not in fasilitas.columns]
    _pastikan(not hilang, f"Kolom wajib hilang di data_center_indonesia.csv: {hilang}")
    _pastikan(fasilitas["lat"].between(-11, 6).all() and fasilitas["lon"].between(95, 141).all(), "Koordinat di luar Indonesia")
    _pastikan((fasilitas["kapasitas_it_mw"] > 0).all(), "Kapasitas harus > 0")
    _pastikan(fasilitas["status"].isin(["beroperasi", "dibangun", "rencana"]).all(), "Status tidak dikenal")
    _pastikan(not fasilitas["nama"].duplicated().any(), "Nama fasilitas duplikat")

    pue = pd.read_csv(DATA / "pue_google_kuartalan.csv")
    _pastikan(len(pue) >= 500, "Data PUE Google terlalu sedikit")
    _pastikan(pue["pue_kuartalan"].dropna().between(1.0, 2.0).all(), "PUE di luar rentang wajar")
    _pastikan(not pue.duplicated(["kampus", "tahun", "kuartal"]).any(), "Duplikat PUE kampus/tahun/kuartal")

    lokasi = pd.read_csv(DATA / "lokasi_kampus.csv")
    tanpa_lokasi = set(pue["kampus"]) - set(lokasi["kampus"]) - {"Fleet"}
    _pastikan(not tanpa_lokasi, f"Kampus Google tanpa koordinat di lokasi_kampus.csv: {sorted(tanpa_lokasi)}")

    iklim = pd.read_csv(DATA / "iklim_kuartalan.csv")
    _pastikan(iklim["bola_basah_rata"].between(-40, 35).all(), "Suhu bola basah di luar rentang wajar")
    _pastikan((iklim["jumlah_hari"] >= 85).all(), "Ada kuartal/tahun yang tidak lengkap")
    print(f"  validasi OK: {len(fasilitas)} fasilitas, {len(pue)} baris PUE, {len(iklim)} baris iklim")


def langkah_model() -> None:
    jalankan_skrip("latih_model.py")


def langkah_db() -> None:
    jalankan_skrip("bangun_db.py")


LANGKAH = {
    "unduh_pue": (langkah_unduh_pue, True),
    "unduh_iklim": (langkah_unduh_iklim, True),
    "validasi": (langkah_validasi, False),
    "model": (langkah_model, False),
    "db": (langkah_db, False),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pipeline data dc-impact-dashboard")
    parser.add_argument("--langkah", nargs="+", choices=list(LANGKAH), default=list(LANGKAH))
    parser.add_argument("--tanpa-unduh", action="store_true", help="lewati langkah yang butuh internet")
    args = parser.parse_args(argv)

    for nama in args.langkah:
        fungsi, butuh_internet = LANGKAH[nama]
        if butuh_internet and args.tanpa_unduh:
            print(f"[{nama}] dilewati (--tanpa-unduh)")
            continue
        mulai = time.time()
        print(f"[{nama}] mulai ...")
        fungsi()
        print(f"[{nama}] selesai dalam {time.time() - mulai:.1f} detik")
    return 0


if __name__ == "__main__":
    sys.exit(main())
