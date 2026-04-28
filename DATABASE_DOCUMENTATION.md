# 🗄️ Dokumentasi Database AVATAR - Sistem Prediksi Tsunami

## 📋 Daftar Isi
1. [Overview](#overview)
2. [Arsitektur Database](#arsitektur-database)
3. [Struktur Tabel](#struktur-tabel)
4. [Fungsi PostGIS](#fungsi-postgis)
5. [Views & Analytics](#views--analytics)
6. [Cara Penggunaan](#cara-penggunaan)
7. [Query Contoh](#query-contoh)

---

## Overview

### Informasi Database
- **Nama Database**: `tsunami_db`
- **DBMS**: PostgreSQL 15+
- **Extension**: PostGIS 3.3+ (untuk geospatial data)
- **Encoding**: UTF-8
- **Timezone**: Disesuaikan dengan server

### Kredensial (Development)
```
Host: localhost (atau 'db' jika di Docker)
Port: 5432
Database: tsunami_db
Username: tsunami_user
Password: tsunami_password
```

> ⚠️ **PENTING**: Ganti password untuk production!

### Tujuan Database
Database ini dirancang untuk:
1. **Menyimpan riwayat simulasi** tsunami yang dilakukan pengguna
2. **Menyimpan data gempa real-time** dari BMKG dan USGS
3. **Menyimpan zona genangan** hasil prediksi tsunami
4. **Menyimpan data referensi garis pantai** untuk visualisasi
5. **Melakukan analisis geospasial** menggunakan PostGIS

---

## Arsitektur Database

### Entity Relationship Diagram

```
┌─────────────────┐
│   SIMULATIONS   │
│  (Simulasi)     │
└────────┬────────┘
         │
         │ 1:N
         │
         ▼
┌─────────────────┐
│ INUNDATION_ZONES│
│ (Zona Genangan) │
└─────────────────┘

┌─────────────────┐
│  EARTHQUAKES    │
│  (Gempa Bumi)   │
└─────────────────┘

┌─────────────────┐
│   COASTLINES    │
│  (Garis Pantai) │
└─────────────────┘
```

### Relasi Tabel
- **SIMULATIONS** → **INUNDATION_ZONES**: One-to-Many (1 simulasi bisa punya banyak zona genangan)
- **EARTHQUAKES**: Independent (data gempa real-time, tidak berelasi)
- **COASTLINES**: Independent (data referensi garis pantai)

---

## Struktur Tabel

### 1. 📊 Tabel `simulations`

**Deskripsi**: Menyimpan riwayat simulasi tsunami yang dilakukan oleh pengguna

#### Kolom-kolom:

| Kolom | Tipe | Nullable | Deskripsi |
|-------|------|----------|-----------|
| `id` | UUID | NO | Primary Key (auto-generated) |
| `magnitude` | FLOAT | NO | Magnitudo gempa (skala Richter, contoh: 7.5) |
| `depth` | FLOAT | NO | Kedalaman gempa dalam kilometer (contoh: 10.0) |
| `latitude` | FLOAT | NO | Lintang epicenter (-90 hingga 90) |
| `longitude` | FLOAT | NO | Bujur epicenter (-180 hingga 180) |
| `epicenter` | GEOMETRY | YES | Lokasi epicenter dalam format PostGIS POINT |
| `prediction_data` | JSONB | NO | Hasil prediksi dalam format JSON |
| `created_at` | TIMESTAMP | NO | Waktu simulasi dibuat (default: NOW()) |
| `user_session_id` | VARCHAR(255) | YES | ID sesi pengguna |
| `ip_address` | VARCHAR(45) | YES | IP address pengguna |
| `processing_time_ms` | INTEGER | YES | Waktu proses dalam milidetik |
| `model_version` | VARCHAR(50) | YES | Versi model ML yang digunakan |

#### Index:
- `idx_simulations_epicenter`: Spatial index pada kolom `epicenter` (GIST)
- `idx_simulations_created_at`: Index pada `created_at` untuk sorting

#### Contoh Data JSON di `prediction_data`:
```json
{
  "tsunamiCategory": "Bahaya",
  "waveHeight": 5.2,
  "arrivalTime": 15,
  "affectedAreas": ["Anyer", "Carita"],
  "confidence": 0.89
}
```

---

### 2. 🌍 Tabel `earthquakes`

**Deskripsi**: Menyimpan data gempa real-time dari BMKG dan USGS

#### Kolom-kolom:

| Kolom | Tipe | Nullable | Deskripsi |
|-------|------|----------|-----------|
| `id` | VARCHAR(100) | NO | Primary Key dari BMKG/USGS |
| `magnitude` | FLOAT | NO | Magnitudo gempa |
| `depth` | FLOAT | NO | Kedalaman dalam kilometer |
| `latitude` | FLOAT | NO | Lintang lokasi |
| `longitude` | FLOAT | NO | Bujur lokasi |
| `location` | GEOMETRY | YES | Lokasi dalam format PostGIS POINT |
| `location_name` | TEXT | YES | Nama lokasi (contoh: "50 km SW Pandeglang") |
| `timestamp` | TIMESTAMP | NO | Waktu kejadian gempa |
| `source` | VARCHAR(50) | NO | Sumber data: "BMKG" atau "USGS" |
| `tsunami_potential` | BOOLEAN | YES | Apakah berpotensi tsunami (default: FALSE) |
| `tsunami_risk_level` | VARCHAR(50) | YES | Level risiko: Rendah, Sedang, Bahaya |
| `max_wave_height` | FLOAT | YES | Tinggi gelombang maksimum dalam meter |
| `created_at` | TIMESTAMP | NO | Kapan data disimpan ke database |
| `updated_at` | TIMESTAMP | NO | Kapan data terakhir diupdate |

#### Index:
- `idx_earthquakes_location`: Spatial index pada kolom `location` (GIST)
- `idx_earthquakes_timestamp`: Index pada `timestamp` untuk sorting

---

### 3. 🌊 Tabel `inundation_zones`

**Deskripsi**: Menyimpan zona genangan tsunami dari hasil simulasi

#### Kolom-kolom:

| Kolom | Tipe | Nullable | Deskripsi |
|-------|------|----------|-----------|
| `id` | UUID | NO | Primary Key (auto-generated) |
| `simulation_id` | UUID | NO | Foreign Key ke tabel `simulations` |
| `geometry` | GEOMETRY | NO | Area genangan dalam format PostGIS POLYGON |
| `wave_height` | FLOAT | NO | Tinggi gelombang dalam meter |
| `arrival_time` | INTEGER | NO | Waktu tiba dalam menit setelah gempa |
| `area_sqkm` | FLOAT | YES | Luas area genangan dalam km² |
| `affected_population` | INTEGER | YES | Estimasi jumlah penduduk terdampak |
| `created_at` | TIMESTAMP | YES | Waktu data dibuat |

#### Index:
- `idx_inundation_zones_geometry`: Spatial index pada kolom `geometry` (GIST)
- `idx_inundation_zones_simulation_id`: Index pada `simulation_id`

#### Foreign Key Constraint:
- `simulation_id` REFERENCES `simulations(id)` ON DELETE CASCADE
  - Jika simulasi dihapus, zona genangan juga ikut terhapus

---

### 4. 🏖️ Tabel `coastlines`

**Deskripsi**: Menyimpan data garis pantai sebagai referensi untuk visualisasi

#### Kolom-kolom:

| Kolom | Tipe | Nullable | Deskripsi |
|-------|------|----------|-----------|
| `id` | UUID | NO | Primary Key (auto-generated) |
| `name` | VARCHAR(255) | NO | Nama pantai/wilayah |
| `geometry` | GEOMETRY | NO | Garis pantai dalam format PostGIS LINESTRING |
| `region` | VARCHAR(100) | YES | Nama wilayah/provinsi |
| `length_km` | FLOAT | YES | Panjang garis pantai dalam kilometer |
| `created_at` | TIMESTAMP | YES | Waktu data dibuat |

#### Index:
- `idx_coastlines_geometry`: Spatial index pada kolom `geometry` (GIST)

#### Data Awal:
Database sudah dilengkapi dengan 3 garis pantai contoh:
1. **Pantai Anyer** (Banten) - 2.5 km
2. **Pantai Carita** (Banten) - 5.2 km
3. **Pesisir Lampung Selatan** (Lampung) - 8.3 km

---

## Fungsi PostGIS

### 1. 📏 `calculate_distance(lat1, lon1, lat2, lon2)`

**Deskripsi**: Menghitung jarak real (great circle distance) antara dua koordinat

**Parameter**:
- `lat1` (FLOAT): Lintang titik pertama
- `lon1` (FLOAT): Bujur titik pertama
- `lat2` (FLOAT): Lintang titik kedua
- `lon2` (FLOAT): Bujur titik kedua

**Return**: FLOAT (jarak dalam kilometer)

**Contoh Penggunaan**:
```sql
-- Hitung jarak antara Jakarta dan Anyer
SELECT calculate_distance(-6.2088, 106.8456, -6.0833, 105.8833);
-- Result: ~94.2 km
```

**Cara Kerja**:
- Menggunakan tipe data `geography` untuk perhitungan akurat di permukaan bumi
- Memperhitungkan kelengkungan bumi (great circle distance)
- Lebih akurat daripada perhitungan euclidean biasa

---

### 2. ✅ `is_in_sunda_strait(lat, lon)`

**Deskripsi**: Mengecek apakah suatu koordinat berada dalam batas geografis Selat Sunda

**Parameter**:
- `lat` (FLOAT): Lintang
- `lon` (FLOAT): Bujur

**Return**: BOOLEAN (TRUE jika di Selat Sunda, FALSE jika tidak)

**Batas Geografis Selat Sunda**:
- Lintang: -7.0° hingga -5.0° (selatan)
- Bujur: 104.5° hingga 106.5° (timur)

**Contoh Penggunaan**:
```sql
-- Cek apakah koordinat Anyer ada di Selat Sunda
SELECT is_in_sunda_strait(-6.0833, 105.8833);
-- Result: TRUE

-- Cek apakah Jakarta ada di Selat Sunda
SELECT is_in_sunda_strait(-6.2088, 106.8456);
-- Result: FALSE
```

---

## Views & Analytics

### 1. 📈 View `v_recent_simulations`

**Deskripsi**: Menampilkan 100 simulasi terakhir dengan informasi penting

**Kolom**:
- `id`: ID simulasi
- `magnitude`: Magnitudo gempa
- `depth`: Kedalaman gempa
- `latitude`: Lintang epicenter
- `longitude`: Bujur epicenter
- `tsunami_category`: Kategori tsunami (dari prediction_data)
- `created_at`: Waktu simulasi
- `processing_time_ms`: Waktu proses

**Query**:
```sql
SELECT * FROM v_recent_simulations;
```

---

### 2. 📊 View `v_earthquake_stats`

**Deskripsi**: Statistik gempa dikelompokkan berdasarkan sumber data (BMKG/USGS)

**Kolom**:
- `source`: Sumber data (BMKG/USGS)
- `total_earthquakes`: Total jumlah gempa
- `avg_magnitude`: Magnitudo rata-rata
- `max_magnitude`: Magnitudo maksimum
- `tsunami_count`: Jumlah gempa berpotensi tsunami

**Query**:
```sql
SELECT * FROM v_earthquake_stats;
```

**Contoh Result**:
```
source | total_earthquakes | avg_magnitude | max_magnitude | tsunami_count
-------|-------------------|---------------|---------------|---------------
BMKG   | 150               | 5.2           | 7.8           | 12
USGS   | 89                | 4.9           | 7.5           | 8
```

---

## Cara Penggunaan

### Setup Database dengan Docker

**1. Start Docker Compose**:
```bash
cd "c:\Users\Fatihh\OneDrive\Documents\BISMILLAH SKRIPSI\Fullstack WEB AVATA (AntiGravity)\Backend---Skripsi-"
docker-compose up -d
```

**2. Cek Status Container**:
```bash
docker-compose ps
```

**3. Akses Database via psql**:
```bash
docker exec -it tsunami_db psql -U tsunami_user -d tsunami_db
```

**4. Jalankan Setup Script** (jika perlu reset):
```bash
docker exec -i tsunami_db psql -U postgres < database_setup.sql
```

### Akses Database via pgAdmin

1. Buka browser: `http://localhost:5050`
2. Login:
   - Email: `admin@avatar.com`
   - Password: `admin`
3. Add New Server:
   - Name: `AVATAR Tsunami DB`
   - Host: `db` (jika pgAdmin di Docker) atau `localhost`
   - Port: `5432`
   - Database: `tsunami_db`
   - Username: `tsunami_user`
   - Password: `tsunami_password`

---

## Query Contoh

### Simulasi

**Insert Simulasi Baru**:
```sql
INSERT INTO simulations (
    magnitude, depth, latitude, longitude, 
    epicenter, prediction_data, 
    processing_time_ms, model_version
)
VALUES (
    7.5, 10.0, -6.102, 105.423,
    ST_SetSRID(ST_MakePoint(105.423, -6.102), 4326),
    '{"tsunamiCategory": "Bahaya", "waveHeight": 5.2, "arrivalTime": 15}',
    1250, 'v1.0.0'
);
```

**Ambil 10 Simulasi Terakhir**:
```sql
SELECT 
    id, 
    magnitude, 
    depth,
    prediction_data->>'tsunamiCategory' as kategori_tsunami,
    prediction_data->>'waveHeight' as tinggi_gelombang,
    created_at
FROM simulations
ORDER BY created_at DESC
LIMIT 10;
```

**Cari Simulasi dengan Magnitudo > 7.0**:
```sql
SELECT 
    magnitude,
    depth,
    ST_AsText(epicenter) as lokasi,
    prediction_data
FROM simulations
WHERE magnitude > 7.0
ORDER BY magnitude DESC;
```

---

### Gempa

**Insert Data Gempa dari BMKG**:
```sql
INSERT INTO earthquakes (
    id, magnitude, depth, latitude, longitude,
    location, location_name, timestamp, source,
    tsunami_potential, tsunami_risk_level
)
VALUES (
    'BMKG-20260203-001',
    6.8, 15.0, -6.5, 105.2,
    ST_SetSRID(ST_MakePoint(105.2, -6.5), 4326),
    '50 km Barat Daya Pandeglang',
    '2026-02-03 14:30:00',
    'BMKG',
    TRUE,
    'Sedang'
);
```

**Cari Gempa Berpotensi Tsunami dalam 24 Jam Terakhir**:
```sql
SELECT 
    id,
    magnitude,
    location_name,
    timestamp,
    tsunami_risk_level,
    source
FROM earthquakes
WHERE tsunami_potential = TRUE
    AND timestamp > NOW() - INTERVAL '24 hours'
ORDER BY timestamp DESC;
```

**Hitung Jarak Gempa dari Titik Tertentu**:
```sql
SELECT 
    id,
    magnitude,
    location_name,
    calculate_distance(
        -6.0833, 105.8833,  -- Koordinat Anyer
        latitude, longitude
    ) as jarak_km
FROM earthquakes
WHERE magnitude > 6.0
ORDER BY jarak_km ASC;
```

---

### Zona Genangan

**Insert Zona Genangan**:
```sql
INSERT INTO inundation_zones (
    simulation_id, geometry, wave_height, arrival_time,
    area_sqkm, affected_population
)
VALUES (
    'your-simulation-id-here',
    ST_GeomFromText(
        'POLYGON((105.8 -6.1, 105.9 -6.1, 105.9 -6.0, 105.8 -6.0, 105.8 -6.1))',
        4326
    ),
    3.5,  -- tinggi gelombang 3.5 meter
    20,   -- tiba dalam 20 menit
    15.5, -- luas 15.5 km²
    5000  -- 5000 penduduk terdampak
);
```

**Cari Area Terdampak Tsunami**:
```sql
SELECT 
    s.magnitude,
    s.created_at,
    iz.wave_height,
    iz.arrival_time,
    iz.area_sqkm,
    iz.affected_population,
    ST_AsGeoJSON(iz.geometry) as area_geojson
FROM inundation_zones iz
JOIN simulations s ON iz.simulation_id = s.id
WHERE iz.wave_height > 3.0
ORDER BY s.created_at DESC;
```

---

### Garis Pantai

**Insert Garis Pantai Baru**:
```sql
INSERT INTO coastlines (name, geometry, region, length_km)
VALUES (
    'Pantai Kuta',
    ST_GeomFromText(
        'LINESTRING(115.1695 -8.7181, 115.1720 -8.7150, 115.1750 -8.7120)',
        4326
    ),
    'Bali',
    3.2
);
```

**Cari Garis Pantai Terdekat dari Suatu Titik**:
```sql
SELECT 
    name,
    region,
    length_km,
    ST_Distance(
        geometry::geography,
        ST_SetSRID(ST_MakePoint(105.8833, -6.0833), 4326)::geography
    ) / 1000.0 as jarak_km
FROM coastlines
ORDER BY jarak_km ASC
LIMIT 5;
```

---

### Query Geospatial Advanced

**Cari Pantai yang Terpengaruh oleh Zona Genangan** (dalam radius 10 km):
```sql
SELECT DISTINCT
    c.name as nama_pantai,
    c.region,
    s.magnitude,
    iz.wave_height,
    ST_Distance(
        c.geometry::geography,
        iz.geometry::geography
    ) / 1000.0 as jarak_km
FROM coastlines c
CROSS JOIN inundation_zones iz
INNER JOIN simulations s ON iz.simulation_id = s.id
WHERE ST_DWithin(
    c.geometry::geography,
    iz.geometry::geography,
    10000  -- 10 km dalam meter
)
ORDER BY jarak_km ASC;
```

**Analisis Risiko Tsunami per Wilayah**:
```sql
SELECT 
    region,
    COUNT(*) as jumlah_pantai,
    SUM(length_km) as total_panjang_pantai_km,
    (
        SELECT COUNT(*)
        FROM earthquakes e
        WHERE e.tsunami_potential = TRUE
            AND ST_DWithin(
                e.location::geography,
                c.geometry::geography,
                50000  -- dalam radius 50 km
            )
    ) as jumlah_gempa_berisiko
FROM coastlines c
GROUP BY region
ORDER BY jumlah_gempa_berisiko DESC;
```

---

## 🔒 Security & Best Practices

### Production Checklist:

- [ ] **Ganti password default** di `.env` dan `docker-compose.yml`
- [ ] **Gunakan SSL/TLS** untuk koneksi database
- [ ] **Buat user dengan privilege terbatas** (jangan gunakan `postgres`)
- [ ] **Enable connection pooling** untuk performa
- [ ] **Setup backup otomatis** (pg_dump)
- [ ] **Monitor resource usage** (disk space, memory)
- [ ] **Review dan optimize index** sesuai query pattern
- [ ] **Enable query logging** untuk debugging
- [ ] **Setup replica** untuk high availability

### Backup Database:
```bash
# Backup
docker exec tsunami_db pg_dump -U tsunami_user tsunami_db > backup_$(date +%Y%m%d).sql

# Restore
docker exec -i tsunami_db psql -U tsunami_user tsunami_db < backup_20260203.sql
```

---

## 📞 Troubleshooting

### Database tidak bisa connect:

1. Cek container running: `docker-compose ps`
2. Cek logs: `docker-compose logs db`
3. Cek port: `netstat -ano | findstr :5432`
4. Restart container: `docker-compose restart db`

### PostGIS tidak aktif:

```sql
-- Cek extension
SELECT * FROM pg_extension WHERE extname = 'postgis';

-- Install jika belum ada
CREATE EXTENSION IF NOT EXISTS postgis;
```

### Performance lambat:

```sql
-- Analyze tables
ANALYZE simulations;
ANALYZE earthquakes;
ANALYZE inundation_zones;
ANALYZE coastlines;

-- Vacuum database
VACUUM ANALYZE;
```

---

## 📚 Referensi

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [PostGIS Documentation](https://postgis.net/documentation/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [GeoJSON Format](https://geojson.org/)

---

**Happy Coding! 🌊**

*Dokumentasi ini dibuat untuk AVATAR - Advanced Virtual Assistant for Tsunami Awareness*
