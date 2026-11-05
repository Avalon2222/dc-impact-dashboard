-- Operator dengan estimasi listrik terbesar
-- Memakai VIEW v_estimasi (rumus listrik & air versi SQL dengan parameter default).
SELECT
    operator,
    COUNT(*)                         AS fasilitas,
    ROUND(SUM(kapasitas_it_mw), 1)   AS mw_total,
    ROUND(SUM(listrik_gwh_tahun), 0) AS gwh_per_tahun,
    ROUND(SUM(air_m3_tahun), 0)      AS air_m3_per_tahun,
    ROUND(SUM(setara_orang_listrik)) AS setara_orang_listrik
FROM v_estimasi
GROUP BY operator
ORDER BY gwh_per_tahun DESC
LIMIT 10;
