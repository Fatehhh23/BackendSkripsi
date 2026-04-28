import os
import gzip
import urllib.request
import rasterio
from rasterio.merge import merge
import numpy as np

os.makedirs('data/dem', exist_ok=True)
os.makedirs('data/temp_dem', exist_ok=True)

# Batas koordinat Selat Sunda
# (104.5, -7.0, 106.5, -5.0) -> S07 to S05, E104 to E106

tiles = [
    'S07/S07E104', 'S06/S06E104', 'S05/S05E104',
    'S07/S07E105', 'S06/S06E105', 'S05/S05E105',
    'S07/S07E106', 'S06/S06E106', 'S05/S05E106'
]

base_url = "https://s3.amazonaws.com/elevation-tiles-prod/skadi"
hgt_files = []

print("Mulai mendownload data DEM secara langsung...")
for tile in tiles:
    url = f"{base_url}/{tile}.hgt.gz"
    gz_path = f"data/temp_dem/{tile.replace('/', '_')}.hgt.gz"
    hgt_path = f"data/temp_dem/{tile.replace('/', '_')}.hgt"
    
    if not os.path.exists(hgt_path):
        print(f"Downloading {url}...")
        try:
            urllib.request.urlretrieve(url, gz_path)
            # Decompress
            with gzip.open(gz_path, 'rb') as f_in:
                with open(hgt_path, 'wb') as f_out:
                    f_out.write(f_in.read())
            os.remove(gz_path)
        except Exception as e:
            print(f"Gagal mendownload {tile}: {e}")
            continue
            
    if os.path.exists(hgt_path):
        # Kita perlu membuat dummy VRT atau menggunakan Rasterio untuk membacanya
        # HGT format didukung secara native oleh GDAL
        hgt_files.append(hgt_path)

if not hgt_files:
    print("Gagal mendownload semua tile.")
    exit(1)

print("Menggabungkan tile DEM...")
# Merge dengan Rasterio
src_files_to_mosaic = []
for fp in hgt_files:
    src = rasterio.open(fp)
    src_files_to_mosaic.append(src)

mosaic, out_trans = merge(src_files_to_mosaic)

# Crop sesuai bounding box (approximate)
# bounds=(104.5, -7.0, 106.5, -5.0)
min_lon, min_lat, max_lon, max_lat = 104.5, -7.0, 106.5, -5.0

# Cari index pixel
# VRT/Affine: (lon = trans[2] + col*trans[0], lat = trans[5] + row*trans[4])
# col = (lon - trans[2]) / trans[0]
# row = (lat - trans[5]) / trans[4]

col_min = int((min_lon - out_trans[2]) / out_trans[0])
col_max = int((max_lon - out_trans[2]) / out_trans[0])
# out_trans[4] is negative
row_min = int((max_lat - out_trans[5]) / out_trans[4])
row_max = int((min_lat - out_trans[5]) / out_trans[4])

# Pastikan di dalam batas array
col_min = max(0, col_min)
row_min = max(0, row_min)
col_max = min(mosaic.shape[2], col_max)
row_max = min(mosaic.shape[1], row_max)

cropped_mosaic = mosaic[:, row_min:row_max, col_min:col_max]

out_meta = src.meta.copy()
out_meta.update({
    "driver": "GTiff",
    "height": cropped_mosaic.shape[1],
    "width": cropped_mosaic.shape[2],
    "transform": rasterio.Affine(out_trans[0], out_trans[1], out_trans[2] + col_min*out_trans[0],
                                 out_trans[3], out_trans[4], out_trans[5] + row_min*out_trans[4])
})

out_path = "data/dem/DEM_TopoBathy_Selat_Sunda_30m.tif"
with rasterio.open(out_path, "w", **out_meta) as dest:
    dest.write(cropped_mosaic)

print(f"Selesai! DEM disimpan di {out_path}")

# Cleanup
for src in src_files_to_mosaic:
    src.close()
for fp in hgt_files:
    os.remove(fp)
os.rmdir("data/temp_dem")
