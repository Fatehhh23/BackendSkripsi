import geopandas as gpd
from shapely.geometry import Point, Polygon, LineString
from typing import Dict, Any, List
import logging
import json

from app.config import settings

logger = logging.getLogger(__name__)

class GeospatialService:
    """
    Service untuk operasi geospasial (GeoJSON conversion, spatial analysis)
    """
    
    def __init__(self):
        self.coastline_data = None
        self._load_coastline_data()
    
    def _load_coastline_data(self):
        """
        Load coastline data dari file GeoJSON
        """
        try:
            coastline_path = settings.COASTLINES_DIR / "sunda_strait_coastline.geojson"
            if coastline_path.exists():
                self.coastline_data = gpd.read_file(coastline_path)
                logger.info(f"✅ Loaded coastline data: {len(self.coastline_data)} features")
            else:
                logger.warning(f"⚠️ Coastline data not found at {coastline_path}")
        except Exception as e:
            logger.error(f"Error loading coastline data: {e}")
    
    def create_epicenter_geojson(self, latitude: float, longitude: float) -> Dict:
        """
        Create GeoJSON Point for epicenter
        """
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [longitude, latitude]
            },
            "properties": {
                "type": "epicenter"
            }
        }
    
    def create_inundation_polygon(self, coordinates: List[List[float]], wave_height: float) -> Dict:
        """
        Create GeoJSON Polygon for inundation zone
        """
        return {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [coordinates]
            },
            "properties": {
                "waveHeight": wave_height,
                "type": "inundation_zone"
            }
        }
    
    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two points using geodesic
        Returns distance in kilometers
        """
        from geopy.distance import geodesic
        return geodesic((lat1, lon1), (lat2, lon2)).kilometers
    
    def get_coastal_points_in_range(self, lat: float, lon: float, radius_km: float) -> List[Dict]:
        """
        Get coastal points within radius from epicenter
        """
        if self.coastline_data is None:
            return []
        
        try:
            epicenter = Point(lon, lat)
            buffer_radius = radius_km / 111.0  # Rough conversion to degrees
            
            # Create buffer around epicenter
            buffer = epicenter.buffer(buffer_radius)
            
            # Find intersecting coastline segments
            intersecting = self.coastline_data[self.coastline_data.intersects(buffer)]
            
            coastal_points = []
            for idx, row in intersecting.iterrows():
                # Extract representative point
                point = row.geometry.centroid
                coastal_points.append({
                    'latitude': point.y,
                    'longitude': point.x,
                    'name': row.get('name', f'Point {idx}')
                })
            
            return coastal_points
            
        except Exception as e:
            logger.error(f"Error getting coastal points: {e}")
            return []
    
    def convert_to_geojson_feature_collection(self, features: List[Dict]) -> Dict:
        """
        Convert list of features to GeoJSON FeatureCollection
        """
        return {
            "type": "FeatureCollection",
            "features": features
        }
