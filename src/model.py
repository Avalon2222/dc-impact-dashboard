"""
model.py - Fitur dan pemuatan model prediksi PUE & WUE dari iklim.

Ide dasarnya: pendingin data center bekerja lebih berat di udara panas-lembap.
Google mempublikasikan PUE kuartalan tiap kampus, Meta mempublikasikan listrik
dan air tahunan tiap situs. Keduanya digabung dengan iklim lokasi masing-masing
(NASA POWER) menjadi data latih. Model yang sudah dilatih lalu dipakai untuk
menebak PUE/WUE kelas hyperscale di iklim lokasi data center Indonesia.

Pelatihan dan evaluasi ada di scripts/latih_model.py. File ini hanya berisi
hal yang dipakai bersama oleh skrip, aplikasi Streamlit, dan API:
  - daftar fitur
  - fungsi menyiapkan fitur dari tabel iklim
  - fungsi memuat model dan memprediksi
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DIR_MODEL = ROOT / "models"

# Fitur iklim yang sama dipakai dua model; PUE menambah umur kampus (fase ramp-up) dan tahun (tren teknologi).
FITUR_IKLIM = [
    "suhu_rata", "suhu_maks_rata", "rh_rata", "titik_embun_rata",
    "bola_basah_rata", "bola_basah_p90", "hari_panas_lembap", "cdd18",
]
FITUR_PUE = FITUR_IKLIM + ["umur_kuartal", "tahun"]
# WUE hanya punya ~70 baris data latih, jadi fiturnya sengaja sedikit dan punya alasan fisik:
# bola basah (pendingin evaporatif), cooling degree days (beban pendingin), RH (kebutuhan pelembapan).
FITUR_WUE = ["bola_basah_rata", "rh_rata", "cdd18", "tahun"]
UMUR_MATANG = 16  # kuartal; di atas ini kampus dianggap sudah stabil


def siapkan_fitur_pue(iklim: pd.DataFrame, umur_kuartal: int = UMUR_MATANG, tahun: int | None = None) -> pd.DataFrame:
    """Dari baris iklim kuartalan (kolom FITUR_IKLIM) buat tabel fitur untuk model PUE."""
    x = iklim[FITUR_IKLIM].copy()
    x["umur_kuartal"] = umur_kuartal
    x["tahun"] = tahun if tahun is not None else iklim["tahun"].values
    return x[FITUR_PUE]


def siapkan_fitur_wue(iklim: pd.DataFrame, tahun: int | None = None) -> pd.DataFrame:
    """Dari baris iklim tahunan (kuartal = 0) buat tabel fitur untuk model WUE."""
    x = iklim[FITUR_IKLIM].copy()
    x["tahun"] = tahun if tahun is not None else iklim["tahun"].values
    return x[FITUR_WUE]


def muat_model(nama: str):
    """Muat models/model_<nama>.joblib. Mengembalikan None kalau belum ada."""
    path = DIR_MODEL / f"model_{nama}.joblib"
    if not path.exists():
        return None
    return joblib.load(path)


def muat_metrik() -> dict | None:
    path = DIR_MODEL / "metrik.json"
    return json.loads(path.read_text()) if path.exists() else None


def prediksi_pue(fitur: pd.DataFrame, model=None) -> pd.Series:
    model = model or muat_model("pue")
    if model is None:
        raise FileNotFoundError("Model PUE belum dilatih; jalankan python scripts/latih_model.py")
    return pd.Series(model.predict(fitur[FITUR_PUE]), index=fitur.index, name="pue_prediksi")


def prediksi_wue(fitur: pd.DataFrame, model=None) -> pd.Series:
    model = model or muat_model("wue")
    if model is None:
        raise FileNotFoundError("Model WUE belum dilatih; jalankan python scripts/latih_model.py")
    return pd.Series(model.predict(fitur[FITUR_WUE]), index=fitur.index, name="wue_prediksi").clip(lower=0)
