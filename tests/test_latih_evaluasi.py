"""Tes cara evaluasi dan gerbang kelayakan model (scripts/latih_model.py)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import latih_model  # noqa: E402
from sklearn.dummy import DummyRegressor  # noqa: E402
from sklearn.linear_model import LinearRegression  # noqa: E402


@pytest.fixture
def data_linear():
    acak = np.random.default_rng(0)
    n = 120
    df = pd.DataFrame({
        "x": acak.uniform(0, 10, n),
        "grup": np.repeat([f"k{i}" for i in range(6)], n // 6),
        "tahun": np.tile(np.arange(2016, 2026), n // 10),
    })
    df["y"] = 1.1 + 0.02 * df["x"] + acak.normal(0, 0.001, n)
    return df


def test_kandidat_selalu_punya_baseline():
    k = latih_model.kandidat()
    assert "baseline_rata_rata" in k
    assert len(k) >= 3


def test_evaluasi_cv_prediksi_out_of_fold_lengkap(data_linear):
    metrik, pred = latih_model.evaluasi_cv(
        LinearRegression(), data_linear[["x"]], data_linear["y"], data_linear["grup"], n_fold=3
    )
    # Setiap baris diprediksi tepat sekali saat grupnya disembunyikan.
    assert pred.notna().all() and len(pred) == len(data_linear)
    assert metrik["r2_cv"] > 0.95
    assert metrik["mae_cv"] <= metrik["rmse_cv"]


def test_evaluasi_waktu_hanya_uji_tahun_baru(data_linear):
    metrik = latih_model.evaluasi_waktu(
        DummyRegressor(), data_linear[["x"]], data_linear["y"], data_linear["tahun"], batas=2024
    )
    assert metrik["n_uji_waktu"] == int((data_linear["tahun"] >= 2024).sum())
    assert metrik["mae_waktu"] > 0


def test_latih_satu_pilih_model_kalau_lolos_gerbang(data_linear):
    _, info, oof = latih_model.latih_satu("uji", data_linear, ["x"], "y", "grup", n_fold=3, uji_waktu=False)
    assert info["layak"] is True
    assert info["terpilih"] != "baseline_rata_rata"
    assert info["n_grup"] == 6 and len(oof) == len(data_linear)


def test_latih_satu_jatuh_ke_baseline_kalau_cuma_noise(data_linear):
    acak = np.random.default_rng(1)
    df = data_linear.assign(y=acak.normal(1.2, 0.05, len(data_linear)))
    _, info, _ = latih_model.latih_satu("uji", df, ["x"], "y", "grup", n_fold=3, uji_waktu=False)
    assert info["layak"] is False
    assert info["terpilih"] == "baseline_rata_rata"
    assert info["pentingnya_fitur"] == {}
