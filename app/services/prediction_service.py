import logging
import math
import time
import os
from typing import Dict, Any, List, Optional
import numpy as np
import torch

from app.config import settings
from app.services.model_architecture import PIResNet50, PIMMViT

logger = logging.getLogger(__name__)


class PredictionService:
    """
    Service untuk menjalankan prediksi tsunami menggunakan ensemble
    2 model PyTorch: PI-ResNet50 dan PI-MMViT.

    Kedua model dijalankan secara paralel dan hasilnya di-rata-rata
    (ensemble averaging) untuk prediksi yang lebih robust.

    Arsitektur:
      - PI-ResNet50: ResNet-50 encoder + FiLM fusion + U-Net decoder
      - PI-MMViT: CNN stem + ViT bottleneck + U-Net decoder
      - Ensemble: rata-rata depth output dari kedua model
    """

    # Bounding box geografis Selat Sunda yang di-map ke grid 256x256
    GEO_BOUNDS = {
        "min_lon": 104.5, "max_lon": 106.5,
        "min_lat": -7.0,  "max_lat": -5.0,
    }

    def __init__(self):
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() and settings.USE_GPU else "cpu"
        )
        self.model_resnet: Optional[PIResNet50] = None
        self.model_mmvit: Optional[PIMMViT] = None
        self.model_resnet_loaded = False
        self.model_mmvit_loaded = False
        self.model_loaded = False   # True jika minimal 1 model berhasil di-load
        self._last_crop_bounds = self.GEO_BOUNDS

        # Batasan Normalisasi Fault (sama dengan training pipeline)
        self.fault_bounds = {
            'mw':     (7.0, 9.2),
            'lon0':   (103.0, 108.0),
            'lat0':   (-9.0, -4.5),
            'depth':  (5.0, 55.0),
            'strike': (260.0, 330.0),
            'dip':    (5.0, 40.0),
            'rake':   (70.0, 115.0),
            'length': (10.0, 600.0),
            'width':  (5.0, 250.0),
        }

        # Pre-compute lon/lat grids (256x256) sekali saja
        b = self.GEO_BOUNDS
        self._lon_grid, self._lat_grid = np.meshgrid(
            np.linspace(b["min_lon"], b["max_lon"], 256),
            np.linspace(b["max_lat"], b["min_lat"], 256),   # lat turun (north→south)
            indexing='xy',
        )
        # Luas per pixel dalam km² (approx)
        # Pixel area untuk DEM 30m: 30m * 30m = 900 m2 = 0.0009 km2
        self._pixel_area_km2 = (30 / 1000) * (30 / 1000)

        self._load_model()
        self._load_dem_raster()

    # ──────────────────────────────────────────────
    # MODEL LOADING
    # ──────────────────────────────────────────────
    def _load_model(self):
        """Load kedua model: PI-ResNet50 dan PI-MMViT."""
        # ── 1. Load PI-ResNet50 ────────────────────────────────────
        try:
            self.model_resnet = PIResNet50(
                in_channels=10, fault_dim=9, num_classes=3,
                pretrained=False,
            ).to(self.device)

            if os.path.exists(settings.MODEL_RESNET_PATH):
                cp = torch.load(
                    settings.MODEL_RESNET_PATH,
                    map_location=self.device,
                    weights_only=False,
                )
                if isinstance(cp, dict) and "model_state" in cp:
                    self.model_resnet.load_state_dict(cp["model_state"])
                else:
                    self.model_resnet.load_state_dict(cp)
                self.model_resnet.eval()
                self.model_resnet_loaded = True
                logger.info(
                    f"\u2705 PI-ResNet50 loaded "
                    f"(epoch {cp.get('epoch', '?')}, MAE {cp.get('mae', '?')})"
                )
            else:
                logger.warning(f"\u26a0\ufe0f PI-ResNet50 weights not found: {settings.MODEL_RESNET_PATH}")
        except Exception as e:
            logger.error(f"\u274c Gagal load PI-ResNet50: {e}", exc_info=True)

        # ── 2. Load PI-MMViT ──────────────────────────────────────
        try:
            self.model_mmvit = PIMMViT(
                dem_channels=10, fault_dim=9, num_classes=3,
            ).to(self.device)

            if os.path.exists(settings.MODEL_MMVIT_PATH):
                cp = torch.load(
                    settings.MODEL_MMVIT_PATH,
                    map_location=self.device,
                    weights_only=False,
                )
                if isinstance(cp, dict) and "model_state" in cp:
                    self.model_mmvit.load_state_dict(cp["model_state"])
                else:
                    self.model_mmvit.load_state_dict(cp)
                self.model_mmvit.eval()
                self.model_mmvit_loaded = True
                logger.info(
                    f"\u2705 PI-MMViT loaded "
                    f"(epoch {cp.get('epoch', '?')}, "
                    f"MAE_flood {cp.get('mae_flood', '?')})"
                )
            else:
                logger.warning(f"\u26a0\ufe0f PI-MMViT weights not found: {settings.MODEL_MMVIT_PATH}")
        except Exception as e:
            logger.error(f"\u274c Gagal load PI-MMViT: {e}", exc_info=True)

        # ── Status ────────────────────────────────────────────────
        self.model_loaded = self.model_resnet_loaded or self.model_mmvit_loaded
        loaded = []
        if self.model_resnet_loaded: loaded.append("PI-ResNet50")
        if self.model_mmvit_loaded:  loaded.append("PI-MMViT")
        if loaded:
            logger.info(f"\u2705 Ensemble ready: {' + '.join(loaded)}")
        else:
            logger.warning("\u26a0\ufe0f Tidak ada model yang berhasil di-load. Heuristic-only mode.")

    # ──────────────────────────────────────────────
    # DEM ASLI (10-CHANNEL DARI GEOTIFF)
    # ──────────────────────────────────────────────
    def _load_dem_raster(self):
        """Load DEM GeoTIFF sekali saat startup dan cache di memori."""
        self._dem_data = None
        self._dem_transform = None
        self._dem_bounds = None
        self._dem_shape = None

        dem_path = settings.DEM_GEOTIFF_PATH
        if not os.path.exists(dem_path):
            logger.warning(f"DEM file not found: {dem_path}. Fallback ke sintetis.")
            return

        try:
            import rasterio
            with rasterio.open(dem_path) as ds:
                self._dem_data = ds.read(1).astype(np.float32)  # (H, W)
                self._dem_transform = ds.transform
                self._dem_bounds = ds.bounds  # BoundingBox(left, bottom, right, top)
                self._dem_shape = self._dem_data.shape
                self._dem_nodata = ds.nodata

            # Replace nodata dengan 0
            if self._dem_nodata is not None:
                mask = np.isinf(self._dem_data) | np.isnan(self._dem_data)
                self._dem_data[mask] = 0.0

            logger.info(
                f"DEM loaded: {self._dem_shape}, "
                f"bounds=({self._dem_bounds.left:.2f}, {self._dem_bounds.bottom:.2f}) - "
                f"({self._dem_bounds.right:.2f}, {self._dem_bounds.top:.2f}), "
                f"range=[{self._dem_data.min():.1f}, {self._dem_data.max():.1f}]m"
            )
        except Exception as e:
            logger.error(f"Gagal load DEM GeoTIFF: {e}", exc_info=True)
            self._dem_data = None

    def _crop_dem_at_epicenter(self, lat: float, lon: float, size: int = 256) -> np.ndarray:
        """
        Crop region size×size dari DEM asli, atau buat DEM sintetis jika
        file GeoTIFF tidak tersedia.
        """
        if self._dem_data is not None:
            b  = self._dem_bounds
            H, W = self._dem_shape
            col_per_deg = W / (b.right - b.left)
            row_per_deg = H / (b.top  - b.bottom)
            center_col  = int((lon - b.left) * col_per_deg)
            center_row  = int((b.top - lat)  * row_per_deg)
            half = size // 2
            r0 = max(0, center_row - half)
            r1 = min(H, center_row + half)
            c0 = max(0, center_col - half)
            c1 = min(W, center_col + half)
            res_lon = (b.right - b.left) / W
            res_lat = (b.top  - b.bottom) / H
            self._last_crop_bounds = {
                "min_lon": b.left + c0 * res_lon,
                "max_lon": b.left + c1 * res_lon,
                "min_lat": b.top  - r1 * res_lat,
                "max_lat": b.top  - r0 * res_lat,
            }
            crop = self._dem_data[r0:r1, c0:c1].copy()
            if crop.shape != (size, size):
                padded = np.zeros((size, size), dtype=np.float32)
                ph = min(crop.shape[0], size)
                pw = min(crop.shape[1], size)
                padded[:ph, :pw] = crop[:ph, :pw]
                crop = padded
            return crop
        else:
            # DEM tidak ada → gunakan model sintetis berbasis geografi Selat Sunda
            return self._create_synthetic_dem_sunda(lat, lon, size)

    def _create_synthetic_dem_sunda(self, lat_center: float, lon_center: float, size: int = 256) -> np.ndarray:
        """
        DEM sintetis geografi-aware untuk Selat Sunda.
        Dipakai sebagai fallback ketika file GeoTIFF tidak tersedia.

        Model terrain sederhana namun realistis:
          - Selat (laut)    : elevasi negatif, lebih dalam di tengah
          - Pantai Banten   : dataran rendah 0-10m kemudian naik gradual
          - Pantai Lampung  : serupa tetapi lebih curam
          - Zona shallow    : 0-5m di sepanjang garis pantai

        Catatan: Anak Krakatau / pulau-pulau kecil tidak dimodelkan secara
        eksplisit tetapi akan muncul sebagai puncak positif dalam noise.
        """
        from scipy.ndimage import gaussian_filter

        half_deg = 0.45           # ~50 km radius
        lat_arr  = np.linspace(lat_center + half_deg, lat_center - half_deg, size)
        lon_arr  = np.linspace(lon_center - half_deg, lon_center + half_deg, size)
        lon_mesh, lat_mesh = np.meshgrid(lon_arr, lat_arr)

        # Garis pantai utama Selat Sunda (approximate)
        java_coast_lat    = -6.03    # pantai utara Jawa (Banten)
        sumatra_coast_lat = -5.55    # pantai selatan Sumatera (Lampung)
        strait_center_lat = (java_coast_lat + sumatra_coast_lat) / 2.0

        java_land    = lat_mesh <= java_coast_lat
        sumatra_land = lat_mesh >= sumatra_coast_lat
        in_strait    = ~java_land & ~sumatra_land

        dist_java     = np.abs(lat_mesh - java_coast_lat)
        dist_sumatra  = np.abs(lat_mesh - sumatra_coast_lat)
        dist_nearest  = np.minimum(dist_java, dist_sumatra)

        elev = np.zeros((size, size), dtype=np.float32)

        # Laut / Selat — makin ke tengah makin dalam
        strait_hw = abs(java_coast_lat - sumatra_coast_lat) / 2.0
        rel_pos   = np.abs(lat_mesh - strait_center_lat) / max(strait_hw, 0.01)
        sea_depth = -160.0 * np.sqrt(np.clip(1.0 - rel_pos, 0, 1))
        elev[in_strait] = sea_depth[in_strait]

        # Zona dangkal (<1 km dari pantai) → -5 s/d 0 m
        shallow = (dist_nearest < 0.010) & in_strait
        t = dist_nearest[shallow] / 0.010        # 0 di pantai, 1 di batas zona
        elev[shallow] = -5.0 * t

        # Dataran Jawa/Banten: naik dari 0 di pantai → plateau ~50 m
        # Zona 0-3 km: rata-rata 0-5 m (dataran pantai)
        # Zona 3-15 km: naik ke 20-50 m (perbukitan)
        d_java_km = dist_java * 111.0            # konversi ke km (approx)
        elev_java = np.where(
            d_java_km < 3.0,
            d_java_km * 1.5,                     # ~1.5 m/km (dataran pantai rendah)
            4.5 + (d_java_km - 3.0) * 4.0        # ~4 m/km setelah 3 km
        )
        elev[java_land] = np.clip(elev_java[java_land], 0, 100)

        # Dataran Sumatera/Lampung: sedikit lebih curam
        d_sum_km = dist_sumatra * 111.0
        elev_sum = np.where(
            d_sum_km < 2.0,
            d_sum_km * 1.8,
            3.6 + (d_sum_km - 2.0) * 5.0
        )
        elev[sumatra_land] = np.clip(elev_sum[sumatra_land], 0, 120)

        # Variasi terrain lokal (bukit, lembah kecil)
        rng   = np.random.default_rng(seed=int(abs(lat_center * 10000)))
        noise = rng.normal(0, 1, (size, size)).astype(np.float32)
        noise = gaussian_filter(noise, sigma=5) * 3.0
        elev += noise
        elev[java_land]    = np.maximum(0.0, elev[java_land])
        elev[sumatra_land] = np.maximum(0.0, elev[sumatra_land])

        # Simpan bounds untuk konversi piksel → koordinat geo
        self._last_crop_bounds = {
            "min_lon": lon_center - half_deg,
            "max_lon": lon_center + half_deg,
            "min_lat": lat_center - half_deg,
            "max_lat": lat_center + half_deg,
        }

        return elev

    def _build_dem_tensor(
        self,
        magnitude: float,
        depth: float,
        lat: float,
        lon: float,
    ) -> torch.Tensor:
        """
        Bangun input DEM 10-channel (1, 10, 256, 256) dari GeoTIFF asli.

        Crop region 256×256 (~7.7km × 7.7km pada resolusi 30m) centered
        di epicenter, lalu derive 10 channel terrain features:

        Channel:
          0: Elevation (raw, normalized)
          1: Slope magnitude
          2: Slope aspect
          3: Profile curvature
          4: Plan curvature
          5: TPI (Topographic Position Index)
          6: TRI (Terrain Ruggedness Index)
          7: Roughness
          8: Distance-to-coast (jarak ke garis pantai 0m)
          9: Bathymetry mask (laut vs darat)
        """
        # Crop DEM asli di lokasi epicenter
        elev = self._crop_dem_at_epicenter(lat, lon, 256)

        channels = np.zeros((10, 256, 256), dtype=np.float32)

        # --- Ch 0: Elevation (standard-normalized) ---
        channels[0] = self._standardize(elev)

        # --- Ch 1: Slope magnitude ---
        gy, gx = np.gradient(elev)
        slope = np.sqrt(gx**2 + gy**2)
        channels[1] = self._standardize(slope)

        # --- Ch 2: Slope aspect ---
        aspect = np.arctan2(gy, gx)  # [-pi, pi]
        channels[2] = self._standardize(aspect)

        # --- Ch 3: Profile curvature (second derivative along gradient) ---
        gyy, _ = np.gradient(gy)
        _, gxx = np.gradient(gx)
        prof_curv = gyy + gxx
        channels[3] = self._standardize(prof_curv)

        # --- Ch 4: Plan curvature (second derivative perpendicular to gradient) ---
        gxy_y, _ = np.gradient(gx)
        _, gyx_x = np.gradient(gy)
        plan_curv = gxy_y - gyx_x
        channels[4] = self._standardize(plan_curv)

        # --- Ch 5: TPI (Topographic Position Index) ---
        # Perbedaan elevasi pixel vs rata-rata tetangga
        from scipy.ndimage import uniform_filter
        mean_elev = uniform_filter(elev, size=11)
        tpi = elev - mean_elev
        channels[5] = self._standardize(tpi)

        # --- Ch 6: TRI (Terrain Ruggedness Index) ---
        # Standar deviasi elevasi di jendela 3×3
        mean_sq = uniform_filter(elev**2, size=3)
        sq_mean = uniform_filter(elev, size=3)**2
        tri = np.sqrt(np.maximum(mean_sq - sq_mean, 0))
        channels[6] = self._standardize(tri)

        # --- Ch 7: Roughness ---
        # Perbedaan max–min di jendela 3×3
        from scipy.ndimage import maximum_filter, minimum_filter
        roughness = maximum_filter(elev, size=3) - minimum_filter(elev, size=3)
        channels[7] = self._standardize(roughness)

        # --- Ch 8: Distance-to-coast ---
        # Coast = batas antara elevasi negatif (laut) dan positif (darat)
        from scipy.ndimage import distance_transform_edt
        is_land = (elev >= 0).astype(np.float32)
        coast_dist = distance_transform_edt(1 - is_land) - distance_transform_edt(is_land)
        channels[8] = self._standardize(coast_dist)

        # --- Ch 9: Bathymetry mask (kontinu) ---
        # -1 = laut dalam, 0 = garis pantai, +1 = darat tinggi
        bathy_mask = np.clip(elev / 100.0, -1.0, 1.0)
        channels[9] = bathy_mask.astype(np.float32)

        return torch.tensor(channels, dtype=torch.float32).unsqueeze(0).to(self.device)

    @staticmethod
    def _standardize(arr: np.ndarray) -> np.ndarray:
        """Standard normalization (mean=0, std=1)."""
        std = arr.std()
        if std < 1e-8:
            return np.zeros_like(arr, dtype=np.float32)
        return ((arr - arr.mean()) / std).astype(np.float32)

    @staticmethod
    def _norm01(arr: np.ndarray) -> np.ndarray:
        """Normalisasi array ke [0, 1]."""
        mn, mx = arr.min(), arr.max()
        if mx - mn < 1e-8:
            return np.zeros_like(arr)
        return ((arr - mn) / (mx - mn)).astype(np.float32)

    # ──────────────────────────────────────────────
    # FAULT PREPROCESSING
    # ──────────────────────────────────────────────
    def preprocess_fault(self, magnitude, depth, lat, lon) -> torch.Tensor:
        """Normalisasi 9 parameter fault ke [0, 1] sesuai training bounds."""
        # Parameter statis (strike, dip, rake, length, width) — default realistis
        # untuk Selat Sunda (zona subduksi)
        fault_length = self._empirical_fault_length(magnitude)
        fault_width  = self._empirical_fault_width(magnitude)

        p = {
            'mw': magnitude,
            'lon0': lon,
            'lat0': lat,
            'depth': depth,
            'strike': 300.0,
            'dip': 20.0,
            'rake': 90.0,
            'length': fault_length,
            'width': fault_width,
        }
        vec = []
        keys = ['mw', 'lon0', 'lat0', 'depth', 'strike', 'dip', 'rake', 'length', 'width']
        for key in keys:
            low, high = self.fault_bounds[key]
            val = (p[key] - low) / (high - low)
            vec.append(np.clip(val, 0.0, 1.0))
        return torch.tensor([vec], dtype=torch.float32).to(self.device)

    @staticmethod
    def _empirical_fault_length(mw: float) -> float:
        """Panjang sesar empiris (Wells & Coppersmith 1994): log10(L) = -2.44 + 0.59*Mw."""
        return min(600.0, max(10.0, 10 ** (-2.44 + 0.59 * mw)))

    @staticmethod
    def _empirical_fault_width(mw: float) -> float:
        """Lebar sesar empiris (Wells & Coppersmith 1994): log10(W) = -1.01 + 0.32*Mw."""
        return min(250.0, max(5.0, 10 ** (-1.01 + 0.32 * mw)))

    # ──────────────────────────────────────────────
    # SEGMENTATION → GeoJSON POLYGON
    # ──────────────────────────────────────────────
    def _seg_mask_to_inundation_zones(
        self,
        seg_mask: np.ndarray,
        depth_map: np.ndarray,
    ) -> List[Dict]:
        """
        Konversi depth map 256x256 menjadi polygon GeoJSON.
        Menghasilkan 6 level zona genangan sesuai standar BMKG:
          > 14m  = Bahaya Ekstrem   (merah tua)
          10-14m = Bahaya Sangat Tinggi (merah)
           6-10m = Bahaya Tinggi    (oranye tua)
           3-6m  = Bahaya Sedang    (oranye)
          0.5-3m = Bahaya Rendah    (kuning)
         <0.5m  = Waspada           (hijau)
        """
        zones = []
        max_depth = float(np.max(depth_map))

        if max_depth < 0.05:
            return zones

        active_mask = seg_mask > 0
        if not np.any(active_mask):
            return zones

        # Threshold 6 level BMKG
        thresholds = [
            (14.0, 9999.0),   # Bahaya Ekstrem
            (10.0,  14.0),    # Bahaya Sangat Tinggi
            ( 6.0,  10.0),    # Bahaya Tinggi
            ( 3.0,   6.0),    # Bahaya Sedang
            ( 0.5,   3.0),    # Bahaya Rendah
            ( 0.05,  0.5),    # Waspada
        ]

        for low_th, high_th in thresholds:
            mask = active_mask & (depth_map >= low_th) & (depth_map < high_th)
            if not np.any(mask):
                continue

            mean_height  = float(np.mean(depth_map[mask]))
            polygon_rings = self._mask_to_polygon(mask)

            if polygon_rings:
                zones.append({
                    "coordinates": polygon_rings,
                    "height": round(mean_height, 2),
                })

        return zones

    def _mask_to_polygon(self, mask: np.ndarray) -> List[List[List[float]]]:
        """
        Konversi binary mask (256x256) menjadi polygon rings
        dalam koordinat geografis (lon, lat).

        Menggunakan skimage.measure.find_contours untuk bentuk tidak beraturan.
        """
        from skimage import measure

        # Map pixel coords ke geo coords berdasarkan LAST CROP BOUNDS
        b = self._last_crop_bounds
        
        # Cari kontur
        contours = measure.find_contours(mask.astype(float), 0.5)
        
        all_rings = []
        for contour in contours:
            # contour adalah (N, 2) array of (row, col)
            if len(contour) < 4:
                continue
                
            # Konversi pixel (row, col) ke (lon, lat)
            # Row 0 adalah top (max_lat), Row 256 adalah bottom (min_lat)
            # Col 0 adalah left (min_lon), Col 256 adalah right (max_lon)
            ring = []
            for row, col in contour:
                lon = b["min_lon"] + (col / 256.0) * (b["max_lon"] - b["min_lon"])
                lat = b["max_lat"] - (row / 256.0) * (b["max_lat"] - b["min_lat"])
                ring.append([round(float(lon), 6), round(float(lat), 6)])
            
            # Tutup ring jika belum
            if ring[0] != ring[-1]:
                ring.append(ring[0])
            
            all_rings.append(ring)

        return all_rings

    def _compute_inundation_realistic(
        self,
        lat: float,
        lon: float, 
        max_wave_height: float,
        magnitude: float,
        depth: float
    ) -> np.ndarray:
        """
        Modified Bathtub Model — mengikuti terrain nyata.
        Lebih achievable dari AI penuh, tetap menghasilkan
        zona genangan realistis.
        
        Return: array (256, 256) kedalaman genangan dalam meter
        """
        from scipy.ndimage import distance_transform_edt, gaussian_filter
        
        # Ambil data elevasi nyata
        elev = self._crop_dem_at_epicenter(lat, lon, 256)
        
        if elev is None or np.all(elev == 0):
            # Fallback jika DEM tidak tersedia
            return self._heuristic_depth_map(max_wave_height)
        
        # --- 1. Tentukan garis pantai ---
        # Pantai = area dengan elevasi mendekati 0 (batas laut-darat)
        land_mask = elev >= 0        # daratan
        sea_mask  = elev < 0         # laut / bawah laut
        
        # Jarak setiap piksel ke garis pantai (dalam piksel × 30m)
        coast_line = land_mask & ~sea_mask  # piksel tepat di pantai
        if not np.any(coast_line):
            # Jika tidak ada garis pantai di crop ini, buat dari elevasi rendah
            coast_line = elev < 2
        
        dist_to_coast_px = distance_transform_edt(~coast_line)
        dist_to_coast_m  = dist_to_coast_px * 30.0  # konversi ke meter
        
        # --- 2. Hitung tinggi gelombang di setiap titik daratan ---
        # Gelombang melemah seiring jarak dan naikan elevasi
        # Koefisien Manning-based attenuation
        k_distance  = 0.0015   # pelemahan karena jarak
        k_elevation = 0.08     # pelemahan karena naik elevasi
        
        wave_at_point = (
            max_wave_height 
            * np.exp(-k_distance  * dist_to_coast_m)
            * np.exp(-k_elevation * np.maximum(elev, 0))
        )
        
        # --- 3. Tentukan area tergenang ---
        # Tergenang jika: tinggi gelombang > elevasi daratan
        inundated_mask = (
            (wave_at_point > elev) &  # gelombang melebihi elevasi
            land_mask &                # hanya daratan (bukan laut)
            (elev < max_wave_height * 3)  # batas realistis
        )
        
        # --- 4. Hitung kedalaman genangan ---
        inundation_depth = np.where(
            inundated_mask,
            wave_at_point - elev,  # kedalaman = tinggi gelombang - elevasi
            0.0
        )
        
        # Haluskan tepi zona (supaya tidak terlalu kotak-kotak)
        inundation_depth = gaussian_filter(inundation_depth, sigma=1.5)
        inundation_depth = np.where(inundated_mask, inundation_depth, 0.0)
        inundation_depth = np.clip(inundation_depth, 0.0, 30.0)
        
        return inundation_depth

    def _heuristic_depth_map(self, max_wave_height: float) -> np.ndarray:
        """Fallback jika DEM tidak tersedia."""
        center = 128
        Y, X = np.ogrid[:256, :256]
        dist = np.sqrt((X - center)**2 + (Y - center)**2)
        depth = max_wave_height * np.exp(-0.015 * dist)
        return np.clip(depth, 0, max_wave_height)


    # MAIN PREDICTION
    # ──────────────────────────────────────────────
    async def predict(
        self,
        magnitude: float,
        depth: float,
        latitude: float,
        longitude: float,
        mode: str = "AI",
    ) -> Dict[str, Any]:
        start_time = time.time()
        logger.info(
            f"Running {mode} prediction for M{magnitude} "
            f"at ({latitude}, {longitude}), depth={depth}km"
        )

        # 1. Heuristic metrics (selalu dihitung untuk fallback dan impact zones)
        tsunami_potential = self._assess_tsunami_potential(magnitude, depth)
        heuristic_wave_height = self._estimate_wave_height(magnitude, depth)
        eta_minutes = self._estimate_eta(magnitude, depth, latitude, longitude)

        predicted_wave_height = heuristic_wave_height
        inundation_zones = []
        affected_area = 0.0
        mode_used = "HEURISTIC_FALLBACK"

        # 2. Physics-based Realistic Inundation
        if tsunami_potential and heuristic_wave_height > 0.1:
            try:
                # --- GUNAKAN METODE FISIKA REALISTIS ---
                depth_map = self._compute_inundation_realistic(
                    lat=latitude,
                    lon=longitude,
                    max_wave_height=heuristic_wave_height,
                    magnitude=magnitude,
                    depth=depth
                )

                # Statistik dari peta genangan
                active_pixels = int(np.sum(depth_map > 0.05))
                predicted_wave_height = float(np.max(depth_map))
                affected_area = float(active_pixels * self._pixel_area_km2)

                # Buat zona dari peta kedalaman (0 = aman, 1 = tergenang)
                zone_mask = np.where(depth_map > 0.05, 1, 0).astype(np.int64)

                inundation_zones = self._seg_mask_to_inundation_zones(
                    zone_mask, depth_map
                )
                
                mode_used = "PHYSICS_REALISTIC"

                logger.info(
                    f"Inundasi realistis: max={predicted_wave_height:.2f}m, "
                    f"area={affected_area:.1f}km², zona={len(inundation_zones)}"
                )

            except Exception as e:
                logger.error(f"Gagal hitung inundasi: {e}. Fallback ke Heuristic.", exc_info=True)
                predicted_wave_height = heuristic_wave_height
                affected_area = self._estimate_affected_area(magnitude, heuristic_wave_height)
                inundation_zones = self._generate_inundation_zones_heuristic(
                    latitude, longitude, heuristic_wave_height
                )
                mode_used = "HEURISTIC_FALLBACK"

        # 3. Metrik turunan
        category = self._classify_tsunami_category(magnitude, predicted_wave_height)
        impact_zones = self._get_impact_zones(latitude, longitude, magnitude, predicted_wave_height)
        wave_data = self._generate_wave_data(eta_minutes, predicted_wave_height)

        processing_time = (time.time() - start_time) * 1000

        result = {
            "prediction": {
                "eta": eta_minutes,
                "maxWaveHeight": round(predicted_wave_height, 2),
                "affectedArea": round(affected_area, 2),
                "tsunamiCategory": category,
                "processingTimeMs": int(processing_time),
            },
            "epicenter": {
                "latitude": latitude,
                "longitude": longitude,
            },
            "inundationZones": inundation_zones,
            "impactZones": impact_zones,
            "waveData": wave_data,
            "mode_used": mode_used,
        }

        logger.info(
            f"✅ Prediction selesai dalam {processing_time:.0f}ms "
            f"[{mode_used}] wave={predicted_wave_height:.2f}m"
        )
        return result

    # ──────────────────────────────────────────────
    # HEURISTIC HELPER METHODS
    # ──────────────────────────────────────────────
    def _assess_tsunami_potential(self, magnitude: float, depth: float) -> bool:
        return magnitude >= 6.5 and depth < 70

    def _estimate_wave_height(self, magnitude: float, depth: float) -> float:
        if magnitude < 6.5:
            return 0.0
        base_height = (magnitude - 6.0) ** 2.5
        depth_factor = max(0.1, 1.0 - (depth / 100.0))
        wave_height = base_height * depth_factor * 0.8
        return max(0.0, min(wave_height, 30.0))

    def _estimate_eta(self, magnitude: float, depth: float, lat: float, lon: float) -> int:
        # Jarak approx dari epicenter ke pantai terdekat Selat Sunda
        coastal_ref = [
            (-6.034, 105.826),  # Anyer
            (-6.394, 105.793),  # Labuan
            (-6.301, 105.656),  # Carita
        ]
        min_dist = min(
            self._haversine_distance(lat, lon, c[0], c[1])
            for c in coastal_ref
        )
        # Kecepatan tsunami di perairan dangkal ~100-200 km/h
        wave_speed_kmh = 200 if depth < 30 else 400
        eta_hours = min_dist / wave_speed_kmh
        eta_minutes = int(eta_hours * 60)
        return max(1, min(eta_minutes, 180))

    def _estimate_affected_area(self, magnitude: float, wave_height: float) -> float:
        if wave_height < 0.5:
            return 0.0
        area = (magnitude - 5.0) ** 2 * wave_height * 10
        return max(0.0, min(area, 500.0))

    def _classify_tsunami_category(self, magnitude: float, wave_height: float) -> str:
        if wave_height >= 10.0 or magnitude >= 8.5:
            return "Extreme"
        elif wave_height >= 5.0 or magnitude >= 8.0:
            return "High"
        elif wave_height >= 2.0 or magnitude >= 7.0:
            return "Medium"
        elif wave_height >= 0.5 or magnitude >= 6.5:
            return "Low"
        else:
            return "Minimal"



    def _generate_inundation_zones_heuristic(
        self, lat: float, lon: float, wave_height: float
    ) -> List[Dict]:
        """Fallback: inundation zones berdasarkan ellipse jarak (heuristic mode)."""
        if wave_height < 0.5:
            return []

        zones = []
        ellipse_params = [
            (0.20, 0.13, wave_height * 1.0),
            (0.13, 0.08, wave_height * 0.6),
            (0.07, 0.045, wave_height * 0.3),
        ]
        n_points = 36
        for semi_lon, semi_lat, height_at_level in ellipse_params:
            ring = []
            for i in range(n_points):
                angle = 2 * math.pi * i / n_points
                ring.append([
                    round(lon + semi_lon * math.cos(angle), 6),
                    round(lat + semi_lat * math.sin(angle), 6),
                ])
            ring.append(ring[0])
            zones.append({
                "coordinates": [ring],
                "height": round(height_at_level, 2),
            })
        return zones

    def _get_impact_zones(
        self, lat: float, lon: float, magnitude: float, wave_height: float
    ) -> List[Dict]:
        coastal_cities = [
            {"name": "Pantai Anyer", "lat": -6.034, "lon": 105.826},
            {"name": "Labuan",       "lat": -6.394, "lon": 105.793},
            {"name": "Carita",       "lat": -6.301, "lon": 105.656},
            {"name": "Sumur",        "lat": -6.650, "lon": 105.583},
            {"name": "Cilegon",      "lat": -6.003, "lon": 106.001},
        ]
        impact_zones = []
        for city in coastal_cities:
            distance = self._haversine_distance(lat, lon, city["lat"], city["lon"])
            if distance < 100:
                local_wave_height = wave_height * math.exp(-distance / 50.0)
                if local_wave_height > 0.3:
                    eta = int(distance / 10) + 5
                    impact_zones.append({
                        "name": city["name"],
                        "distance": round(distance, 1),
                        "eta": eta,
                        "waveHeight": round(local_wave_height, 2),
                    })
        return sorted(impact_zones, key=lambda x: x["eta"])

    def _generate_wave_data(self, eta_minutes: int, max_wave_height: float) -> List[Dict]:
        time_points = range(0, min(eta_minutes + 30, 120), 5)
        wave_data = []
        for t in time_points:
            if t < eta_minutes:
                height = 0.2 + 0.1 * np.sin(t / 10.0)
            else:
                time_since_arrival = t - eta_minutes
                decay = np.exp(-time_since_arrival / 20.0)
                oscillation = np.sin(time_since_arrival / 5.0)
                height = max_wave_height * decay * (0.7 + 0.3 * oscillation)
            wave_data.append({
                "time": t,
                "waveHeight": round(max(0.0, float(height)), 2),
            })
        return wave_data

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c


# ──────────────────────────────────────────────
# SINGLETON — model di-load sekali saat import
# ──────────────────────────────────────────────
prediction_service = PredictionService()
