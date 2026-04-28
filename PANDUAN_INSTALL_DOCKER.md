# 🐳 Panduan Lengkap Instalasi Docker Desktop di Windows

## 📋 Daftar Isi
1. [Persyaratan Sistem](#persyaratan-sistem)
2. [Download Docker Desktop](#download-docker-desktop)
3. [Instalasi Docker Desktop](#instalasi-docker-desktop)
4. [Konfigurasi Awal](#konfigurasi-awal)
5. [Verifikasi Instalasi](#verifikasi-instalasi)
6. [Setup Database AVATAR](#setup-database-avatar)
7. [Troubleshooting](#troubleshooting)

---

## 📌 Persyaratan Sistem

### Minimum Requirements:
- ✅ **Windows 10/11** (64-bit)
- ✅ **RAM**: Minimal 4GB (Recommended 8GB+)
- ✅ **Disk Space**: Minimal 5GB free space
- ✅ **Virtualization**: Harus diaktifkan di BIOS

### Cek Virtualization Enabled:

**Cara 1 - Via Task Manager:**
1. Tekan `Ctrl + Shift + Esc` untuk buka Task Manager
2. Klik tab **Performance**
3. Klik **CPU**
4. Lihat bagian **Virtualization** - harus menunjukkan **Enabled**

**Cara 2 - Via PowerShell:**
```powershell
# Jalankan sebagai Administrator
Get-ComputerInfo | Select-Object HyperVRequirementVirtualizationFirmwareEnabled
```

### Jika Virtualization Disabled:

> ⚠️ **PENTING**: Jika Virtualization disabled, Anda harus masuk ke BIOS dan mengaktifkannya.

**Langkah Masuk BIOS:**
1. Restart komputer
2. Tekan tombol BIOS key (biasanya `F2`, `F10`, `Del`, atau `Esc`) saat boot
3. Cari menu **Advanced** atau **CPU Configuration**
4. Cari opsi **Intel VT-x** atau **AMD-V** atau **Virtualization Technology**
5. Set ke **Enabled**
6. Save & Exit (biasanya `F10`)

---

## 📥 Download Docker Desktop

### Metode 1: Download Langsung

1. **Buka Browser** dan kunjungi:
   ```
   https://www.docker.com/products/docker-desktop/
   ```

2. **Klik tombol "Download for Windows"**
   - File yang didownload: `Docker Desktop Installer.exe`
   - Size: ~500-600 MB
   - Lokasi default download: `C:\Users\Fatihh\Downloads\`

### Metode 2: Download via PowerShell (Optional)

```powershell
# Jalankan di PowerShell
$url = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
$output = "$env:USERPROFILE\Downloads\DockerDesktopInstaller.exe"
Invoke-WebRequest -Uri $url -OutFile $output
```

### Verify Download:
```powershell
# Cek file sudah terdownload
Get-ChildItem "$env:USERPROFILE\Downloads\DockerDesktopInstaller.exe"
```

---

## 🚀 Instalasi Docker Desktop

### Step-by-Step Installation:

#### Step 1: Jalankan Installer

1. **Buka File Explorer**
2. Navigate ke **Downloads** folder
3. **Double-click** file `Docker Desktop Installer.exe`
4. Jika muncul **User Account Control**, klik **Yes**

#### Step 2: Configuration Options

Saat installer muncul, Anda akan melihat 2 options:

```
☑ Use WSL 2 instead of Hyper-V (recommended)
☑ Add shortcut to desktop
```

**Rekomendasi Setting:**
- ✅ **CENTANG** "Use WSL 2 instead of Hyper-V" (lebih ringan dan cepat)
- ✅ **CENTANG** "Add shortcut to desktop" (untuk kemudahan akses)

Klik **OK** untuk lanjut.

#### Step 3: Proses Instalasi

- Installer akan mulai extract dan install files
- Proses ini memakan waktu **5-10 menit** tergantung kecepatan PC
- Progress bar akan menunjukkan status instalasi

**Yang Akan Diinstall:**
- Docker Engine
- Docker CLI
- Docker Compose
- Docker Content Trust
- Kubernetes (optional)

#### Step 4: Restart Required

Setelah instalasi selesai, Anda akan melihat pesan:
```
Installation succeeded
You need to restart your computer to complete the installation.
```

**Klik "Close and restart"** atau restart manual.

---

## ⚙️ Konfigurasi Awal

### Step 1: Pertama Kali Buka Docker Desktop

Setelah restart:

1. **Buka Docker Desktop** dari Desktop shortcut atau Start Menu
2. Docker akan melakukan **initialization** (tunggu 2-3 menit)
3. Mungkin muncul **Docker Subscription Service Agreement**
   - Baca dan klik **Accept** (untuk personal use, free)

### Step 2: Sign In (Optional)

- Docker akan minta login/create account
- Ini **OPTIONAL** untuk penggunaan lokal
- Klik **Continue without signing in** jika tidak ingin create account

### Step 3: Tutorial (Optional)

- Docker mungkin menawarkan tutorial
- Klik **Skip tutorial** jika ingin langsung menggunakan

### Step 4: Cek Docker Running

Di system tray (pojok kanan bawah), Anda akan melihat:
- 🐳 **Docker icon**
- Status: **Docker Desktop is running**

---

## ✅ Verifikasi Instalasi

### Buka PowerShell dan Jalankan:

```powershell
# 1. Cek versi Docker
docker --version
# Expected output: Docker version 24.x.x, build xxxxx

# 2. Cek Docker Compose
docker compose version
# Expected output: Docker Compose version v2.x.x

# 3. Test Docker dengan container sederhana
docker run hello-world
```

### Expected Output untuk `docker run hello-world`:

```
Unable to find image 'hello-world:latest' locally
latest: Pulling from library/hello-world
...
Hello from Docker!
This message shows that your installation appears to be working correctly.
```

✅ **Jika muncul pesan di atas, Docker berhasil terinstall!**

---

## 🎯 Setup Database AVATAR

Sekarang Docker sudah ready, mari setup database untuk project AVATAR!

### Step 1: Navigate ke Folder Backend

```powershell
cd "C:\Users\Fatihh\OneDrive\Documents\BISMILLAH SKRIPSI\Fullstack WEB AVATA (AntiGravity)\Backend---Skripsi-"
```

### Step 2: Verify Files

```powershell
# Cek apakah docker-compose.yml ada
ls docker-compose.yml

# Cek apakah .env ada
ls .env
```

### Step 3: Pull Docker Images

```powershell
# Download images yang dibutuhkan (first time only)
docker compose pull
```

Ini akan download:
- ✅ `postgis/postgis:15-3.3` (~200 MB) - PostgreSQL + PostGIS
- ✅ `dpage/pgadmin4:latest` (~100 MB) - pgAdmin GUI

**Estimasi waktu**: 5-10 menit tergantung koneksi internet

### Step 4: Start Containers

```powershell
# Start semua services (database, backend, pgAdmin)
docker compose up -d
```

**Penjelasan Flag:**
- `up`: Start containers
- `-d`: Detached mode (berjalan di background)

### Step 5: Cek Status Containers

```powershell
docker compose ps
```

**Expected Output:**
```
NAME               IMAGE                    STATUS         PORTS
tsunami_backend    backend-skripsi-backend  Up 2 minutes   0.0.0.0:8000->8000/tcp
tsunami_db         postgis/postgis:15-3.3   Up 2 minutes   0.0.0.0:5432->5432/tcp
tsunami_pgadmin    dpage/pgadmin4:latest    Up 2 minutes   0.0.0.0:5050->80/tcp
```

✅ Semua status harus **Up**

### Step 6: Cek Logs (Optional)

```powershell
# Cek logs database
docker compose logs db

# Cek logs backend
docker compose logs backend

# Follow logs real-time
docker compose logs -f
```

---

## 🌐 Akses Services

### 1. **Backend API**
- URL: http://localhost:8000
- Docs: http://localhost:8000/docs (Swagger UI)
- ReDoc: http://localhost:8000/redoc

### 2. **pgAdmin** (Database Management GUI)
- URL: http://localhost:5050
- Email: `admin@avatar.com`
- Password: `admin`

**Setup Server di pgAdmin:**
1. Buka http://localhost:5050 dan login
2. Klik kanan **Servers** → **Register** → **Server**
3. Tab **General**:
   - Name: `AVATAR Tsunami DB`
4. Tab **Connection**:
   - Host: `db`
   - Port: `5432`
   - Database: `tsunami_db`
   - Username: `tsunami_user`
   - Password: `tsunami_password`
5. Klik **Save**

### 3. **Direct Database Access**

```powershell
# Connect via docker exec
docker exec -it tsunami_db psql -U tsunami_user -d tsunami_db
```

Di dalam psql:
```sql
-- Cek tabel yang ada
\dt

-- Cek PostGIS version
SELECT PostGIS_Version();

-- Lihat data coastlines
SELECT * FROM coastlines;

-- Exit
\q
```

---

## 🛠️ Perintah Docker Berguna

### Container Management:

```powershell
# Start semua containers
docker compose up -d

# Stop semua containers
docker compose down

# Restart semua containers
docker compose restart

# Stop dan hapus containers + volumes (HATI-HATI: data hilang!)
docker compose down -v

# Rebuild containers (jika ada perubahan Dockerfile)
docker compose up -d --build
```

### Monitoring:

```powershell
# Lihat status containers
docker compose ps

# Lihat logs
docker compose logs

# Follow logs real-time
docker compose logs -f

# Logs untuk service tertentu
docker compose logs db
docker compose logs backend

# Lihat resource usage
docker stats
```

### Database Management:

```powershell
# Backup database
docker exec tsunami_db pg_dump -U tsunami_user tsunami_db > backup.sql

# Restore database
docker exec -i tsunami_db psql -U tsunami_user tsunami_db < backup.sql

# Connect to database
docker exec -it tsunami_db psql -U tsunami_user -d tsunami_db

# Execute SQL file
docker exec -i tsunami_db psql -U tsunami_user -d tsunami_db < database_setup.sql
```

### Clean Up:

```powershell
# Hapus semua unused containers
docker container prune

# Hapus semua unused images
docker image prune

# Hapus semua unused volumes
docker volume prune

# Hapus SEMUA unused resources
docker system prune -a
```

---

## 🔧 Troubleshooting

### Problem 1: "Docker daemon is not running"

**Solusi:**
1. Buka **Docker Desktop** dari Start Menu
2. Tunggu sampai icon di system tray menunjukkan "Running"
3. Retry command

### Problem 2: Port Already in Use

**Error:**
```
Error: bind: address already in use
```

**Penyebab:**
- Port 5432 (PostgreSQL) atau 8000 (Backend) sudah dipakai

**Solusi:**
```powershell
# Cek process yang pakai port 5432
netstat -ano | findstr :5432

# Kill process (ganti PID dengan angka dari output di atas)
taskkill /PID <PID> /F

# Atau edit docker-compose.yml untuk ganti port:
# ports:
#   - "5433:5432"  # Ganti 5432 menjadi 5433
```

### Problem 3: WSL 2 Not Installed

**Error:**
```
WSL 2 installation is incomplete
```

**Solusi:**
1. Buka PowerShell sebagai **Administrator**
2. Jalankan:
```powershell
wsl --install
```
3. Restart komputer
4. Buka Docker Desktop lagi

### Problem 4: Virtualization Not Enabled

**Error:**
```
Hardware assisted virtualization and data execution protection must be enabled in the BIOS
```

**Solusi:**
- Ikuti panduan di bagian [Persyaratan Sistem](#persyaratan-sistem)
- Aktifkan Virtualization di BIOS

### Problem 5: Container Tidak Start

**Solusi:**
```powershell
# Stop semua containers
docker compose down

# Remove volumes
docker compose down -v

# Pull images lagi
docker compose pull

# Start fresh
docker compose up -d

# Cek logs untuk error detail
docker compose logs
```

### Problem 6: Database Connection Failed

**Cek:**
1. Container database running:
   ```powershell
   docker compose ps db
   ```

2. Health check:
   ```powershell
   docker exec tsunami_db pg_isready -U tsunami_user
   ```

3. Cek .env file:
   - URL harus: `postgresql://tsunami_user:tsunami_password@db:5432/tsunami_db`

### Problem 7: Disk Space Full

**Cek disk usage:**
```powershell
docker system df
```

**Clean up:**
```powershell
# Hapus unused data
docker system prune -a --volumes

# Konfirmasi dengan 'y'
```

---

## 📚 Resources & Next Steps

### Official Documentation:
- [Docker Desktop Docs](https://docs.docker.com/desktop/)
- [Docker Compose Docs](https://docs.docker.com/compose/)
- [PostgreSQL Docker Hub](https://hub.docker.com/_/postgres)
- [PostGIS Docker Hub](https://hub.docker.com/r/postgis/postgis)

### Next Steps After Installation:

1. ✅ **Test Backend API**
   - Buka http://localhost:8000/docs
   - Test endpoint `/api/health` atau similar

2. ✅ **Explore Database via pgAdmin**
   - Buka http://localhost:5050
   - Connect ke database
   - Lihat struktur tabel

3. ✅ **Run Migrations** (jika ada)
   ```powershell
   docker compose exec backend alembic upgrade head
   ```

4. ✅ **Test Simulation**
   - Gunakan frontend untuk submit simulasi
   - Cek data tersimpan di database

5. ✅ **Setup Monitoring**
   - Monitor container health
   - Setup backup schedule untuk database

---

## 🎓 Tips & Best Practices

### Development:

1. **Gunakan Docker Compose** untuk manage multi-container apps
2. **Mount volumes** untuk development (hot reload)
3. **Use .env files** untuk manage environment variables
4. **Name containers** dengan jelas untuk mudah identify

### Production:

1. **Ganti default passwords** di docker-compose.yml dan .env
2. **Limit resources** (CPU, memory) per container
3. **Use secrets** untuk sensitive data
4. **Setup backup automation** untuk database
5. **Monitor logs** dan setup alerts

### Performance:

1. **WSL 2 backend** lebih cepat daripada Hyper-V
2. **Allocate enough resources** di Docker Desktop Settings
3. **Use multi-stage builds** untuk optimize image size
4. **Clean up unused resources** secara berkala

---

## ✅ Checklist Instalasi

Gunakan checklist ini untuk memastikan semua sudah setup dengan benar:

- [ ] Virtualization enabled di BIOS
- [ ] Docker Desktop terinstall
- [ ] Docker Desktop running (icon di system tray)
- [ ] `docker --version` menampilkan versi
- [ ] `docker compose version` menampilkan versi
- [ ] `docker run hello-world` berhasil
- [ ] File `.env` sudah ada di folder backend
- [ ] `docker compose pull` berhasil download images
- [ ] `docker compose up -d` start containers tanpa error
- [ ] `docker compose ps` menunjukkan semua containers Up
- [ ] http://localhost:8000 accessible (backend API)
- [ ] http://localhost:5050 accessible (pgAdmin)
- [ ] pgAdmin bisa connect ke database
- [ ] Database `tsunami_db` memiliki tabel (simulations, earthquakes, dll)

---

## 🎉 Selamat!

Jika semua checklist di atas sudah ✅, maka Docker Desktop Anda sudah terinstall dengan benar dan database AVATAR sudah ready to use!

**Happy Coding! 🚀**

---

## 📞 Need Help?

Jika mengalami masalah:
1. Cek bagian **Troubleshooting** di atas
2. Lihat logs: `docker compose logs`
3. Restart Docker Desktop
4. Restart komputer

**Common Commands Reference:**
```powershell
# Start
docker compose up -d

# Stop
docker compose down

# Logs
docker compose logs -f

# Restart
docker compose restart

# Status
docker compose ps
```

---

*Dokumentasi ini dibuat untuk project AVATAR - Advanced Virtual Assistant for Tsunami Awareness*

*Last updated: 2026-02-04*
