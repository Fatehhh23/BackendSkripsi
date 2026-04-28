-- ============================================
-- AVATAR Backend - Script Setup Database
-- ============================================
-- Setup PostgreSQL + PostGIS untuk Sistem Prediksi Tsunami
--
-- Prasyarat:
--   - PostgreSQL 15+ sudah terinstall
--   - PostGIS 3.3+ sudah terinstall
--
-- Cara menjalankan script ini sebagai user postgres:
--   psql -U postgres -f database_setup.sql
-- 
-- Atau bisa juga melalui pgAdmin:
--   1. Buka pgAdmin
--   2. Klik kanan pada Databases > Query Tool
--   3. Copy-paste isi file ini
--   4. Klik Execute (F5)
-- ============================================
-- ============================================
-- LANGKAH 1: Buat Database Baru
-- ============================================
-- Hapus database lama jika ada (HATI-HATI: akan menghapus semua data!)
DROP DATABASE IF EXISTS tsunami_db;
-- Buat database baru dengan nama "tsunami_db"
CREATE DATABASE tsunami_db WITH OWNER = postgres ENCODING = 'UTF8' LC_COLLATE = 'English_United States.1252' LC_CTYPE = 'English_United States.1252' TABLESPACE = pg_default CONNECTION
LIMIT = -1;
-- ============================================
-- LANGKAH 2: Koneksi ke Database yang Baru Dibuat
-- ============================================
-- Perintah \c digunakan untuk berpindah ke database tsunami_db
\ c tsunami_db -- ============================================
-- LANGKAH 3: Aktifkan Extension PostGIS
-- ============================================
-- PostGIS adalah extension untuk menyimpan dan memproses data geografis
-- PostGIS Topology digunakan untuk analisis topologi spatial
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
-- Verifikasi bahwa PostGIS sudah terinstall dengan benar
SELECT PostGIS_Version();
SELECT PostGIS_Full_Version();
-- ============================================
-- LANGKAH 4: Buat Tabel-Tabel Database
-- ============================================
-- Tabel ini disesuaikan dengan SQLAlchemy models di backend
-- ---------------------------------------------
-- Tabel 1: SIMULATIONS
-- ---------------------------------------------
-- Menyimpan riwayat simulasi tsunami yang dilakukan user
CREATE TABLE IF NOT EXISTS simulations (
    -- ID unik untuk setiap simulasi (UUID format)
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Parameter input gempa
    magnitude FLOAT NOT NULL,
    -- Magnitudo gempa (skala Richter)
    depth FLOAT NOT NULL,
    -- Kedalaman gempa (kilometer)
    latitude FLOAT NOT NULL,
    -- Lintang epicenter (-90 hingga 90)
    longitude FLOAT NOT NULL,
    -- Bujur epicenter (-180 hingga 180)
    -- Lokasi epicenter dalam format geometry PostGIS
    -- POINT menyimpan koordinat (longitude, latitude)
    -- SRID 4326 adalah sistem koordinat WGS84 (standar GPS)
    epicenter GEOMETRY(Point, 4326),
    -- Hasil prediksi dalam format JSON
    -- Berisi informasi: tsunamiCategory, waveHeight, arrivalTime, dll
    prediction_data JSONB NOT NULL,
    -- Metadata simulasi
    created_at TIMESTAMP DEFAULT NOW(),
    -- Waktu simulasi dibuat
    user_session_id VARCHAR(255),
    -- ID sesi user (opsional)
    ip_address VARCHAR(45),
    -- IP address user (opsional)
    -- Metrics performa
    processing_time_ms INTEGER,
    -- Waktu proses dalam milidetik
    model_version VARCHAR(50) -- Versi model ML yang digunakan
);
-- Buat index spatial untuk pencarian cepat berdasarkan lokasi
-- GIST (Generalized Search Tree) adalah tipe index untuk geometri
CREATE INDEX IF NOT EXISTS idx_simulations_epicenter ON simulations USING GIST (epicenter);
-- Buat index untuk pencarian berdasarkan waktu
CREATE INDEX IF NOT EXISTS idx_simulations_created_at ON simulations (created_at DESC);
-- ---------------------------------------------
-- Tabel 2: EARTHQUAKES
-- ---------------------------------------------
-- Menyimpan data gempa real-time dari BMKG dan USGS
CREATE TABLE IF NOT EXISTS earthquakes (
    -- ID dari sumber data (BMKG atau USGS)
    id VARCHAR(100) PRIMARY KEY,
    -- Parameter gempa
    magnitude FLOAT NOT NULL,
    -- Magnitudo gempa
    depth FLOAT NOT NULL,
    -- Kedalaman (km)
    latitude FLOAT NOT NULL,
    -- Lintang
    longitude FLOAT NOT NULL,
    -- Bujur
    -- Lokasi dalam format PostGIS Point
    location GEOMETRY(Point, 4326),
    -- Informasi tambahan
    location_name TEXT,
    -- Nama lokasi (contoh: "50 km Barat Daya Pandeglang")
    timestamp TIMESTAMP NOT NULL,
    -- Waktu kejadian gempa
    source VARCHAR(50) NOT NULL,
    -- Sumber data: BMKG atau USGS
    -- Analisis potensi tsunami
    tsunami_potential BOOLEAN DEFAULT FALSE,
    -- Apakah berpotensi tsunami
    tsunami_risk_level VARCHAR(50),
    -- Level risiko: Rendah, Sedang, Bahaya
    max_wave_height FLOAT,
    -- Tinggi gelombang maksimum (meter)
    -- Timestamps audit
    created_at TIMESTAMP DEFAULT NOW(),
    -- Kapan data disimpan
    updated_at TIMESTAMP DEFAULT NOW() -- Kapan data terakhir diupdate
);
-- Buat index spatial untuk lokasi gempa
CREATE INDEX IF NOT EXISTS idx_earthquakes_location ON earthquakes USING GIST (location);
-- Buat index untuk pencarian berdasarkan waktu kejadian
CREATE INDEX IF NOT EXISTS idx_earthquakes_timestamp ON earthquakes (timestamp DESC);
-- ---------------------------------------------
-- Tabel 3: INUNDATION_ZONES
-- ---------------------------------------------
-- Menyimpan zona genangan tsunami dari hasil simulasi
CREATE TABLE IF NOT EXISTS inundation_zones (
    -- ID unik zona genangan
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Foreign key ke tabel simulations
    -- CASCADE: jika simulasi dihapus, zona genangan juga ikut terhapus
    simulation_id UUID NOT NULL REFERENCES simulations(id) ON DELETE CASCADE,
    -- Geometry zona genangan dalam bentuk Polygon
    -- Polygon menyimpan area genangan (koordinat-koordinat batas area)
    geometry GEOMETRY(Polygon, 4326) NOT NULL,
    -- Karakteristik gelombang tsunami
    wave_height FLOAT NOT NULL,
    -- Tinggi gelombang (meter)
    arrival_time INTEGER NOT NULL,
    -- Waktu tiba gelombang (menit setelah gempa)
    -- Statistik area terdampak
    area_sqkm FLOAT,
    -- Luas area genangan (km²)
    affected_population INTEGER,
    -- Estimasi jumlah penduduk terdampak
    created_at TIMESTAMP DEFAULT NOW()
);
-- Index spatial untuk polygon zona genangan
CREATE INDEX IF NOT EXISTS idx_inundation_zones_geometry ON inundation_zones USING GIST (geometry);
-- Index untuk relasi dengan simulasi
CREATE INDEX IF NOT EXISTS idx_inundation_zones_simulation_id ON inundation_zones (simulation_id);
-- ---------------------------------------------
-- Tabel 4: COASTLINES
-- ---------------------------------------------
-- Menyimpan data garis pantai sebagai referensi
-- Data ini digunakan untuk visualisasi dan analisis jarak
CREATE TABLE IF NOT EXISTS coastlines (
    -- ID unik garis pantai
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Nama pantai/wilayah
    name VARCHAR(255) NOT NULL,
    -- Geometry garis pantai dalam bentuk LineString
    -- LineString menyimpan urutan koordinat yang membentuk garis
    geometry GEOMETRY(LineString, 4326) NOT NULL,
    -- Metadata
    region VARCHAR(100),
    -- Wilayah/provinsi
    length_km FLOAT,
    -- Panjang garis pantai (km)
    created_at TIMESTAMP DEFAULT NOW()
);
-- Index spatial untuk garis pantai
CREATE INDEX IF NOT EXISTS idx_coastlines_geometry ON coastlines USING GIST (geometry);
-- ---------------------------------------------
-- Tabel 5: CONTACT_MESSAGES
-- ---------------------------------------------
-- Menyimpan pesan yang dikirim dari form kontak user
CREATE TABLE IF NOT EXISTS contact_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'unread' NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);
-- Index untuk pencarian berdasarkan waktu
CREATE INDEX IF NOT EXISTS idx_contact_messages_created_at ON contact_messages (created_at DESC);
-- ============================================
-- LANGKAH 5: Insert Data Contoh Garis Pantai
-- ============================================
-- Menambahkan beberapa garis pantai di Selat Sunda sebagai contoh
-- ST_GeomFromText: fungsi PostGIS untuk membuat geometry dari text WKT
-- Format: LINESTRING(lon1 lat1, lon2 lat2, ...)
INSERT INTO coastlines (name, geometry, region, length_km)
VALUES -- Pantai Anyer, Banten
    (
        'Pantai Anyer',
        ST_GeomFromText(
            'LINESTRING(105.8833 -6.0833, 105.9000 -6.0667)',
            4326
        ),
        'Banten',
        2.5
    ),
    -- Pantai Carita, Banten
    (
        'Pantai Carita',
        ST_GeomFromText(
            'LINESTRING(105.7000 -6.2833, 105.7500 -6.2667)',
            4326
        ),
        'Banten',
        5.2
    ),
    -- Pesisir Lampung Selatan
    (
        'Pesisir Lampung Selatan',
        ST_GeomFromText(
            'LINESTRING(105.6500 -5.9000, 105.7000 -5.8500)',
            4326
        ),
        'Lampung',
        8.3
    );
-- ============================================
-- LANGKAH 6: Buat Fungsi-fungsi Helper
-- ============================================
-- ---------------------------------------------
-- Fungsi 1: Hitung Jarak Antar Dua Titik
-- ---------------------------------------------
-- Fungsi ini menghitung jarak real (great circle distance) 
-- antara dua koordinat dalam kilometer
--
-- Parameter:
--   lat1, lon1: Koordinat titik pertama
--   lat2, lon2: Koordinat titik kedua
-- Return: Jarak dalam kilometer (FLOAT)
--
-- Contoh penggunaan:
--   SELECT calculate_distance(-6.102, 105.423, -6.200, 105.500);
--   Hasil: ~11.2 (km)
CREATE OR REPLACE FUNCTION calculate_distance(
        lat1 FLOAT,
        -- Lintang titik 1
        lon1 FLOAT,
        -- Bujur titik 1  
        lat2 FLOAT,
        -- Lintang titik 2
        lon2 FLOAT -- Bujur titik 2
    ) RETURNS FLOAT AS $$
DECLARE point1 GEOMETRY;
point2 GEOMETRY;
BEGIN -- Buat geometry Point dari koordinat
-- ST_SetSRID: set Spatial Reference ID (4326 = WGS84)
-- ST_MakePoint: buat point dari (longitude, latitude)
point1 := ST_SetSRID(ST_MakePoint(lon1, lat1), 4326);
point2 := ST_SetSRID(ST_MakePoint(lon2, lat2), 4326);
-- Hitung jarak menggunakan geography (bukan geometry)
-- geography memperhitungkan kelengkungan bumi
-- ST_Distance mengembalikan meter, dibagi 1000 untuk dapat km
RETURN ST_Distance(
    point1::geography,
    point2::geography
) / 1000.0;
END;
$$ LANGUAGE plpgsql;
-- ---------------------------------------------
-- Fungsi 2: Cek Apakah Koordinat di Selat Sunda
-- ---------------------------------------------
-- Fungsi ini mengecek apakah suatu koordinat berada
-- dalam batas geografis Selat Sunda
--
-- Parameter:
--   lat: Lintang
--   lon: Bujur
-- Return: TRUE jika di Selat Sunda, FALSE jika tidak
--
-- Batas Selat Sunda:
--   Lintang: -7.0 hingga -5.0 (selatan)
--   Bujur: 104.5 hingga 106.5 (timur)
--
-- Contoh penggunaan:
--   SELECT is_in_sunda_strait(-6.102, 105.423);
--   Hasil: TRUE
CREATE OR REPLACE FUNCTION is_in_sunda_strait(
        lat FLOAT,
        -- Lintang
        lon FLOAT -- Bujur
    ) RETURNS BOOLEAN AS $$ BEGIN RETURN (
        lat BETWEEN -7.0 AND -5.0
        AND lon BETWEEN 104.5 AND 106.5
    );
END;
$$ LANGUAGE plpgsql;
-- ============================================
-- LANGKAH 7: Buat Views untuk Analytics
-- ============================================
-- ---------------------------------------------
-- View 1: Simulasi Terbaru
-- ---------------------------------------------
-- Menampilkan 100 simulasi terakhir dengan info penting
CREATE OR REPLACE VIEW v_recent_simulations AS
SELECT id,
    magnitude,
    depth,
    latitude,
    longitude,
    prediction_data->>'tsunamiCategory' as tsunami_category,
    created_at,
    processing_time_ms
FROM simulations
ORDER BY created_at DESC
LIMIT 100;
-- ---------------------------------------------
-- View 2: Statistik Gempa per Sumber Data
-- ---------------------------------------------
-- Menampilkan ringkasan gempa dikelompokkan berdasarkan sumber (BMKG/USGS)
CREATE OR REPLACE VIEW v_earthquake_stats AS
SELECT source,
    -- Sumber data
    COUNT(*) as total_earthquakes,
    -- Total gempa
    AVG(magnitude) as avg_magnitude,
    -- Magnitudo rata-rata
    MAX(magnitude) as max_magnitude,
    -- Magnitudo maksimum
    COUNT(
        CASE
            WHEN tsunami_potential THEN 1
        END
    ) as tsunami_count -- Jumlah berpotensi tsunami
FROM earthquakes
GROUP BY source;
-- ============================================
-- LANGKAH 8: Grant Permissions (Opsional)
-- ============================================
-- Uncomment jika ingin membuat user terpisah untuk backend
-- Ini lebih aman untuk production
-- Buat user khusus untuk aplikasi
-- CREATE USER tsunami_user WITH PASSWORD 'AVATAR23';
-- Berikan akses penuh ke database
-- GRANT ALL PRIVILEGES ON DATABASE tsunamidb TO tsunami_user;
-- Berikan akses ke semua tabel
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO tsunami_user;
-- Berikan akses ke sequences (untuk auto-increment)
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO tsunami_user;
-- ============================================
-- LANGKAH 9: Tampilkan Info Database
-- ============================================
-- Tampilkan pesan sukses dan versi software
SELECT 'Setup Database Berhasil!' as status,
    version() as versi_postgresql,
    PostGIS_Version() as versi_postgis;
-- Tampilkan ukuran setiap tabel
SELECT schemaname as skema,
    tablename as nama_tabel,
    pg_size_pretty(
        pg_total_relation_size(schemaname || '.' || tablename)
    ) AS ukuran
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC;
-- Tampilkan timezone yang digunakan
SHOW TIMEZONE;
-- ============================================
-- SELESAI!
-- ============================================
-- Database tsunami_db sudah siap digunakan!
-- 
-- Langkah selanjutnya:
-- 1. Update .env file di backend dengan DATABASE_URL yang benar
-- 2. Uncomment geometry columns di app/database/models.py
-- 3. Uncomment geospatial imports di app/database/crud.py  
-- 4. Install geoalchemy2 dan shapely: pip install geoalchemy2 shapely
-- 5. Restart backend server
-- 6. Test koneksi: python test_database.py
--
-- Untuk melihat data:
--   SELECT * FROM simulations LIMIT 10;
--   SELECT * FROM earthquakes LIMIT 10;
--   SELECT * FROM coastlines;
--   SELECT * FROM v_recent_simulations;
--   SELECT * FROM v_earthquake_stats;
--
-- Happy coding! 🌊
-- ============================================