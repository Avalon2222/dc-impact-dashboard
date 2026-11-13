"""Tes penyusunan data latih model PUE dan WUE (scripts/latih_model.py)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import latih_model  # noqa: E402
from src.model import FITUR_PUE, FITUR_WUE, UMUR_MATANG  # noqa: E402


def test_kunci_lokasi_dua_desimal():
    assert latih_model.kunci_lokasi(-6.2088, 106.8456) == "-6.21,106.85"
    assert latih_model.kunci_lokasi(1, 2) == "1.00,2.00"


def test_data_latih_pue_tanpa_fleet_dan_lengkap():
    df = latih_model.data_latih_pue()
    assert len(df) > 0
    assert "Fleet" not in set(df["kampus"])
    assert df["pue_kuartalan"].notna().all()
    # Semua fitur yang dipakai model harus tersedia setelah JOIN dengan iklim.
    kolom_iklim = [f for f in FITUR_PUE if f not in ("umur_kuartal", "tahun")]
    assert set(kolom_iklim) <= set(df.columns)


def test_data_latih_pue_umur_kampus_dibatasi():
    df = latih_model.data_latih_pue()
    assert df["umur_kuartal"].min() == 0
    assert df["umur_kuartal"].max() <= UMUR_MATANG
    # Kuartal pertama tiap kampus selalu berumur 0.
    assert (df.groupby("kampus")["umur_kuartal"].min() == 0).all()


def test_data_latih_wue_buang_situs_kecil():
    df = latih_model.data_latih_wue()
    assert len(df) > 0
    assert (df["listrik_mwh"] > 50_000).all()
    hitung_ulang = df["air_megaliter"] * 1e6 / (df["listrik_mwh"] * 1e3)
    assert (df["liter_per_kwh"] - hitung_ulang).abs().max() < 1e-9
    assert set(f for f in FITUR_WUE if f != "tahun") <= set(df.columns)
