"""
muat_data.py - Fungsi untuk membaca file CSV di folder data/.

Kenapa dipisah dari app.py?
  Supaya logika "baca data" bisa dites sendiri (lihat tests/), dan app.py
  tetap fokus ke tampilan. Ini kebiasaan bagus: pisahkan DATA, LOGIKA, TAMPILAN.
"""

from pathlib import Path

import pandas as pd

# Path(__file__) = lokasi file ini. .parent.parent = naik dua folder = root proyek.
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

# Urutan status yang masuk akal secara waktu (dipakai untuk urutan legenda/warna).
URUTAN_STATUS = ["beroperasi", "dibangun", "rencana"]
URUTAN_KEYAKINAN = ["tinggi", "sedang", "rendah"]


def muat_data_center(path: Path | None = None) -> pd.DataFrame:
    """Baca daftar data center dan rapikan tipe datanya.

    Mengembalikan DataFrame dengan satu baris = satu fasilitas data center.
    """
    path = path or DATA_DIR / "data_center_indonesia.csv"
    df = pd.read_csv(path)

    # Pastikan kolom angka memang bertipe angka (kalau ada yang kosong jadi NaN).
    for kolom in ["lat", "lon", "kapasitas_it_mw", "tahun"]:
        df[kolom] = pd.to_numeric(df[kolom], errors="coerce")

    # Kolom kategori diberi urutan supaya legenda grafik konsisten.
    df["status"] = pd.Categorical(df["status"], categories=URUTAN_STATUS, ordered=True)
    df["keyakinan"] = pd.Categorical(df["keyakinan"], categories=URUTAN_KEYAKINAN, ordered=True)

    # Kolom teks yang kosong (NaN) diganti string kosong supaya tooltip rapi.
    for kolom in ["catatan", "url_sumber", "sumber"]:
        df[kolom] = df[kolom].fillna("")

    return df


def muat_parameter(path: Path | None = None) -> dict:
    """Baca parameter asumsi (PUE, WUE, dll) menjadi dict {nama: nilai}.

    Contoh hasil: {"pue": 1.5, "wue": 1.8, ...}
    """
    path = path or DATA_DIR / "parameter_asumsi.csv"
    df = pd.read_csv(path)
    return dict(zip(df["parameter"], df["nilai"]))


def muat_parameter_lengkap(path: Path | None = None) -> pd.DataFrame:
    """Versi lengkap tabel parameter (dengan sumber dan catatan) untuk ditampilkan."""
    path = path or DATA_DIR / "parameter_asumsi.csv"
    return pd.read_csv(path).fillna("")
