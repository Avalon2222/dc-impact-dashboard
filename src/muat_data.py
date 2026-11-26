"""
muat_data.py - Fungsi untuk membaca file CSV di folder data/.

Kenapa dipisah dari app.py?
  Supaya logika "baca data" bisa dites sendiri (lihat tests/), dan app.py
  tetap fokus ke tampilan. Ini kebiasaan bagus: pisahkan DATA, LOGIKA, TAMPILAN.
"""

from pathlib import Path

import numpy as np
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
    # Kolom teks dibaca sebagai string. Kalau satu kolom kosong semua, pandas menebaknya float
    # dan fillna("") di bawah jadi bercampur tipe.
    df = pd.read_csv(path, dtype={"catatan": str, "url_sumber": str, "sumber": str})

    # Pastikan kolom angka memang bertipe angka (kalau ada yang kosong jadi NaN).
    for kolom in ["lat", "lon", "kapasitas_it_mw", "tahun"]:
        df[kolom] = pd.to_numeric(df[kolom], errors="coerce")
    # Kapasitas negatif (salah ketik tanda minus) akan menghasilkan listrik dan air negatif
    # yang diam-diam mengurangi total nasional.
    negatif = df.loc[df["kapasitas_it_mw"] < 0, "nama"].tolist()
    if negatif:
        raise ValueError(f"kapasitas_it_mw negatif di {Path(path).name}: {negatif}")
    # "inf" lolos to_numeric dan membuat total listrik/air nasional ikut tak hingga.
    tak_hingga = df.loc[np.isinf(df["kapasitas_it_mw"]), "nama"].tolist()
    if tak_hingga:
        raise ValueError(f"kapasitas_it_mw tak hingga di {Path(path).name}: {tak_hingga}")
    # Tahun "inf" juga lolos to_numeric dan membuat grafik pertumbuhan kapasitas punya titik di tak hingga.
    tahun_rusak = df.loc[np.isinf(df["tahun"]), "nama"].tolist()
    if tahun_rusak:
        raise ValueError(f"tahun tak hingga di {Path(path).name}: {tahun_rusak}")

    # Lat/lon tertukar (106, -6) atau salah ketik membuat titik muncul di luar bumi atau di Antartika.
    di_luar = df.loc[(df["lat"].abs() > 90) | (df["lon"].abs() > 180), "nama"].tolist()
    if di_luar:
        raise ValueError(f"Koordinat di luar rentang (lat ±90, lon ±180) di {Path(path).name}: {di_luar}")

    # Rapikan huruf besar dan spasi dulu ("Beroperasi " -> "beroperasi"), lalu tolak nilai asing.
    # Tanpa ini, nilai di luar daftar urutan diam-diam berubah jadi NaN di Categorical.
    for kolom, pilihan in (("status", URUTAN_STATUS), ("keyakinan", URUTAN_KEYAKINAN)):
        df[kolom] = df[kolom].astype("string").str.strip().str.lower()
        # Sel berisi spasi saja sama dengan sel kosong, bukan nilai asing bernama ''.
        df[kolom] = df[kolom].mask(df[kolom] == "")
        asing = sorted(set(df[kolom].dropna()) - set(pilihan))
        if asing:
            raise ValueError(f"Nilai '{kolom}' tidak dikenal di {Path(path).name}: {asing}. Pilihan: {pilihan}")

    # Kolom kategori diberi urutan supaya legenda grafik konsisten.
    df["status"] = pd.Categorical(df["status"], categories=URUTAN_STATUS, ordered=True)
    df["keyakinan"] = pd.Categorical(df["keyakinan"], categories=URUTAN_KEYAKINAN, ordered=True)

    # Kolom teks yang kosong (NaN) diganti string kosong supaya tooltip rapi.
    for kolom in ["catatan", "url_sumber", "sumber"]:
        df[kolom] = df[kolom].fillna("")

    return df


def _nilai_angka(kolom: pd.Series) -> pd.Series:
    """Kolom nilai parameter -> float. "1,5" (koma desimal) diterima, teks lain jadi NaN."""
    teks = kolom.astype(str).str.strip().str.replace(",", ".", regex=False)
    return pd.to_numeric(teks, errors="coerce").astype(float)


def muat_parameter(path: Path | None = None) -> dict:
    """Baca parameter asumsi (PUE, WUE, dll) menjadi dict {nama: nilai}.

    Contoh hasil: {"pue": 1.5, "wue": 1.8, ...}
    """
    path = path or DATA_DIR / "parameter_asumsi.csv"
    df = pd.read_csv(path)
    # Spasi sisa edit manual ("pue ") atau huruf besar ("PUE") membuat PARAM["pue"] KeyError
    # dan lolos dari cek dobel.
    df["parameter"] = df["parameter"].fillna("").astype(str).str.strip().str.lower()
    df = df[df["parameter"] != ""]   # baris kosong di akhir CSV bukan parameter "nan"
    # Nilai harus angka; "1,5" (koma desimal) diterima, sel kosong atau teks ditolak dengan nama parameternya.
    nilai = _nilai_angka(df["nilai"])
    # "inf" lolos to_numeric, padahal asumsi tak hingga membuat semua estimasi ikut tak hingga.
    rusak = df.loc[~np.isfinite(nilai), "parameter"].tolist()
    if rusak:
        raise ValueError(f"Nilai parameter kosong atau bukan angka di {Path(path).name}: {rusak}")
    df = df.assign(nilai=nilai)
    dobel = sorted(df.loc[df["parameter"].duplicated(), "parameter"].unique())
    if dobel:
        # dict() diam-diam memakai baris terakhir, jadi parameter dobel lebih baik ditolak.
        raise ValueError(f"Parameter dobel di {Path(path).name}: {dobel}")
    return dict(zip(df["parameter"], df["nilai"]))


def muat_parameter_lengkap(path: Path | None = None) -> pd.DataFrame:
    """Versi lengkap tabel parameter (dengan sumber dan catatan) untuk ditampilkan."""
    path = path or DATA_DIR / "parameter_asumsi.csv"
    df = pd.read_csv(path)
    # Nama dirapikan dan baris kosong dibuang dengan aturan yang sama seperti muat_parameter,
    # supaya tabel yang ditampilkan selalu sama dengan tabel yang dipakai menghitung.
    df["parameter"] = df["parameter"].fillna("").astype(str).str.strip().str.lower()
    df = df[df["parameter"] != ""].reset_index(drop=True)
    # Nilai "1,5" dipakai sebagai 1.5 oleh muat_parameter, jadi tabel tampilan memakai angka yang sama.
    df["nilai"] = _nilai_angka(df["nilai"])
    teks = [k for k in df.columns if k != "nilai"]
    df[teks] = df[teks].fillna("")
    return df
