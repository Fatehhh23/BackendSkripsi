# Panduan Menjalankan AVATAR (Frontend & Backend)

Dokumen ini menjelaskan cara menjalankan aplikasi secara efisien tanpa perlu melakukan *rebuild* (membangun ulang) setiap saat.

## Prinsip Dasar: "Build Sekali, Jalankan Berkali-kali"

Aplikasi Backend menggunakan Docker. Docker bekerja dengan sistem **Image** (cetakan) dan **Container** (wadah yang berjalan).
- **Build**: Membuat *Image* dari kode sumber. Ini butuh waktu lama (download library, install dependency).
- **Run**: Menjalankan *Container* dari *Image* yang sudah jadi. Ini sangat cepat (hitungan detik).

---

## 1. Menjalankan Aplikasi (Cara Cepat/Normal)

Gunakan cara ini untuk penggunaan sehari-hari jika Anda **tidak mengubah** library tambahan di `requirements.txt`.

### 🔥 Cara Paling Mudah (Otomatis)
Cukup jalankan file:
👉 **`start_avatar.bat`**

Script ini otomatis menjalankan perintah:
- Backend: `docker-compose up -d` (Hanya menjalankan, tidak build ulang)
- Frontend: `npm run dev` (Server development super cepat)

### 💻 Cara Manual (Lewat Terminal)

**Backend:**
```bash
cd "Backend---Skripsi-"
docker-compose up -d
```
*Catatan: Perintah `up` otomatis mengecek apakah image sudah ada. Jika sudah ada, dia langsung pakai yang itu.*

**Frontend:**
```bash
cd "Frontend-Skripsi-"
npm run dev
```

---

## 2. Kapan Harus Build Ulang?

Anda HANYA perlu melakukan build ulang jika:
1.  Menambahkan library baru di `requirements.txt`.
2.  Mengubah konfigurasi di `Dockerfile`.
3.  Ada error "Module not found" padahal codingan sudah benar.

**Cara Build Ulang (Jika Perlu Saja):**
```bash
cd "Backend---Skripsi-"
docker-compose up -d --build
```
*Tanda `--build` memaksa Docker untuk membuat ulang image dari awal.*

---

## 📠 Ringkasan
| Tujuan | Perintah | Kecepatan |
| :--- | :--- | :--- |
| **Menjalankan Biasa** | `docker-compose up -d` | ⚡ Cepat (< 5 detik) |
| **Update Library/Code** | `docker-compose up -d --build` | 🐢 Lambat (Terghantung koneksi) |
| **Restart (Tanpa Build)** | `docker-compose restart` | ⚡ Cepat |

Jadi, untuk selanjutnya, **cukup gunakan `start_avatar.bat`** atau `docker-compose up -d`. Tidak perlu `--build` lagi.
