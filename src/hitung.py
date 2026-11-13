"""
hitung.py - Rumus estimasi dampak listrik & air data center.

Semua rumus di sini SEDERHANA dan TRANSPARAN. Tujuannya bukan angka yang
presisi, tapi angka yang masuk akal (order of magnitude) dan bisa diubah
asumsinya lewat slider di dashboard.

Istilah penting:
  - Kapasitas IT (MW) : daya maksimum yang bisa dipakai server.
  - Utilisasi         : seberapa penuh kapasitas itu terpakai (0-1).
  - PUE               : Power Usage Effectiveness = listrik total / listrik server.
                        PUE 1.5 -> tiap 1 kWh ke server, fasilitas total pakai 1.5 kWh.
  - WUE               : Water Usage Effectiveness = liter air per kWh listrik server.
"""

from __future__ import annotations

import pandas as pd

JAM_PER_TAHUN = 8760  # 365 hari x 24 jam
HARI_PER_TAHUN = 365


def listrik_tahunan_gwh(kapasitas_it_mw: float, utilisasi: float, pue: float) -> float:
    """Estimasi konsumsi listrik total fasilitas per tahun, dalam GWh.

    Rumus:
        MW x utilisasi            -> daya server rata-rata (MW)
        x PUE                     -> daya total fasilitas (MW)
        x 8760 jam                -> energi per tahun (MWh)
        / 1000                    -> GWh

    Contoh: 10 MW, utilisasi 0.6, PUE 1.5
        10 x 0.6 x 1.5 x 8760 / 1000 = 78.84 GWh/tahun
    """
    return kapasitas_it_mw * utilisasi * pue * JAM_PER_TAHUN / 1000


def air_tahunan_m3(kapasitas_it_mw: float, utilisasi: float, wue_liter_per_kwh: float) -> float:
    """Estimasi pemakaian air pendingin per tahun, dalam meter kubik (m3).

    WUE didefinisikan per kWh LISTRIK SERVER (bukan listrik total), jadi
    di sini PUE tidak ikut dikalikan.

    Rumus:
        MW x utilisasi x 8760     -> energi server per tahun (MWh)
        x 1000                    -> kWh
        x WUE                     -> liter
        / 1000                    -> m3  (1 m3 = 1000 liter)

    Contoh: 10 MW, utilisasi 0.6, WUE 1.8
        10 x 0.6 x 8760 x 1000 x 1.8 / 1000 = 94608 m3/tahun (sekitar 94,6 ribu m3)
    """
    kwh_server = kapasitas_it_mw * utilisasi * JAM_PER_TAHUN * 1000
    return kwh_server * wue_liter_per_kwh / 1000


def setara_penduduk_listrik(listrik_gwh: float, kwh_per_kapita_tahun: float) -> float:
    """Berapa orang Indonesia yang konsumsi listrik setahunnya setara angka ini?

    1 GWh = 1.000.000 kWh.
    """
    return listrik_gwh * 1_000_000 / kwh_per_kapita_tahun


def setara_penduduk_air(air_m3_tahun: float, liter_per_orang_hari: float) -> float:
    """Berapa orang yang kebutuhan air setahunnya setara angka ini?"""
    liter_per_orang_tahun = liter_per_orang_hari * HARI_PER_TAHUN
    return air_m3_tahun * 1000 / liter_per_orang_tahun


def tambah_kolom_estimasi(
    df: pd.DataFrame,
    utilisasi: float,
    pue: float,
    wue: float,
    kwh_per_kapita_tahun: float,
    liter_per_orang_hari: float,
    orang_per_rumah_tangga: float = 4,
) -> pd.DataFrame:
    """Tambahkan kolom-kolom estimasi ke DataFrame data center.

    Kolom baru:
      listrik_gwh_tahun, air_m3_tahun, air_liter_hari,
      setara_orang_listrik, setara_orang_air,
      setara_rumah_tangga_listrik, setara_rumah_tangga_air
    """
    hasil = df.copy()
    mw = hasil["kapasitas_it_mw"]

    hasil["listrik_gwh_tahun"] = listrik_tahunan_gwh(mw, utilisasi, pue)
    hasil["air_m3_tahun"] = air_tahunan_m3(mw, utilisasi, wue)
    hasil["air_liter_hari"] = hasil["air_m3_tahun"] * 1000 / HARI_PER_TAHUN

    hasil["setara_orang_listrik"] = setara_penduduk_listrik(
        hasil["listrik_gwh_tahun"], kwh_per_kapita_tahun
    )
    hasil["setara_orang_air"] = setara_penduduk_air(hasil["air_m3_tahun"], liter_per_orang_hari)

    hasil["setara_rumah_tangga_listrik"] = hasil["setara_orang_listrik"] / orang_per_rumah_tangga
    hasil["setara_rumah_tangga_air"] = hasil["setara_orang_air"] / orang_per_rumah_tangga

    return hasil


def format_angka(x: float, desimal: int = 0) -> str:
    """Format angka gaya Indonesia: titik ribuan, koma desimal. 1234567.8 -> '1.234.568'."""
    if pd.isna(x):
        return "-"
    teks = f"{x:,.{desimal}f}"  # gaya Inggris: 1,234,567.8
    return teks.replace(",", "X").replace(".", ",").replace("X", ".")


def format_ringkas(x: float) -> str:
    """Angka besar jadi ringkas: 1.500.000 -> '1,5 juta', 12.300 -> '12,3 ribu'.
    Di bawah 10.000 ditulis utuh (2.300 tetap '2.300')."""
    if pd.isna(x):
        return "-"
    # Cek dari satuan terbesar. Pakai nilai SETELAH dibulatkan, supaya
    # 999.960 jadi "1,0 juta" dan bukan "1.000,0 ribu".
    for batas, akhiran in ((1_000_000_000, " miliar"), (1_000_000, " juta"), (1_000, " ribu")):
        if abs(round(x / batas, 1)) >= 1 and (batas > 1_000 or abs(round(x)) >= 10_000):
            return format_angka(x / batas, 1) + akhiran
    return format_angka(x, 0)
