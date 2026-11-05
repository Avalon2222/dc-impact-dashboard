-- Pola musiman PUE: kuartal mana yang paling boros?
-- Rata-rata per kuartal untuk kampus tropis vs seluruh fleet, lima tahun terakhir.
SELECT
    kuartal,
    ROUND(AVG(CASE WHEN kampus LIKE 'Singapore%' OR kampus LIKE 'Changhua%' THEN pue_kuartalan END), 3) AS pue_tropis_rata,
    ROUND(AVG(CASE WHEN kampus = 'Fleet' THEN pue_kuartalan END), 3)                                   AS pue_fleet_rata,
    ROUND(AVG(CASE WHEN kampus IN ('Hamina, Finland', 'Fredericia, Denmark') THEN pue_kuartalan END), 3) AS pue_nordik_rata
FROM pue_google
WHERE tahun >= 2021
GROUP BY kuartal
ORDER BY kuartal;
