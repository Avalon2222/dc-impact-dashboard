"""
db.py - Akses ke database DuckDB (data/dc_impact.duckdb).

Dipakai oleh app.py (tab SQL Explorer), api/ (FastAPI), dan tes.
Semua fungsi di sini hanya MEMBACA. Database dibangun ulang oleh
scripts/bangun_db.py (dijalankan pipeline), bukan dari aplikasi.

Kalau file database tidak ada (misalnya clone baru sebelum pipeline jalan),
database dibangun sementara di memori dari CSV supaya aplikasi tetap hidup.
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PATH_DB = ROOT / "data" / "dc_impact.duckdb"
DIR_SQL = ROOT / "sql"

# Hanya pernyataan pembacaan yang boleh dijalankan dari SQL Explorer / API.
_POLA_AMAN = re.compile(r"^\s*(WITH|SELECT|DESCRIBE|SHOW|EXPLAIN|PRAGMA\s+table_info|SUMMARIZE)\b", re.IGNORECASE)
_KATA_TERLARANG = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|ATTACH|COPY|EXPORT|IMPORT|INSTALL|LOAD|CALL|SET|RESET|TRUNCATE|VACUUM)\b",
    re.IGNORECASE,
)


def koneksi(path: Path | None = None) -> duckdb.DuckDBPyConnection:
    """Buka database hanya-baca. Kalau filenya belum ada, bangun di memori dari CSV."""
    path = path or PATH_DB
    if path.exists():
        return duckdb.connect(str(path), read_only=True)

    # Jalan darurat: bangun di memori. Import di sini supaya scripts/ hanya dimuat saat perlu.
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from bangun_db import bangun, muat_tabel  # type: ignore

    kon = duckdb.connect(":memory:")
    bangun(kon, muat_tabel())
    return kon


def _tanpa_komentar(sql: str) -> str:
    """Buang komentar -- ... dan /* ... */ supaya pemeriksaan keamanan melihat SQL aslinya."""
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return "\n".join(b for b in sql.splitlines() if not b.strip().startswith("--")).strip()


def sql_aman(sql: str) -> bool:
    """True kalau SQL hanya membaca data (SELECT/WITH/...) dan tidak mengandung kata berbahaya."""
    bersih = _tanpa_komentar(sql).rstrip(";").strip()
    if not bersih or ";" in bersih:
        return False  # kosong, atau lebih dari satu pernyataan
    return bool(_POLA_AMAN.match(bersih)) and not _KATA_TERLARANG.search(bersih)


def jalankan(sql: str, params: list | None = None, kon: duckdb.DuckDBPyConnection | None = None) -> pd.DataFrame:
    """Jalankan SELECT dan kembalikan DataFrame. Menolak SQL yang mengubah data."""
    if not sql_aman(sql):
        raise ValueError("Hanya pernyataan SELECT/WITH yang diizinkan.")
    tutup = kon is None
    kon = kon or koneksi()
    try:
        return kon.execute(sql, params or []).df()
    finally:
        if tutup:
            kon.close()


def daftar_tabel(kon: duckdb.DuckDBPyConnection | None = None) -> pd.DataFrame:
    """Nama tabel/view beserta jumlah kolom, untuk ditampilkan di SQL Explorer."""
    return jalankan(
        "SELECT table_name AS tabel, table_type AS jenis, COUNT(*) AS kolom "
        "FROM information_schema.columns JOIN information_schema.tables USING (table_name) "
        "GROUP BY table_name, table_type ORDER BY table_type DESC, table_name",
        kon=kon,
    )


def skema(tabel: str, kon: duckdb.DuckDBPyConnection | None = None) -> pd.DataFrame:
    """Daftar kolom + tipe data satu tabel."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tabel):
        raise ValueError("Nama tabel tidak valid.")
    return jalankan(f"DESCRIBE {tabel}", kon=kon)[["column_name", "column_type"]]


def query_tersimpan() -> list[dict]:
    """Baca sql/*.sql. Baris komentar pertama (-- Judul) jadi judul, sisanya jadi deskripsi."""
    hasil = []
    for path in sorted(DIR_SQL.glob("*.sql")):
        teks = path.read_text(encoding="utf-8")
        komentar = [b[2:].strip() for b in teks.splitlines() if b.startswith("--")]
        hasil.append({
            "file": path.name,
            "judul": komentar[0] if komentar else path.stem,
            "deskripsi": " ".join(komentar[1:]),
            "sql": teks,
        })
    return hasil
