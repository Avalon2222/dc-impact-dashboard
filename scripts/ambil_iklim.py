"""
ambil_iklim.py - Mengambil data iklim historis dari NASA POWER untuk setiap lokasi.

Mengapa iklim? Pendingin data center bekerja lebih berat kalau udara luar panas
dan lembap. Variabel kuncinya adalah suhu bola basah (wet-bulb): makin tinggi,
makin sedikit "pendinginan gratis" dari udara luar, dan makin banyak air yang
menguap di menara pendingin. Model di scripts/latih_model.py memakai angka-angka
ini sebagai fitur.

Sumber: NASA POWER Daily API (reanalisis MERRA-2, gratis, tanpa kunci, resolusi ~0,5°).
https://power.larc.nasa.gov/docs/services/api/temporal/daily/

Lokasi yang diambil:
  1. Kampus Google dan situs Meta di data/lokasi_kampus.csv (data latih).
  2. Lokasi data center Indonesia di data/data_center_indonesia.csv (data prediksi).

Keluaran: data/iklim_kuartalan.csv, satu baris = satu lokasi x tahun x kuartal.
Baris dengan kuartal = 0 adalah agregat setahun penuh.

Jalankan:  python scripts/ambil_iklim.py
"""

from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
KELUARAN = DATA / "iklim_kuartalan.csv"
URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
TAHUN_MULAI = 2016  # laporan PUE per kampus Google dimulai Q2 2016
# Nama parameter NASA POWER -> nama kolom kita.
VARIABEL = {
    "T2M": "suhu",            # suhu udara rata-rata harian 2 m (°C)
    "T2M_MAX": "suhu_maks",   # suhu maksimum harian (°C)
    "RH2M": "rh",             # kelembapan relatif (%)
    "T2MDEW": "titik_embun",  # titik embun (°C)
    "T2MWET": "bola_basah",   # suhu bola basah (°C)
}
NILAI_KOSONG = -999.0
AMBANG_BOLA_BASAH = 20.0  # °C; di atas ini pendingin evaporatif mulai kehilangan daya
SUHU_DASAR_CDD = 18.0  # °C; dasar cooling degree days


def kunci_lokasi(lat: float, lon: float) -> str:
    """Satu lokasi = satu string 'lat,lon' dua desimal, supaya kampus yang sama tidak diambil dua kali."""
    return f"{lat:.2f},{lon:.2f}"


def daftar_lokasi() -> pd.DataFrame:
    """Gabungkan semua titik yang perlu diambil iklimnya (tanpa duplikat koordinat)."""
    kampus = pd.read_csv(DATA / "lokasi_kampus.csv")[["lat", "lon"]]
    indo = pd.read_csv(DATA / "data_center_indonesia.csv")[["lat", "lon"]]
    semua = pd.concat([kampus, indo], ignore_index=True).dropna()
    semua["lokasi_id"] = [kunci_lokasi(a, b) for a, b in zip(semua["lat"], semua["lon"])]
    return semua.drop_duplicates("lokasi_id").reset_index(drop=True)


def akhir_kuartal_terakhir(hari_ini: date | None = None) -> date:
    """Tanggal terakhir dari kuartal penuh yang sudah lewat (data ERA5 tertinggal beberapa hari)."""
    hari_ini = hari_ini or date.today()
    kuartal_sekarang = (hari_ini.month - 1) // 3  # 0..3
    if kuartal_sekarang == 0:
        return date(hari_ini.year - 1, 12, 31)
    bulan_akhir = kuartal_sekarang * 3
    hari_akhir = {3: 31, 6: 30, 9: 30}[bulan_akhir]
    return date(hari_ini.year, bulan_akhir, hari_akhir)


def unduh_harian(lat: float, lon: float, mulai: date, selesai: date, sesi: requests.Session | None = None) -> pd.DataFrame:
    """Ambil data harian satu titik dari NASA POWER dan kembalikan DataFrame."""
    sesi = sesi or requests.Session()
    r = sesi.get(URL, params={
        "parameters": ",".join(VARIABEL), "community": "RE",
        "latitude": lat, "longitude": lon,
        "start": mulai.strftime("%Y%m%d"), "end": selesai.strftime("%Y%m%d"),
        "format": "JSON",
    }, timeout=180)
    r.raise_for_status()
    return rapikan_json(r.json())


def rapikan_json(isi: dict) -> pd.DataFrame:
    """Ubah JSON NASA POWER ({parameter: {tanggal: nilai}}) menjadi tabel harian."""
    parameter = isi["properties"]["parameter"]
    harian = pd.DataFrame({kolom: pd.Series(parameter[nama]) for nama, kolom in VARIABEL.items()})
    harian.index.name = "time"
    harian = harian.reset_index()
    harian["time"] = pd.to_datetime(harian["time"], format="%Y%m%d")
    harian = harian.astype({k: "float64" for k in VARIABEL.values()})
    return harian.replace(NILAI_KOSONG, float("nan"))


def agregasi(harian: pd.DataFrame) -> pd.DataFrame:
    """Ringkas data harian jadi per kuartal (1-4) dan per tahun (kuartal = 0)."""
    h = harian.dropna().copy()
    h["tahun"] = h["time"].dt.year
    h["kuartal"] = h["time"].dt.quarter
    h["panas_lembap"] = (h["bola_basah"] > AMBANG_BOLA_BASAH).astype(int)
    h["cdd"] = (h["suhu"] - SUHU_DASAR_CDD).clip(lower=0)

    def ringkas(grup: pd.DataFrame) -> pd.Series:
        return pd.Series({
            "suhu_rata": grup["suhu"].mean(),
            "suhu_maks_rata": grup["suhu_maks"].mean(),
            "rh_rata": grup["rh"].mean(),
            "titik_embun_rata": grup["titik_embun"].mean(),
            "bola_basah_rata": grup["bola_basah"].mean(),
            "bola_basah_p90": grup["bola_basah"].quantile(0.9),
            "hari_panas_lembap": grup["panas_lembap"].sum(),
            "cdd18": grup["cdd"].sum(),
            "jumlah_hari": len(grup),
        })

    per_kuartal = h.groupby(["tahun", "kuartal"]).apply(ringkas, include_groups=False).reset_index()
    per_tahun = h.groupby("tahun").apply(ringkas, include_groups=False).reset_index()
    per_tahun["kuartal"] = 0
    # Hanya simpan periode yang lengkap (kuartal >= 85 hari, tahun >= 360 hari).
    per_kuartal = per_kuartal[per_kuartal["jumlah_hari"] >= 85]
    per_tahun = per_tahun[per_tahun["jumlah_hari"] >= 360]
    return pd.concat([per_kuartal, per_tahun], ignore_index=True)


def main() -> int:
    lokasi = daftar_lokasi()
    mulai, selesai = date(TAHUN_MULAI, 1, 1), akhir_kuartal_terakhir()
    print(f"Mengambil iklim {len(lokasi)} lokasi, {mulai} s/d {selesai} ...")
    sesi = requests.Session()
    potongan = []
    for i, baris in lokasi.iterrows():
        for percobaan in range(3):
            try:
                harian = unduh_harian(baris["lat"], baris["lon"], mulai, selesai, sesi)
                break
            except requests.RequestException as e:
                if percobaan == 2:
                    raise
                print(f"  gagal ({e}); coba lagi ...")
                time.sleep(5 * (percobaan + 1))
        ringkas = agregasi(harian)
        ringkas.insert(0, "lokasi_id", baris["lokasi_id"])
        ringkas.insert(1, "lat", baris["lat"])
        ringkas.insert(2, "lon", baris["lon"])
        potongan.append(ringkas)
        print(f"  [{i + 1}/{len(lokasi)}] {baris['lokasi_id']}: {len(ringkas)} baris")
        time.sleep(0.3)  # sopan ke server gratis
    hasil = pd.concat(potongan, ignore_index=True)
    hasil = hasil.round(3).sort_values(["lokasi_id", "tahun", "kuartal"])
    hasil.to_csv(KELUARAN, index=False)
    print(f"Tersimpan {len(hasil)} baris -> {KELUARAN.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
