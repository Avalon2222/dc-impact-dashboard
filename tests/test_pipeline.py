"""Tes langkah pipeline yang bisa dijalankan tanpa internet: parser HTML Google, agregasi iklim, validasi."""

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ambil_iklim  # noqa: E402
import ambil_pue_google  # noqa: E402
import pipeline  # noqa: E402

HTML_CONTOH = """
<h2>2025 PUE Yearly Report</h2>
<div data-cy="tabItem"><span>Quarter 01</span>
<table><tr><td>Fleet</td><td>1.08</td><td>1.09</td></tr></table>
<table>
<tr role="row"><td>Hamina, Finland</td><td>1.09</td><td>1.1</td></tr>
<tr role="row"><td>Changua County, Taiwan</td><td>1.1</td><td>1.12</td></tr>
<tr role="row"><td>Mesa, Arizona</td><td>1.22</td></tr>
<tr role="row"><td>RLF- New Campus</td><td>1.5</td></tr>
</table></div>
<div data-cy="tabItem"><span>Quarter 02</span>
<table><tr role="row"><td>Hamina, Finland</td><td>1.10</td><td>1.10</td></tr></table></div>
<h2>2010 PUE Yearly Report</h2>
<div data-cy="tabItem"><span>Quarter 03</span>
<table><tr><td>Fleet-wide quarterly PUE:</td><td>1.20</td></tr>
<tr><td>Fleet-wide trailing twelve-month (TTM) PUE:</td><td>1.17</td></tr></table></div>
"""


def test_parser_pue_google():
    df = ambil_pue_google.parse_html(HTML_CONTOH)
    assert set(df.columns) == {"kampus", "tahun", "kuartal", "pue_kuartalan", "pue_ttm"}
    hamina = df[(df.kampus == "Hamina, Finland") & (df.tahun == 2025)]
    assert hamina["kuartal"].tolist() == [1, 2]
    assert hamina.iloc[0]["pue_ttm"] == 1.1
    # Nama disamakan, placeholder dibuang, kampus baru tanpa TTM tetap masuk.
    assert "Changhua County, Taiwan" in set(df.kampus) and "Changua County, Taiwan" not in set(df.kampus)
    assert "RLF- New Campus" not in set(df.kampus)
    assert pd.isna(df[df.kampus == "Mesa, Arizona"].iloc[0]["pue_ttm"])
    # Format lama (dua baris fleet) digabung jadi satu baris "Fleet".
    fleet_2010 = df[(df.kampus == "Fleet") & (df.tahun == 2010)].iloc[0]
    assert fleet_2010["pue_kuartalan"] == 1.20 and fleet_2010["pue_ttm"] == 1.17


def test_agregasi_iklim_per_kuartal_dan_tahun():
    hari = pd.date_range("2024-01-01", "2024-12-31", freq="D")
    harian = pd.DataFrame({
        "time": hari, "suhu": 25.0, "suhu_maks": 31.0, "rh": 80.0, "titik_embun": 22.0,
        "bola_basah": [19.0] * 200 + [23.0] * 166,
    })
    hasil = ambil_iklim.agregasi(harian)
    kuartal = hasil[hasil.kuartal > 0]
    tahun = hasil[hasil.kuartal == 0].iloc[0]
    assert sorted(kuartal["kuartal"]) == [1, 2, 3, 4]
    assert tahun["jumlah_hari"] == 366
    assert tahun["hari_panas_lembap"] == 166           # hari dengan bola basah > 20 °C
    assert tahun["cdd18"] == pytest.approx(7 * 366)    # (25 - 18) tiap hari
    assert kuartal["jumlah_hari"].sum() == 366


def test_agregasi_buang_periode_tidak_lengkap():
    hari = pd.date_range("2024-01-01", "2024-04-10", freq="D")  # Q2 hanya 10 hari
    harian = pd.DataFrame({"time": hari, "suhu": 20.0, "suhu_maks": 25.0, "rh": 70.0, "titik_embun": 15.0, "bola_basah": 17.0})
    hasil = ambil_iklim.agregasi(harian)
    assert hasil["kuartal"].tolist() == [1]  # Q2 dan agregat tahunan dibuang


def test_rapikan_json_nasa_power():
    isi = {"properties": {"parameter": {
        "T2M": {"20240101": 25.0, "20240102": -999.0}, "T2M_MAX": {"20240101": 30.0, "20240102": 31.0},
        "RH2M": {"20240101": 80.0, "20240102": 81.0}, "T2MDEW": {"20240101": 21.0, "20240102": 21.5},
        "T2MWET": {"20240101": 23.0, "20240102": 23.2},
    }}}
    df = ambil_iklim.rapikan_json(isi)
    assert list(df["time"].dt.strftime("%Y-%m-%d")) == ["2024-01-01", "2024-01-02"]
    assert pd.isna(df["suhu"].iloc[1])  # -999 = nilai kosong


def test_akhir_kuartal_terakhir():
    from datetime import date
    assert ambil_iklim.akhir_kuartal_terakhir(date(2026, 11, 5)) == date(2026, 9, 30)
    assert ambil_iklim.akhir_kuartal_terakhir(date(2026, 2, 1)) == date(2025, 12, 31)


def test_validasi_data_lolos():
    pipeline.langkah_validasi()
