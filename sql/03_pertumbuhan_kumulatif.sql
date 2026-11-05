-- Pertumbuhan kapasitas kumulatif per tahun
-- Window function SUM() OVER (ORDER BY tahun) = running total, tanpa loop.
WITH per_tahun AS (
    SELECT tahun, status, SUM(kapasitas_it_mw) AS mw
    FROM fasilitas
    WHERE tahun IS NOT NULL
    GROUP BY tahun, status
)
SELECT
    tahun,
    status,
    mw                                                              AS mw_tahun_ini,
    SUM(mw) OVER (PARTITION BY status ORDER BY tahun)               AS mw_kumulatif,
    SUM(mw) OVER (ORDER BY tahun ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS mw_kumulatif_semua
FROM per_tahun
ORDER BY tahun, status;
