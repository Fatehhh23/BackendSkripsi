# download_dem.py — jalankan sekali saja
import elevation
import os

os.makedirs("data/dem", exist_ok=True)

# Download SRTM untuk daratan Selat Sunda
elevation.clip(
    bounds=(104.5, -7.0, 106.5, -5.0),  # batas Selat Sunda
    output="data/dem/DEM_TopoBathy_Selat_Sunda_30m.tif",
    product="SRTM1"  # resolusi 30m
)
elevation.clean()
print("DEM berhasil didownload!")
