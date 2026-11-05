-- Iklim lokasi data center Indonesia dibanding kampus Google & Meta (tahun penuh terakhir)
-- UNION ALL dua sumber, lalu urutkan menurut suhu bola basah: makin tinggi makin berat pendinginnya.
WITH tahun_terakhir AS (
    SELECT MAX(tahun) AS tahun FROM iklim WHERE kuartal = 0
),
titik AS (
    SELECT DISTINCT kabupaten_kota AS nama, 'Indonesia' AS negara, lokasi_id FROM fasilitas
    UNION ALL
    SELECT kampus, negara, lokasi_id FROM lokasi_kampus
)
SELECT
    t.nama,
    t.negara,
    ROUND(AVG(i.suhu_rata), 1)       AS suhu_rata_c,
    ROUND(AVG(i.bola_basah_rata), 1) AS bola_basah_rata_c,
    ROUND(AVG(i.hari_panas_lembap))  AS hari_panas_lembap,
    ROUND(AVG(i.cdd18))              AS cooling_degree_days
FROM titik t
JOIN iklim i ON i.lokasi_id = t.lokasi_id AND i.kuartal = 0
JOIN tahun_terakhir y ON y.tahun = i.tahun
GROUP BY t.nama, t.negara
ORDER BY bola_basah_rata_c DESC;
