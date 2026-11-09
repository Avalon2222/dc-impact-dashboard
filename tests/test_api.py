"""Tes API FastAPI (api/main.py) memakai TestClient, tanpa menjalankan server."""

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def klien():
    return TestClient(app)


def test_beranda(klien):
    r = klien.get("/")
    assert r.status_code == 200
    assert "/fasilitas" in r.json()["endpoint"]


def test_daftar_fasilitas_dengan_filter(klien):
    semua = klien.get("/fasilitas").json()
    beroperasi = klien.get("/fasilitas", params={"status": "beroperasi", "min_mw": 20}).json()
    assert semua["jumlah"] > beroperasi["jumlah"] > 0
    assert all(f["status"] == "beroperasi" and f["kapasitas_it_mw"] >= 20 for f in beroperasi["fasilitas"])


def test_satu_fasilitas_dan_404(klien):
    assert klien.get("/fasilitas/1").json()["id"] == 1
    assert klien.get("/fasilitas/99999").status_code == 404


def test_estimasi_sama_dengan_docstring_hitung(klien):
    r = klien.get("/estimasi", params={"kapasitas_it_mw": 10, "utilisasi": 0.6, "pue": 1.5, "wue": 1.8}).json()
    assert r["listrik_gwh_tahun"] == pytest.approx(78.84)
    assert r["air_m3_tahun"] == pytest.approx(94_608)


def test_estimasi_validasi_input(klien):
    assert klien.get("/estimasi", params={"kapasitas_it_mw": -5}).status_code == 422
    assert klien.get("/estimasi", params={"kapasitas_it_mw": 5, "utilisasi": 1.5}).status_code == 422


def test_ringkasan_total_konsisten(klien):
    r = klien.get("/ringkasan", params={"pue": 1.2}).json()
    assert r["asumsi"]["pue"] == 1.2
    assert r["total"]["kapasitas_it_mw"] == pytest.approx(sum(p["kapasitas_it_mw"] for p in r["per_provinsi"]))


def test_prediksi_pue_dan_wue(klien):
    iklim = {"suhu_rata": 27.6, "suhu_maks_rata": 32, "rh_rata": 83, "titik_embun_rata": 24,
             "bola_basah_rata": 26, "bola_basah_p90": 27, "hari_panas_lembap": 92, "cdd18": 880}
    pue = klien.post("/prediksi/pue", json={"iklim": iklim}).json()
    assert 1.0 < pue["pue_prediksi"] < 1.4
    wue = klien.post("/prediksi/wue", json={"iklim": iklim, "tahun": 2026}).json()
    assert wue["wue_prediksi"] >= 0 and "layak" in wue
    assert klien.post("/prediksi/pue", json={"iklim": {**iklim, "rh_rata": 150}}).status_code == 422


def test_prediksi_lokasi(klien):
    r = klien.get("/prediksi/lokasi").json()
    assert r["jumlah"] >= 10 and "pue_prediksi" in r["lokasi"][0]


def test_sql_tersimpan_dan_sql_bebas(klien):
    assert len(klien.get("/sql/tersimpan").json()) >= 8
    r = klien.post("/sql", json={"sql": "SELECT COUNT(*) AS n FROM fasilitas"}).json()
    assert r["baris"][0]["n"] > 10


def test_sql_menolak_perubahan_data(klien):
    assert klien.post("/sql", json={"sql": "DROP TABLE fasilitas"}).status_code == 400
    assert klien.post("/sql", json={"sql": "SELECT * FROM tabel_tidak_ada"}).status_code == 400


def test_metrik_model_ada_dan_503_kalau_belum_dilatih(klien, monkeypatch):
    import api.main as api_main

    r = klien.get("/model/metrik")
    assert r.status_code == 200 and "model" in r.json()
    monkeypatch.setattr(api_main, "muat_metrik", lambda: None)
    assert klien.get("/model/metrik").status_code == 503


def test_rapikan_nan_jadi_null():
    import numpy as np
    import pandas as pd

    from api.main import _rapikan

    df = pd.DataFrame({"nama": ["A", None], "mw": [1.5, np.nan]})
    assert _rapikan(df) == [{"nama": "A", "mw": 1.5}, {"nama": None, "mw": None}]
