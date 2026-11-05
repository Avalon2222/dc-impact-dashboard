"""
ambil_pue_google.py - Mengunduh PUE kuartalan per kampus dari halaman efisiensi Google.

Google mempublikasikan PUE (Power Usage Effectiveness) tiap kuartal untuk
setiap kampus data center besarnya sejak 2008 di
https://www.google.com/about/datacenters/efficiency/.
Skrip ini membaca halaman itu, mengambil tabel per kuartal, dan menyimpannya
ke data/pue_google_kuartalan.csv dengan kolom:

    kampus, tahun, kuartal, pue_kuartalan, pue_ttm

pue_ttm = trailing twelve month (rata-rata 12 bulan terakhir), bisa kosong
untuk kampus yang belum setahun beroperasi.

Jalankan:  python scripts/ambil_pue_google.py
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd
import requests

URL = "https://www.google.com/about/datacenters/efficiency/"
ROOT = Path(__file__).resolve().parent.parent
KELUARAN = ROOT / "data" / "pue_google_kuartalan.csv"


class _PembacaTabel(HTMLParser):
    """Parser HTML sederhana: mengumpulkan judul laporan, nama kuartal, dan baris tabel."""

    def __init__(self) -> None:
        super().__init__()
        self.baris: list[tuple[int, int, str, list[str]]] = []
        self._tahun: int | None = None
        self._kuartal: int | None = None
        self._di_sel = False
        self._sel_sekarang: list[str] = []
        self._baris_sekarang: list[str] = []
        self._di_h2 = False
        self._teks_h2 = ""
        self._di_tab = False
        self._teks_tab = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "h2":
            self._di_h2, self._teks_h2 = True, ""
        if tag == "div" and a.get("data-cy") == "tabItem":
            self._di_tab, self._teks_tab = True, ""
        if tag == "tr":
            self._baris_sekarang = []
        if tag == "td":
            self._di_sel, self._sel_sekarang = True, []

    def handle_endtag(self, tag):
        if tag == "h2" and self._di_h2:
            self._di_h2 = False
            m = re.search(r"(\d{4}) PUE Yearly Report", self._teks_h2)
            if m:
                self._tahun = int(m.group(1))
        if tag == "td" and self._di_sel:
            self._di_sel = False
            self._baris_sekarang.append(" ".join("".join(self._sel_sekarang).split()))
        if tag == "tr" and self._baris_sekarang and self._tahun and self._kuartal:
            self.baris.append((self._tahun, self._kuartal, self._baris_sekarang[0], self._baris_sekarang[1:]))

    def handle_data(self, data):
        if self._di_h2:
            self._teks_h2 += data
        if self._di_sel:
            self._sel_sekarang.append(data)
        # Judul tab "Quarter 01" muncul sebagai teks biasa sebelum tabelnya.
        m = re.search(r"Quarter 0?(\d)", data)
        if m:
            self._kuartal = int(m.group(1))


# Google beberapa kali mengganti nama kampus atau salah ketik; samakan supaya satu kampus = satu nama.
NAMA_SERAGAM = {
    "Changua County, Taiwan": "Changhua County, Taiwan",
    "Lowcountry, South Carolina": "Berkeley County, South Carolina",
    "New Albany, Ohio": "Central Ohio (New Albany), Ohio",
}
# Baris yang bukan kampus sungguhan (placeholder di halaman Google).
NAMA_DIBUANG = {"RLF- New Campus"}
FLEET_KUARTALAN = "Fleet-wide quarterly PUE:"
FLEET_TTM = "Fleet-wide trailing twelve-month (TTM) PUE:"


def _ke_angka(teks: str) -> float | None:
    try:
        return float(teks)
    except ValueError:
        return None


def parse_html(html: str) -> pd.DataFrame:
    """Ubah HTML halaman efisiensi Google menjadi tabel rapi."""
    p = _PembacaTabel()
    p.feed(html)
    rekaman = []
    for tahun, kuartal, nama, angka in p.baris:
        nilai = [_ke_angka(x) for x in angka]
        nilai = [v for v in nilai if v is not None]
        if not nilai or not nama:
            continue
        rekaman.append({
            "kampus": nama,
            "tahun": tahun,
            "kuartal": kuartal,
            "pue_kuartalan": nilai[0],
            "pue_ttm": nilai[1] if len(nilai) > 1 else None,
        })
    df = pd.DataFrame(rekaman)
    if df.empty:
        return df
    df = df.drop_duplicates(subset=["kampus", "tahun", "kuartal"], keep="first")
    df = df[(df["pue_kuartalan"] > 1.0) & (df["pue_kuartalan"] < 2.0)]
    df = df[~df["kampus"].isin(NAMA_DIBUANG)]
    df["kampus"] = df["kampus"].replace(NAMA_SERAGAM)

    # Laporan 2008-2016 menulis angka fleet sebagai dua baris terpisah (kuartalan & TTM).
    # Gabungkan jadi satu baris "Fleet" seperti format laporan yang lebih baru.
    lama_q = df[df["kampus"] == FLEET_KUARTALAN].set_index(["tahun", "kuartal"])["pue_kuartalan"]
    lama_ttm = df[df["kampus"] == FLEET_TTM].set_index(["tahun", "kuartal"])["pue_kuartalan"]
    if not lama_q.empty or not lama_ttm.empty:
        gabung = pd.concat([lama_q.rename("pue_kuartalan"), lama_ttm.rename("pue_ttm")], axis=1).reset_index()
        gabung["kampus"] = "Fleet"
        df = pd.concat([df[~df["kampus"].isin([FLEET_KUARTALAN, FLEET_TTM])], gabung], ignore_index=True)

    df = df.drop_duplicates(subset=["kampus", "tahun", "kuartal"], keep="first")
    df["tahun"] = df["tahun"].astype(int)
    df["kuartal"] = df["kuartal"].astype(int)
    kolom = ["kampus", "tahun", "kuartal", "pue_kuartalan", "pue_ttm"]
    return df[kolom].sort_values(["tahun", "kuartal", "kampus"]).reset_index(drop=True)


def unduh(url: str = URL) -> str:
    r = requests.get(url, timeout=60, headers={"User-Agent": "dc-impact-dashboard/1.0 (data pipeline)"})
    r.raise_for_status()
    return r.text


def main() -> int:
    df = parse_html(unduh())
    if len(df) < 500:
        print(f"Hanya dapat {len(df)} baris; struktur halaman mungkin berubah. File lama dipertahankan.")
        return 1
    df.to_csv(KELUARAN, index=False)
    n_kampus = df.loc[df["kampus"] != "Fleet", "kampus"].nunique()
    print(f"Tersimpan {len(df)} baris, {n_kampus} kampus, {df['tahun'].min()}-{df['tahun'].max()} -> {KELUARAN.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
