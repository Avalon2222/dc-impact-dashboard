-- PUE terbaru tiap kampus Google, diurutkan dari yang paling boros
-- QUALIFY + ROW_NUMBER(): ambil satu baris terakhir per kampus tanpa subquery bertingkat.
SELECT
    kampus,
    tahun,
    kuartal,
    pue_kuartalan,
    pue_ttm,
    ROUND(pue_kuartalan - 1, 3) AS overhead_pendingin_dll
FROM pue_google
WHERE kampus <> 'Fleet'
QUALIFY ROW_NUMBER() OVER (PARTITION BY kampus ORDER BY tahun DESC, kuartal DESC) = 1
ORDER BY pue_kuartalan DESC;
