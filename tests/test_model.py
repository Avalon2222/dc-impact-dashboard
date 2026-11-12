"""Tes model prediksi (src/model.py) dan artefak hasil pelatihan (models/, data/prediksi_lokasi.csv)."""

import pandas as pd
import pytest

from src import model


@pytest.fixture(scope="module")
def iklim_tropis():
    return pd.DataFrame([{
        "suhu_rata": 27.6, "suhu_maks_rata": 32.0, "rh_rata": 83.0, "titik_embun_rata": 24.0,
        "bola_basah_rata": 26.0, "bola_basah_p90": 27.0, "hari_panas_lembap": 92, "cdd18": 880.0, "tahun": 2025,
    }])


@pytest.fixture(scope="module")
def iklim_dingin():
    return pd.DataFrame([{
        "suhu_rata": 4.0, "suhu_maks_rata": 8.0, "rh_rata": 80.0, "titik_embun_rata": 1.0,
        "bola_basah_rata": 2.5, "bola_basah_p90": 8.0, "hari_panas_lembap": 0, "cdd18": 0.0, "tahun": 2025,
    }])


def test_fitur_pue_urutan_kolom(iklim_tropis):
    fitur = model.siapkan_fitur_pue(iklim_tropis, umur_kuartal=16, tahun=2026)
    assert list(fitur.columns) == model.FITUR_PUE
    assert fitur["tahun"].iloc[0] == 2026 and fitur["umur_kuartal"].iloc[0] == 16


def test_model_pue_ada_dan_masuk_akal(iklim_tropis, iklim_dingin):
    m = model.muat_model("pue")
    assert m is not None, "jalankan python scripts/latih_model.py"
    tropis = model.prediksi_pue(model.siapkan_fitur_pue(iklim_tropis)).iloc[0]
    dingin = model.prediksi_pue(model.siapkan_fitur_pue(iklim_dingin)).iloc[0]
    assert 1.0 < tropis < 1.4 and 1.0 < dingin < 1.4
    # Iklim panas-lembap harus butuh pendinginan lebih berat daripada iklim dingin.
    assert tropis > dingin


def test_model_wue_tidak_negatif(iklim_tropis):
    assert model.muat_model("wue") is not None
    assert model.prediksi_wue(model.siapkan_fitur_wue(iklim_tropis)).iloc[0] >= 0


def test_metrik_lengkap_dan_mengalahkan_baseline():
    metrik = model.muat_metrik()
    assert metrik is not None
    for target in ["pue", "wue"]:
        info = metrik["model"][target]
        assert "baseline_rata_rata" in info["evaluasi"]
        assert info["terpilih"] in info["evaluasi"]
        assert info["n_baris"] > 50
    pue = metrik["model"]["pue"]
    assert pue["layak"] is True
    assert pue["evaluasi"][pue["terpilih"]]["mae_cv"] < pue["evaluasi"]["baseline_rata_rata"]["mae_cv"]
    # Kalau model WUE tidak layak, pipeline harus jujur memilih baseline.
    wue = metrik["model"]["wue"]
    assert wue["layak"] or wue["terpilih"] == "baseline_rata_rata"


def test_prediksi_lokasi_indonesia():
    df = pd.read_csv(model.ROOT / "data" / "prediksi_lokasi.csv")
    assert len(df) >= 10
    assert df["pue_prediksi"].between(1.05, 1.3).all()
    assert (df["wue_prediksi"] >= 0).all()
    # Batam lebih panas-lembap daripada Bekasi, jadi PUE prediksinya tidak boleh lebih rendah.
    batam = df[df["kabupaten_kota"] == "Kota Batam"]["pue_prediksi"].mean()
    bekasi = df[df["kabupaten_kota"] == "Kab. Bekasi"]["pue_prediksi"].mean()
    assert batam >= bekasi


def test_evaluasi_oof_tersimpan():
    oof = pd.read_csv(model.ROOT / "data" / "evaluasi_pue_oof.csv")
    assert {"kampus", "pue_kuartalan", "pue_prediksi_oof"} <= set(oof.columns)
    assert oof["kampus"].nunique() >= 30


class _ModelTiruan:
    """Model buatan tanpa __len__: memastikan argumen model dipakai apa adanya."""

    def __init__(self, nilai):
        self.nilai = nilai

    def __bool__(self):
        raise AssertionError("model tidak boleh dicek dengan truthiness")

    def predict(self, x):
        return [self.nilai] * len(x)


def test_prediksi_pakai_model_dari_argumen(iklim_tropis):
    fitur_pue = model.siapkan_fitur_pue(iklim_tropis, umur_kuartal=8)
    fitur_wue = model.siapkan_fitur_wue(iklim_tropis)
    assert model.prediksi_pue(fitur_pue, _ModelTiruan(1.42)).iloc[0] == 1.42
    assert model.prediksi_wue(fitur_wue, _ModelTiruan(-0.3)).iloc[0] == 0  # dipotong di 0


def test_tanpa_artefak_model(tmp_path, monkeypatch, iklim_tropis):
    monkeypatch.setattr(model, "DIR_MODEL", tmp_path)
    assert model.muat_model("pue") is None
    assert model.muat_metrik() is None
    with pytest.raises(FileNotFoundError, match="Model PUE belum dilatih"):
        model.prediksi_pue(model.siapkan_fitur_pue(iklim_tropis, umur_kuartal=8))
    with pytest.raises(FileNotFoundError, match="Model WUE belum dilatih"):
        model.prediksi_wue(model.siapkan_fitur_wue(iklim_tropis))
