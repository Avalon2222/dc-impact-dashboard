-- Kapasitas per provinsi dan status
-- GROUP BY dua kolom, lalu PIVOT manual dengan CASE supaya tiap status jadi kolom sendiri.
SELECT
    provinsi,
    COUNT(*)                                                          AS jumlah_fasilitas,
    SUM(CASE WHEN status = 'beroperasi' THEN kapasitas_it_mw ELSE 0 END) AS mw_beroperasi,
    SUM(CASE WHEN status = 'dibangun'   THEN kapasitas_it_mw ELSE 0 END) AS mw_dibangun,
    SUM(CASE WHEN status = 'rencana'    THEN kapasitas_it_mw ELSE 0 END) AS mw_rencana,
    SUM(kapasitas_it_mw)                                              AS mw_total
FROM fasilitas
GROUP BY provinsi
ORDER BY mw_total DESC;
