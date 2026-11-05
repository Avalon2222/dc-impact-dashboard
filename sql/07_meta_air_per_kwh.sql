-- Intensitas air situs Meta (liter per kWh) vs iklim tahunan
-- VIEW v_meta_intensitas_air sudah menghitung liter/kWh; di sini di-JOIN ke iklim tahunan (kuartal = 0).
SELECT
    m.situs,
    m.negara,
    m.tahun,
    ROUND(m.liter_per_kwh, 2)    AS liter_per_kwh,
    ROUND(i.bola_basah_rata, 1)  AS bola_basah_rata_c,
    i.hari_panas_lembap
FROM v_meta_intensitas_air m
JOIN iklim i ON i.lokasi_id = m.lokasi_id AND i.tahun = m.tahun AND i.kuartal = 0
ORDER BY liter_per_kwh DESC;
