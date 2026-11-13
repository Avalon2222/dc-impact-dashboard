"""
Tes kecil untuk rumus di src/hitung.py.

Jalankan dengan:  python -m pytest tests/ -v
Kalau semua hijau (PASSED), rumusnya masih benar.
"""

import pandas as pd
import pytest

from src import hitung
from src.muat_data import muat_data_center, muat_parameter


def test_listrik_contoh_di_docstring():
    # 10 MW, utilisasi 0.6, PUE 1.5 -> 78.84 GWh (lihat docstring fungsinya)
    assert hitung.listrik_tahunan_gwh(10, 0.6, 1.5) == pytest.approx(78.84)


def test_air_contoh_di_docstring():
    # 10 MW, utilisasi 0.6, WUE 1.8 -> 94.608 m3
    assert hitung.air_tahunan_m3(10, 0.6, 1.8) == pytest.approx(94_608)


def test_pue_lebih_tinggi_listrik_lebih_banyak():
    assert hitung.listrik_tahunan_gwh(10, 0.6, 1.8) > hitung.listrik_tahunan_gwh(10, 0.6, 1.2)


def test_wue_nol_berarti_tanpa_air():
    assert hitung.air_tahunan_m3(100, 1.0, 0.0) == 0


def test_setara_penduduk_listrik():
    # 1 GWh = 1 juta kWh; kalau per orang 1000 kWh/tahun -> 1000 orang
    assert hitung.setara_penduduk_listrik(1, 1000) == pytest.approx(1000)


def test_setara_penduduk_air():
    # 365 m3 = 365.000 liter; 100 L/orang/hari x 365 hari = 36.500 L/orang/tahun -> 10 orang
    assert hitung.setara_penduduk_air(365, 100) == pytest.approx(10)


def test_format_angka_gaya_indonesia():
    assert hitung.format_angka(1234567.891, 1) == "1.234.567,9"
    assert hitung.format_ringkas(1_500_000) == "1,5 juta"


def test_dataset_bisa_dimuat_dan_valid():
    df = muat_data_center()
    assert len(df) > 10
    # Tidak ada koordinat yang kosong & semuanya di sekitar Indonesia
    assert df["lat"].between(-11, 6).all()
    assert df["lon"].between(95, 141).all()
    assert df["kapasitas_it_mw"].gt(0).all()
    assert set(df["status"].unique()) <= {"beroperasi", "dibangun", "rencana"}


def test_tambah_kolom_estimasi():
    df = muat_data_center()
    p = muat_parameter()
    hasil = hitung.tambah_kolom_estimasi(
        df, p["utilisasi"], p["pue"], p["wue"],
        p["listrik_per_kapita_kwh_tahun"], p["air_per_orang_liter_hari"],
    )
    for kolom in ["listrik_gwh_tahun", "air_m3_tahun", "setara_orang_listrik", "setara_orang_air"]:
        assert kolom in hasil.columns
        assert (hasil[kolom] >= 0).all()


def test_format_ringkas_semua_tingkat():
    assert hitung.format_ringkas(2_300_000_000) == "2,3 miliar"
    assert hitung.format_ringkas(12_500) == "12,5 ribu"
    assert hitung.format_ringkas(999) == "999"


def test_format_ringkas_naik_satuan_setelah_dibulatkan():
    assert hitung.format_ringkas(999_960) == "1,0 juta"          # bukan "1.000,0 ribu"
    assert hitung.format_ringkas(999_999_999) == "1,0 miliar"    # bukan "1.000,0 juta"
    assert hitung.format_ringkas(-2_500_000) == "-2,5 juta"


def test_format_nan_jadi_strip():
    assert hitung.format_angka(float("nan")) == "-"
    assert hitung.format_ringkas(float("nan")) == "-"


def test_rumah_tangga_turunan_dari_orang():
    df = pd.DataFrame({"kapasitas_it_mw": [10.0, 50.0]})
    hasil = hitung.tambah_kolom_estimasi(
        df, utilisasi=0.6, pue=1.5, wue=1.8,
        kwh_per_kapita_tahun=1200, liter_per_orang_hari=120, orang_per_rumah_tangga=4,
    )
    assert hasil["setara_rumah_tangga_listrik"].tolist() == pytest.approx(
        (hasil["setara_orang_listrik"] / 4).tolist()
    )
    assert hasil["air_liter_hari"].iloc[0] == pytest.approx(hasil["air_m3_tahun"].iloc[0] * 1000 / 365)
    # Data center 5x lebih besar -> estimasi juga 5x (rumusnya linear)
    assert hasil["listrik_gwh_tahun"].iloc[1] == pytest.approx(5 * hasil["listrik_gwh_tahun"].iloc[0])


def test_parameter_lengkap_sejalan_dengan_parameter():
    from src.muat_data import muat_parameter_lengkap

    lengkap = muat_parameter_lengkap()
    assert not lengkap.isna().any().any()                      # NaN sudah diganti string kosong
    assert set(lengkap["parameter"]) == set(muat_parameter())  # tabel tampilan = tabel hitung
    assert (lengkap["satuan"] != "").all()
    url = lengkap.loc[lengkap["url_sumber"] != "", "url_sumber"]
    assert url.str.startswith("http").all()


def test_status_dan_keyakinan_tidak_hilang_jadi_nan():
    # Kolom kategori: nilai di luar daftar urutan diam-diam berubah jadi NaN, jadi dicek di sini.
    df = muat_data_center()
    assert df["status"].notna().all()
    assert df["keyakinan"].notna().all()


def test_contoh_di_docstring_tetap_benar():
    # Angka contoh di docstring dipakai di dokumentasi BELAJAR.md, jadi harus sesuai rumus.
    assert hitung.listrik_tahunan_gwh(10, 0.6, 1.5) == pytest.approx(78.84)
    assert hitung.air_tahunan_m3(10, 0.6, 1.8) == pytest.approx(94_608)
