"""Tes lapisan database DuckDB (src/db.py) dan query tersimpan di sql/."""

import pytest

from src import db


def test_semua_query_tersimpan_jalan():
    daftar = db.query_tersimpan()
    assert len(daftar) >= 8
    with db.koneksi() as kon:
        for q in daftar:
            hasil = db.jalankan(q["sql"], kon=kon)
            assert not hasil.empty, q["file"]
            assert q["judul"] and q["judul"] != q["file"]


def test_view_estimasi_sama_dengan_rumus_python():
    from src import hitung
    from src.muat_data import muat_parameter

    p = muat_parameter()
    baris = db.jalankan("SELECT kapasitas_it_mw, listrik_gwh_tahun, air_m3_tahun FROM v_estimasi WHERE id = 1").iloc[0]
    assert baris["listrik_gwh_tahun"] == pytest.approx(
        hitung.listrik_tahunan_gwh(baris["kapasitas_it_mw"], p["utilisasi"], p["pue"]))
    assert baris["air_m3_tahun"] == pytest.approx(
        hitung.air_tahunan_m3(baris["kapasitas_it_mw"], p["utilisasi"], p["wue"]))


def test_tabel_utama_ada():
    tabel = set(db.daftar_tabel()["tabel"])
    assert {"fasilitas", "parameter", "pue_google", "meta_situs", "iklim", "lokasi_kampus", "v_estimasi"} <= tabel
    kolom = db.skema("fasilitas")
    assert "kapasitas_it_mw" in set(kolom["column_name"])


@pytest.mark.parametrize("sql, aman", [
    ("SELECT 1", True),
    ("  select count(*) from fasilitas;", True),
    ("WITH a AS (SELECT 1) SELECT * FROM a", True),
    ("-- komentar\nSELECT 1", True),
    ("DROP TABLE fasilitas", False),
    ("SELECT 1; DROP TABLE fasilitas", False),
    ("INSERT INTO fasilitas VALUES (1)", False),
    ("", False),
    ("SELECT * FROM fasilitas WHERE nama = 'x'; SET threads=1", False),
])
def test_sql_aman(sql, aman):
    assert db.sql_aman(sql) is aman


def test_jalankan_menolak_sql_berbahaya():
    with pytest.raises(ValueError):
        db.jalankan("DELETE FROM fasilitas")


def test_join_pue_dengan_iklim_tidak_kosong():
    df = db.jalankan("""
        SELECT COUNT(*) AS n FROM pue_google g
        JOIN lokasi_kampus l ON l.kampus = g.kampus AND l.perusahaan = 'google'
        JOIN iklim i ON i.lokasi_id = l.lokasi_id AND i.tahun = g.tahun AND i.kuartal = g.kuartal
    """)
    assert df["n"].iloc[0] > 500


def test_koneksi_darurat_tanpa_file(tmp_path):
    # Kalau file DB tidak ada, database dibangun di memori dari CSV dan tetap bisa di-query.
    with db.koneksi(tmp_path / "tidak_ada.duckdb") as kon:
        n = kon.execute("SELECT COUNT(*) FROM fasilitas").fetchone()[0]
    assert n > 10
