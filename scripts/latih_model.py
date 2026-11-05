"""
latih_model.py - Melatih dan mengevaluasi model prediksi PUE dan WUE dari iklim.

Dua model:
  1. PUE kuartalan  <- iklim kuartalan + umur kampus + tahun
     Data latih: PUE per kampus Google (2016-sekarang) JOIN iklim NASA POWER.
  2. WUE tahunan    <- iklim tahunan + tahun
     Data latih: liter air per kWh listrik tiap situs Meta (2020-2024) JOIN iklim.

Cara evaluasi (ini bagian terpenting, bukan angka akurasinya):
  - Baseline "tebak rata-rata" sebagai pembanding. Model yang tidak
    mengalahkan baseline tidak layak dipakai.
  - GroupKFold menurut kampus/situs: saat menguji satu kampus, semua kuartal
    kampus itu disembunyikan dari pelatihan. Ini meniru kasus nyata kita:
    memprediksi lokasi yang belum pernah dilihat model (Indonesia).
  - Uji waktu (hanya PUE): latih <= 2023, uji >= 2024, untuk melihat apakah
    model tetap masuk akal pada data terbaru.
  - Gerbang kelayakan: model hanya dipakai kalau MAE-nya minimal 15% lebih
    baik dari baseline DAN R2 cross-validation >= 0,2. Kalau tidak lolos,
    yang disimpan adalah baseline (rata-rata), supaya dashboard tidak
    menampilkan "prediksi" yang sebenarnya tidak lebih baik dari menebak.

Keluaran:
  models/model_pue.joblib, models/model_wue.joblib  - model terbaik
  models/metrik.json                                - semua angka evaluasi
  data/prediksi_lokasi.csv                          - prediksi untuk lokasi Indonesia

Jalankan:  python scripts/latih_model.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.model import (  # noqa: E402
    DIR_MODEL, FITUR_PUE, FITUR_WUE, UMUR_MATANG, siapkan_fitur_pue, siapkan_fitur_wue,
)

DATA = ROOT / "data"
ACAK = 42
GERBANG_R2 = 0.20       # R2 cross-validation minimal supaya model dianggap layak
GERBANG_MAE = 0.85      # MAE model harus <= 85% MAE baseline


def kunci_lokasi(lat: float, lon: float) -> str:
    return f"{lat:.2f},{lon:.2f}"


# ---------------------------------------------------------------------------
# 1. DATA LATIH
# ---------------------------------------------------------------------------
def data_latih_pue() -> pd.DataFrame:
    pue = pd.read_csv(DATA / "pue_google_kuartalan.csv")
    pue = pue[pue["kampus"] != "Fleet"].dropna(subset=["pue_kuartalan"]).copy()
    lokasi = pd.read_csv(DATA / "lokasi_kampus.csv")
    lokasi = lokasi[lokasi["perusahaan"] == "google"]
    lokasi["lokasi_id"] = [kunci_lokasi(a, b) for a, b in zip(lokasi["lat"], lokasi["lon"])]
    iklim = pd.read_csv(DATA / "iklim_kuartalan.csv")
    iklim = iklim[iklim["kuartal"] > 0]

    # Umur kampus = berapa kuartal sejak pertama kali muncul di laporan (fase ramp-up PUE tinggi).
    pue["indeks_kuartal"] = pue["tahun"] * 4 + pue["kuartal"]
    pertama = pue.groupby("kampus")["indeks_kuartal"].transform("min")
    pue["umur_kuartal"] = (pue["indeks_kuartal"] - pertama).clip(upper=UMUR_MATANG)

    df = (
        pue.merge(lokasi[["kampus", "lokasi_id", "negara"]], on="kampus", how="inner")
        .merge(iklim, on=["lokasi_id", "tahun", "kuartal"], how="inner")
    )
    return df.reset_index(drop=True)


def data_latih_wue() -> pd.DataFrame:
    meta = pd.read_csv(DATA / "meta_listrik_air_tahunan.csv")
    meta = meta[meta["listrik_mwh"] > 50_000].copy()  # situs yang baru mulai beroperasi tidak representatif
    meta["liter_per_kwh"] = meta["air_megaliter"] * 1e6 / (meta["listrik_mwh"] * 1e3)
    lokasi = pd.read_csv(DATA / "lokasi_kampus.csv")
    lokasi = lokasi[lokasi["perusahaan"] == "meta"]
    lokasi["lokasi_id"] = [kunci_lokasi(a, b) for a, b in zip(lokasi["lat"], lokasi["lon"])]
    iklim = pd.read_csv(DATA / "iklim_kuartalan.csv")
    iklim = iklim[iklim["kuartal"] == 0]
    df = (
        meta.merge(lokasi[["kampus", "lokasi_id", "negara"]], left_on="situs", right_on="kampus", how="inner")
        .merge(iklim, on=["lokasi_id", "tahun"], how="inner")
    )
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# 2. KANDIDAT MODEL & EVALUASI
# ---------------------------------------------------------------------------
def kandidat() -> dict:
    return {
        "baseline_rata_rata": DummyRegressor(strategy="mean"),
        "ridge": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
        "random_forest": RandomForestRegressor(
            n_estimators=400, min_samples_leaf=5, max_features=0.6, random_state=ACAK, n_jobs=-1
        ),
        "gradient_boosting": HistGradientBoostingRegressor(
            max_depth=3, learning_rate=0.05, max_iter=300, min_samples_leaf=10, l2_regularization=1.0, random_state=ACAK
        ),
    }


def evaluasi_cv(model, X: pd.DataFrame, y: pd.Series, grup: pd.Series, n_fold: int) -> dict:
    """Cross-validation menurut grup (kampus/situs): prediksi out-of-fold, lalu hitung metrik."""
    pred = pd.Series(np.nan, index=y.index)
    for latih, uji in GroupKFold(n_splits=n_fold).split(X, y, grup):
        model.fit(X.iloc[latih], y.iloc[latih])
        pred.iloc[uji] = model.predict(X.iloc[uji])
    return {
        "mae_cv": float(mean_absolute_error(y, pred)),
        "rmse_cv": float(root_mean_squared_error(y, pred)),
        "r2_cv": float(r2_score(y, pred)),
    }, pred


def evaluasi_waktu(model, X: pd.DataFrame, y: pd.Series, tahun: pd.Series, batas: int = 2024) -> dict:
    """Latih di tahun < batas, uji di tahun >= batas."""
    latih, uji = tahun < batas, tahun >= batas
    model.fit(X[latih], y[latih])
    pred = model.predict(X[uji])
    return {
        "mae_waktu": float(mean_absolute_error(y[uji], pred)),
        "r2_waktu": float(r2_score(y[uji], pred)),
        "n_uji_waktu": int(uji.sum()),
    }


def pentingnya_fitur(model, fitur: list[str], X: pd.DataFrame, y: pd.Series) -> dict:
    """Permutation importance: seberapa buruk model kalau satu fitur diacak."""
    from sklearn.inspection import permutation_importance

    hasil = permutation_importance(model, X, y, n_repeats=10, random_state=ACAK, scoring="neg_mean_absolute_error")
    return {f: float(v) for f, v in sorted(zip(fitur, hasil.importances_mean), key=lambda t: -t[1])}


def latih_satu(nama: str, df: pd.DataFrame, fitur: list[str], target: str, grup: str, n_fold: int, uji_waktu: bool) -> tuple:
    X, y = df[fitur], df[target]
    laporan, prediksi_oof = {}, {}
    for nama_model, model in kandidat().items():
        metrik, pred = evaluasi_cv(model, X, y, df[grup], n_fold)
        if uji_waktu:
            metrik.update(evaluasi_waktu(model, X, y, df["tahun"]))
        laporan[nama_model] = metrik
        prediksi_oof[nama_model] = pred
        print(f"  {nama}/{nama_model:<20} MAE cv {metrik['mae_cv']:.4f}  R2 cv {metrik['r2_cv']:+.3f}"
              + (f"  | uji waktu MAE {metrik['mae_waktu']:.4f}" if uji_waktu else ""))

    # Pilih model terbaik menurut MAE cross-validation, lalu uji gerbang kelayakan terhadap baseline.
    kandidat_terbaik = min((k for k in laporan if k != "baseline_rata_rata"), key=lambda k: laporan[k]["mae_cv"])
    mae_baseline = laporan["baseline_rata_rata"]["mae_cv"]
    lolos = (
        laporan[kandidat_terbaik]["mae_cv"] <= GERBANG_MAE * mae_baseline
        and laporan[kandidat_terbaik]["r2_cv"] >= GERBANG_R2
    )
    terpilih = kandidat_terbaik if lolos else "baseline_rata_rata"
    if lolos:
        alasan = (f"{kandidat_terbaik} lolos gerbang: MAE {laporan[kandidat_terbaik]['mae_cv']:.4f} vs baseline "
                  f"{mae_baseline:.4f}, R2 cv {laporan[kandidat_terbaik]['r2_cv']:.2f}")
    else:
        alasan = (f"tidak ada model yang lolos gerbang (R2 cv >= {GERBANG_R2} dan MAE <= {GERBANG_MAE:.0%} baseline); "
                  f"kandidat terbaik {kandidat_terbaik} R2 cv {laporan[kandidat_terbaik]['r2_cv']:.2f}. "
                  "Dipakai baseline rata-rata.")
    print(f"  -> {alasan}")
    model = kandidat()[terpilih].fit(X, y)
    info = {
        "terpilih": terpilih,
        "layak": bool(lolos),
        "alasan": alasan,
        "n_baris": int(len(df)),
        "n_grup": int(df[grup].nunique()),
        "fitur": fitur,
        "target": target,
        "rentang_target": [float(y.min()), float(y.max())],
        "rata_rata_target": float(y.mean()),
        "evaluasi": laporan,
        "pentingnya_fitur": pentingnya_fitur(model, fitur, X, y) if lolos else {},
    }
    return model, info, prediksi_oof[terpilih]


# ---------------------------------------------------------------------------
# 3. PREDIKSI UNTUK LOKASI INDONESIA
# ---------------------------------------------------------------------------
def prediksi_indonesia(model_pue, model_wue) -> pd.DataFrame:
    fasilitas = pd.read_csv(DATA / "data_center_indonesia.csv")
    fasilitas["lokasi_id"] = [kunci_lokasi(a, b) for a, b in zip(fasilitas["lat"], fasilitas["lon"])]
    lokasi = (
        fasilitas.groupby("lokasi_id")
        .agg(lat=("lat", "first"), lon=("lon", "first"),
             kabupaten_kota=("kabupaten_kota", "first"), provinsi=("provinsi", "first"))
        .reset_index()
    )
    iklim = pd.read_csv(DATA / "iklim_kuartalan.csv")
    tahun_terakhir = int(iklim.loc[iklim["kuartal"] == 0, "tahun"].max())
    tahun_prediksi = date.today().year

    kuartalan = iklim[(iklim["kuartal"] > 0) & (iklim["tahun"] == tahun_terakhir)]
    kuartalan = kuartalan[kuartalan["lokasi_id"].isin(lokasi["lokasi_id"])].copy()
    kuartalan["pue_prediksi"] = model_pue.predict(siapkan_fitur_pue(kuartalan, UMUR_MATANG, tahun_prediksi))
    pue_lebar = kuartalan.pivot(index="lokasi_id", columns="kuartal", values="pue_prediksi")
    pue_lebar.columns = [f"pue_q{int(k)}" for k in pue_lebar.columns]
    pue_lebar["pue_prediksi"] = pue_lebar.mean(axis=1)

    tahunan = iklim[(iklim["kuartal"] == 0) & (iklim["tahun"] == tahun_terakhir)]
    tahunan = tahunan[tahunan["lokasi_id"].isin(lokasi["lokasi_id"])].copy()
    tahunan["wue_prediksi"] = np.clip(model_wue.predict(siapkan_fitur_wue(tahunan, tahun_prediksi)), 0, None)

    hasil = (
        lokasi.merge(pue_lebar.reset_index(), on="lokasi_id")
        .merge(tahunan[["lokasi_id", "wue_prediksi", "suhu_rata", "rh_rata", "bola_basah_rata", "hari_panas_lembap", "cdd18"]],
               on="lokasi_id")
    )
    hasil["tahun_iklim"] = tahun_terakhir
    return hasil.round(4).sort_values("pue_prediksi", ascending=False).reset_index(drop=True)


def main() -> int:
    import joblib

    DIR_MODEL.mkdir(exist_ok=True)
    print("Melatih model PUE (Google) ...")
    df_pue = data_latih_pue()
    model_pue, info_pue, oof_pue = latih_satu("pue", df_pue, FITUR_PUE, "pue_kuartalan", "kampus", 5, uji_waktu=True)
    print("Melatih model WUE (Meta) ...")
    df_wue = data_latih_wue()
    model_wue, info_wue, oof_wue = latih_satu("wue", df_wue, FITUR_WUE, "liter_per_kwh", "situs", df_wue["situs"].nunique(), uji_waktu=False)

    joblib.dump(model_pue, DIR_MODEL / "model_pue.joblib")
    joblib.dump(model_wue, DIR_MODEL / "model_wue.joblib")

    # Simpan prediksi out-of-fold supaya grafik "observasi vs prediksi" di dashboard jujur (bukan data latih).
    df_pue.assign(pue_prediksi_oof=oof_pue.values)[
        ["kampus", "negara", "tahun", "kuartal", "pue_kuartalan", "pue_prediksi_oof", "bola_basah_rata", "umur_kuartal"]
    ].round(4).to_csv(DATA / "evaluasi_pue_oof.csv", index=False)
    df_wue.assign(wue_prediksi_oof=oof_wue.values)[
        ["situs", "negara", "tahun", "liter_per_kwh", "wue_prediksi_oof", "bola_basah_rata"]
    ].round(4).to_csv(DATA / "evaluasi_wue_oof.csv", index=False)

    hasil = prediksi_indonesia(model_pue, model_wue)
    hasil.to_csv(DATA / "prediksi_lokasi.csv", index=False)

    metrik = {
        "dilatih_pada": date.today().isoformat(),
        "sumber": {
            "pue": "Google Data Center Efficiency (PUE kuartalan per kampus) + NASA POWER",
            "wue": "Meta 2025 Environmental Data Index (listrik & air per situs 2020-2024) + NASA POWER",
        },
        "model": {"pue": info_pue, "wue": info_wue},
        "prediksi_indonesia": {
            "pue_min": float(hasil["pue_prediksi"].min()), "pue_maks": float(hasil["pue_prediksi"].max()),
            "wue_min": float(hasil["wue_prediksi"].min()), "wue_maks": float(hasil["wue_prediksi"].max()),
            "tahun_iklim": int(hasil["tahun_iklim"].iloc[0]),
        },
    }
    (DIR_MODEL / "metrik.json").write_text(json.dumps(metrik, indent=2, ensure_ascii=False))
    print(f"Model terpilih: PUE={info_pue['terpilih']}, WUE={info_wue['terpilih']}")
    print(hasil[["kabupaten_kota", "pue_prediksi", "wue_prediksi", "bola_basah_rata"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
