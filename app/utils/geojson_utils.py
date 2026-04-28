from typing import List, Dict, Any
import json

def create_point_geojson(longitude: float, latitude: float, properties: Dict = None) -> Dict:
    """
    Create GeoJSON Point feature
    """
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [longitude, latitude]
        },
        "properties": properties or {}
    }

def create_polygon_geojson(coordinates: List[List[float]], properties: Dict = None) -> Dict:
    """
    Create GeoJSON Polygon feature
    """
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [coordinates]
        },
        "properties": properties or {}
    }

def create_feature_collection(features: List[Dict]) -> Dict:
    """
    Create GeoJSON FeatureCollection
    """
    return {
        "type": "FeatureCollection",
        "features": features
    }

def validate_geojson(geojson: Dict) -> bool:
    """
    Basic GeoJSON validation
    """
    if not isinstance(geojson, dict):
        return False
    
    if "type" not in geojson:
        return False
    
    valid_types = ["Feature", "FeatureCollection", "Point", "LineString", "Polygon", "MultiPoint", "MultiLineString", "MultiPolygon"]
    if geojson["type"] not in valid_types:
        return False
    
    return True
