-- PUE vs iklim: JOIN tabel PUE Google dengan tabel iklim per kampus per kuartal
-- Ini persis data latih model di scripts/latih_model.py, hanya dirangkum per kampus.
SELECT
    g.kampus,
    l.negara,
    COUNT(*)                         AS kuartal_tercatat,
    ROUND(AVG(g.pue_kuartalan), 3)   AS pue_rata,
    ROUND(AVG(i.bola_basah_rata), 1) AS bola_basah_rata_c,
    ROUND(AVG(i.suhu_rata), 1)       AS suhu_rata_c,
    ROUND(AVG(i.rh_rata), 0)         AS rh_rata_pct
FROM pue_google g
JOIN lokasi_kampus l ON l.kampus = g.kampus AND l.perusahaan = 'google'
JOIN iklim i ON i.lokasi_id = l.lokasi_id AND i.tahun = g.tahun AND i.kuartal = g.kuartal
WHERE g.tahun >= 2021
GROUP BY g.kampus, l.negara
ORDER BY pue_rata DESC;
