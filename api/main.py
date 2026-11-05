"""
main.py - API HTTP (FastAPI) di atas database DuckDB dan model prediksi.

Mengapa ada API padahal sudah ada dashboard?
  Dashboard untuk manusia, API untuk program lain: notebook, spreadsheet,
  aplikasi web lain, atau chatbot bisa menarik angka yang sama tanpa membuka
  Streamlit. Logika hitungnya tetap satu (src/hitung.py, src/db.py, src/model.py),
  API hanya membungkusnya.

Jalankan lokal:
    uvicorn api.main:app --reload
    buka http://127.0.0.1:8000/docs  (dokumentasi interaktif otomatis)

Atau lewat Docker:
    docker build -t dc-impact-api .
    docker run -p 8000:8000 dc-impact-api
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src import db, hitung
from src.model import FITUR_IKLIM, muat_metrik, muat_model, prediksi_pue, prediksi_wue, siapkan_fitur_pue, siapkan_fitur_wue
from src.muat_data import muat_parameter

ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="Dampak Data Center Indonesia API",
    version="1.0.0",
    description=(
        "Data fasilitas data center Indonesia, estimasi listrik & air, query SQL hanya-baca, "
        "dan model prediksi PUE/WUE dari iklim. Sumber dan asumsi: lihat data/SUMBER_DATA.md."
    ),
)

PARAM = muat_parameter()
Status = Literal["beroperasi", "dibangun", "rencana"]


def _rapikan(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> list of dict yang aman di-JSON-kan (NaN jadi null)."""
    return df.astype(object).where(df.notna(), None).to_dict(orient="records")


# ---------------------------------------------------------------------------
# Skema permintaan/jawaban (Pydantic): dokumentasi & validasi otomatis
# ---------------------------------------------------------------------------
class Estimasi(BaseModel):
    kapasitas_it_mw: float = Field(..., gt=0, description="Kapasitas IT (MW)")
    utilisasi: float = Field(..., ge=0, le=1)
    pue: float = Field(..., ge=1)
    wue_liter_per_kwh: float = Field(..., ge=0)
    listrik_gwh_tahun: float
    air_m3_tahun: float
    setara_orang_listrik: float
    setara_orang_air: float


class FiturIklim(BaseModel):
    """Ringkasan iklim satu periode. Satuan: °C, %, hari, derajat-hari (dasar 18 °C)."""
    suhu_rata: float = Field(..., ge=-40, le=45, examples=[27.6])
    suhu_maks_rata: float = Field(..., ge=-40, le=55, examples=[32.0])
    rh_rata: float = Field(..., ge=0, le=100, examples=[83.0])
    titik_embun_rata: float = Field(..., ge=-50, le=35, examples=[24.0])
    bola_basah_rata: float = Field(..., ge=-40, le=35, examples=[26.0])
    bola_basah_p90: float = Field(..., ge=-40, le=35, examples=[27.0])
    hari_panas_lembap: float = Field(..., ge=0, le=366, examples=[365])
    cdd18: float = Field(..., ge=0, examples=[3500.0])


class PermintaanPrediksi(BaseModel):
    iklim: FiturIklim
    umur_kuartal: int = Field(16, ge=0, le=16, description="Kuartal sejak kampus mulai beroperasi (16 = sudah stabil)")
    tahun: int = Field(2026, ge=2016, le=2040)


class PermintaanSQL(BaseModel):
    sql: str = Field(..., examples=["SELECT provinsi, SUM(kapasitas_it_mw) AS mw FROM fasilitas GROUP BY provinsi"])
    batas: int = Field(200, ge=1, le=1000)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@app.get("/", tags=["info"])
def beranda():
    metrik = muat_metrik() or {}
    return {
        "nama": app.title,
        "dokumentasi": "/docs",
        "endpoint": ["/fasilitas", "/fasilitas/{id}", "/ringkasan", "/estimasi", "/prediksi/lokasi",
                     "/prediksi/pue", "/prediksi/wue", "/model/metrik", "/sql/tersimpan", "/sql"],
        "model_dilatih_pada": metrik.get("dilatih_pada"),
    }


@app.get("/fasilitas", tags=["data"])
def daftar_fasilitas(
    status: Status | None = None,
    provinsi: str | None = None,
    keyakinan: Literal["tinggi", "sedang", "rendah"] | None = None,
    min_mw: float = Query(0, ge=0),
):
    """Daftar data center Indonesia, bisa difilter. Data dari tabel `fasilitas` di DuckDB."""
    syarat, params = ["kapasitas_it_mw >= ?"], [min_mw]
    if status:
        syarat.append("status = ?"); params.append(status)
    if provinsi:
        syarat.append("provinsi = ?"); params.append(provinsi)
    if keyakinan:
        syarat.append("keyakinan = ?"); params.append(keyakinan)
    df = db.jalankan(f"SELECT * FROM fasilitas WHERE {' AND '.join(syarat)} ORDER BY kapasitas_it_mw DESC", params)
    return {"jumlah": len(df), "fasilitas": _rapikan(df)}


@app.get("/fasilitas/{id}", tags=["data"])
def satu_fasilitas(id: int):
    df = db.jalankan("SELECT * FROM fasilitas WHERE id = ?", [id])
    if df.empty:
        raise HTTPException(404, f"Fasilitas id {id} tidak ada")
    return _rapikan(df)[0]


@app.get("/ringkasan", tags=["estimasi"])
def ringkasan(
    utilisasi: float = Query(PARAM["utilisasi"], ge=0, le=1),
    pue: float = Query(PARAM["pue"], ge=1),
    wue: float = Query(PARAM["wue"], ge=0),
    status: Status | None = None,
):
    """Total kapasitas, listrik, dan air per provinsi dengan asumsi yang bisa diubah lewat query string."""
    syarat = "WHERE status = ?" if status else ""
    df = db.jalankan(
        f"""
        SELECT provinsi, COUNT(*) AS fasilitas, SUM(kapasitas_it_mw) AS kapasitas_it_mw
        FROM fasilitas {syarat} GROUP BY provinsi ORDER BY kapasitas_it_mw DESC
        """,
        [status] if status else [],
    )
    df["listrik_gwh_tahun"] = hitung.listrik_tahunan_gwh(df["kapasitas_it_mw"], utilisasi, pue)
    df["air_m3_tahun"] = hitung.air_tahunan_m3(df["kapasitas_it_mw"], utilisasi, wue)
    total = {
        "fasilitas": int(df["fasilitas"].sum()),
        "kapasitas_it_mw": float(df["kapasitas_it_mw"].sum()),
        "listrik_gwh_tahun": float(df["listrik_gwh_tahun"].sum()),
        "air_m3_tahun": float(df["air_m3_tahun"].sum()),
    }
    return {"asumsi": {"utilisasi": utilisasi, "pue": pue, "wue": wue, "status": status},
            "total": total, "per_provinsi": _rapikan(df.round(2))}


@app.get("/estimasi", response_model=Estimasi, tags=["estimasi"])
def estimasi(
    kapasitas_it_mw: float = Query(..., gt=0, examples=[10]),
    utilisasi: float = Query(PARAM["utilisasi"], ge=0, le=1),
    pue: float = Query(PARAM["pue"], ge=1),
    wue: float = Query(PARAM["wue"], ge=0),
):
    """Hitung listrik & air satu fasilitas hipotetis. Rumus persis sama dengan dashboard (src/hitung.py)."""
    gwh = hitung.listrik_tahunan_gwh(kapasitas_it_mw, utilisasi, pue)
    m3 = hitung.air_tahunan_m3(kapasitas_it_mw, utilisasi, wue)
    return Estimasi(
        kapasitas_it_mw=kapasitas_it_mw, utilisasi=utilisasi, pue=pue, wue_liter_per_kwh=wue,
        listrik_gwh_tahun=gwh, air_m3_tahun=m3,
        setara_orang_listrik=hitung.setara_penduduk_listrik(gwh, PARAM["listrik_per_kapita_kwh_tahun"]),
        setara_orang_air=hitung.setara_penduduk_air(m3, PARAM["air_per_orang_liter_hari"]),
    )


@app.get("/prediksi/lokasi", tags=["model"])
def prediksi_lokasi():
    """Prediksi PUE/WUE kelas hyperscale untuk tiap lokasi data center Indonesia (sudah dihitung pipeline)."""
    try:
        df = db.jalankan("SELECT * FROM prediksi_lokasi ORDER BY pue_prediksi DESC")
    except Exception as e:  # tabel belum ada kalau pipeline belum pernah jalan
        raise HTTPException(503, f"Prediksi belum tersedia: {e}")
    return {"jumlah": len(df), "lokasi": _rapikan(df)}


@app.post("/prediksi/pue", tags=["model"])
def prediksi_pue_endpoint(permintaan: PermintaanPrediksi):
    """Prediksi PUE kuartalan dari ringkasan iklim satu kuartal (model Ridge, dilatih pada data Google)."""
    model = muat_model("pue")
    if model is None:
        raise HTTPException(503, "Model PUE belum dilatih")
    iklim = pd.DataFrame([permintaan.iklim.model_dump()])
    fitur = siapkan_fitur_pue(iklim, permintaan.umur_kuartal, permintaan.tahun)
    nilai = float(prediksi_pue(fitur, model).iloc[0])
    return {"pue_prediksi": round(nilai, 4), "fitur": fitur.iloc[0].to_dict(),
            "catatan": "Perkiraan untuk fasilitas kelas hyperscale; kolokasi umumnya lebih tinggi."}


@app.post("/prediksi/wue", tags=["model"])
def prediksi_wue_endpoint(permintaan: PermintaanPrediksi):
    """Prediksi WUE tahunan (liter/kWh) dari ringkasan iklim setahun. Lihat /model/metrik untuk kelayakan model."""
    model = muat_model("wue")
    if model is None:
        raise HTTPException(503, "Model WUE belum dilatih")
    iklim = pd.DataFrame([permintaan.iklim.model_dump()])
    fitur = siapkan_fitur_wue(iklim, permintaan.tahun)
    metrik = (muat_metrik() or {}).get("model", {}).get("wue", {})
    return {"wue_prediksi": round(float(prediksi_wue(fitur, model).iloc[0]), 4),
            "model": metrik.get("terpilih"), "layak": metrik.get("layak"), "catatan": metrik.get("alasan")}


@app.get("/model/metrik", tags=["model"])
def metrik_model():
    """Semua angka evaluasi model (cross-validation per kampus, uji waktu, pentingnya fitur)."""
    metrik = muat_metrik()
    if metrik is None:
        raise HTTPException(503, "Model belum dilatih")
    return metrik


@app.get("/sql/tersimpan", tags=["sql"])
def sql_tersimpan():
    """Daftar query SQL siap pakai dari folder sql/."""
    return db.query_tersimpan()


@app.post("/sql", tags=["sql"])
def jalankan_sql(permintaan: PermintaanSQL):
    """Jalankan SELECT bebas pada DuckDB (hanya-baca; INSERT/UPDATE/DROP ditolak)."""
    if not db.sql_aman(permintaan.sql):
        raise HTTPException(400, "Hanya satu pernyataan SELECT/WITH yang diizinkan.")
    try:
        df = db.jalankan(permintaan.sql)
    except Exception as e:
        raise HTTPException(400, f"SQL gagal: {e}")
    return {"jumlah": len(df), "kolom": list(df.columns), "baris": _rapikan(df.head(permintaan.batas))}
