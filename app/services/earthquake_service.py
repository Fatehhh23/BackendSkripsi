import aiohttp
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import hashlib

from app.config import settings

logger = logging.getLogger(__name__)

class EarthquakeService:
    """
    Service untuk fetch data gempa dari BMKG atau USGS
    """
    
    def __init__(self):
        self.bmkg_url = settings.BMKG_API_URL
        self.usgs_url = settings.USGS_API_URL
        self.timeout = aiohttp.ClientTimeout(total=settings.API_TIMEOUT)
    
    async def fetch_recent_earthquakes(
        self,
        min_magnitude: float = 5.0,
        hours: int = 24,
        limit: int = 10,
        source: str = "usgs"  # "bmkg" or "usgs"
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent earthquakes from external API
        """
        logger.info(f"Fetching earthquakes from {source.upper()}: M>={min_magnitude}, last {hours}h")
        
        try:
            if source.lower() == "bmkg":
                earthquakes = await self._fetch_from_bmkg()
            else:
                earthquakes = await self._fetch_from_usgs(min_magnitude, hours)
            
            # Filter and sort
            filtered = [
                eq for eq in earthquakes
                if eq['magnitude'] >= min_magnitude
            ]
            filtered.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return filtered[:limit]
            
        except Exception as e:
            logger.error(f"Error fetching earthquakes from {source}: {e}", exc_info=True)
            # Return demo data as fallback
            return self._get_demo_data(limit)
    
    async def _fetch_from_bmkg(self) -> List[Dict[str, Any]]:
        """
        Fetch dari BMKG (format XML)
        URL: https://data.bmkg.go.id/DataMKG/TEWS/gempaterkini.xml
        """
        # Gunakan URL Gempa Terkini (15 gempa M 5.0+)
        url = "https://data.bmkg.go.id/DataMKG/TEWS/gempaterkini.xml"
        
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"BMKG API returned status {response.status}")
                        return []
                    
                    content = await response.text()
                    return self._parse_bmkg_xml(content)
            except Exception as e:
                logger.error(f"Failed to fetch from BMKG: {e}")
                return []
    
    def _parse_bmkg_xml(self, xml_content: str) -> List[Dict[str, Any]]:
        """
        Parse XML response dari BMKG (format gempaterkini.xml)
        """
        try:
            root = ET.fromstring(xml_content)
            earthquakes = []
            
            # BMKG XML structure for gempaterkini.xml:
            # <Infogempa>
            #   <gempa>
            #     <Tanggal>12 Feb 2026</Tanggal>
            #     <Jam>18:00:00 WIB</Jam>
            #     <Lintang>-6.5</Lintang>
            #     <Bujur>105.3</Bujur>
            #     <Magnitude>5.2</Magnitude>
            #     <Kedalaman>10 km</Kedalaman>
            #     <Wilayah>52 km BaratDaya SUMUR-BANTEN</Wilayah>
            #     <Potensi>Tidak berpotensi tsunami</Potensi>
            #   </gempa>
            #   ...
            # </Infogempa>
            
            for gempa in root.findall('gempa'):
                try:
                    # Extract data
                    tanggal = gempa.find('Tanggal').text
                    jam = gempa.find('Jam').text
                    datetime_str = f"{tanggal} {jam}"
                    
                    # Parse timestamp (WIB is UTC+7)
                    # Example: "12 Feb 2026 18:00:00 WIB"
                    # Simple parsing, assuming consistent format
                    dt_str = datetime_str.replace(" WIB", "")
                    try:
                        # Coba parsing format standard BMKG
                        # Format tanggal BMKG bisa berubah, perlu robust parsing
                        # Misal: 12-Feb-26 atau 12 Feb 2026
                        dt = datetime.strptime(dt_str, "%d %b %Y %H:%M:%S")
                        timestamp = dt - timedelta(hours=7) # Convert WIB to UTC
                    except ValueError:
                         # Fallback for current time if parsing fails
                        logger.warning(f"Failed to parse BMKG date: {datetime_str}")
                        timestamp = datetime.utcnow()

                    # Parse latitude
                    lat_str = gempa.find('Lintang').text
                    lat_val = float(lat_str.replace(' LS', '').replace(' LU', ''))
                    if 'LS' in lat_str:
                        lat = -abs(lat_val)
                    else:
                        lat = abs(lat_val)
                    
                    # Parse longitude
                    lon_str = gempa.find('Bujur').text
                    lon_val = float(lon_str.replace(' BT', '').replace(' BB', ''))
                    if 'BB' in lon_str:
                        lon = -abs(lon_val)
                    else:
                        lon = abs(lon_val)
                    
                    mag = float(gempa.find('Magnitude').text)
                    depth_str = gempa.find('Kedalaman').text
                    depth = float(depth_str.split()[0]) # "10 km" -> 10.0
                    wilayah = gempa.find('Wilayah').text
                    
                    # Create unique ID from properties to avoid duplicates
                    id_str = f"{timestamp.isoformat()}-{lat}-{lon}-{mag}"
                    eq_id = f"bmkg-{hashlib.md5(id_str.encode()).hexdigest()[:10]}"
                    
                    earthquakes.append({
                        'id': eq_id,
                        'magnitude': mag,
                        'depth': depth,
                        'latitude': lat,
                        'longitude': lon,
                        'timestamp': timestamp,
                        'location': wilayah,
                        'source': 'BMKG'
                    })
                except Exception as e:
                    logger.error(f"Error parsing individual BMKG quake: {e}")
                    continue
            
            return earthquakes
            
        except Exception as e:
            logger.error(f"Error parsing BMKG XML Root: {e}")
            return []
    
    async def _fetch_from_usgs(self, min_magnitude: float, hours: int) -> List[Dict[str, Any]]:
        """
        Fetch dari USGS Earthquake API (GeoJSON)
        URL: https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson
        """
        # USGS Feed URL (Past Day, M2.5+)
        # Documentation: https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php
        url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"
        
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"USGS API returned status {response.status}")
                        return []
                    
                    data = await response.json()
                    return self._parse_usgs_geojson(data)
            except Exception as e:
                logger.error(f"Failed to fetch from USGS: {e}")
                return []
    
    def _parse_usgs_geojson(self, geojson: Dict) -> List[Dict[str, Any]]:
        """
        Parse GeoJSON response dari USGS
        """
        earthquakes = []
        
        try:
            for feature in geojson.get('features', []):
                try:
                    props = feature.get('properties', {})
                    geom = feature.get('geometry', {})
                    coords = geom.get('coordinates', [])
                    
                    if len(coords) < 3:
                        continue
                        
                    mag = float(props.get('mag', 0.0))
                    
                    # USGS uses milliseconds timestamp
                    ts_ms = props.get('time', 0)
                    timestamp = datetime.utcfromtimestamp(ts_ms / 1000)
                    
                    # USGS ID is reliable
                    eq_id = f"usgs-{feature.get('id')}"
                    
                    earthquakes.append({
                        'id': eq_id,
                        'magnitude': mag,
                        'depth': float(coords[2]), # Depth in km
                        'latitude': float(coords[1]),
                        'longitude': float(coords[0]),
                        'timestamp': timestamp,
                        'location': props.get('place', 'Unknown Location'),
                        'source': 'USGS'
                    })
                except Exception as e:
                     continue
            
            return earthquakes
            
        except Exception as e:
            logger.error(f"Error parsing USGS GeoJSON: {e}")
            return []
    
    def _get_demo_data(self, limit: int) -> List[Dict[str, Any]]:
        """
        Return demo earthquake data for testing
        """
        import random
        
        demo_earthquakes = []
        base_time = datetime.utcnow()
        
        locations = [
            "52 km Barat Daya Sumur-Banten",
            "45 km Selatan Pandeglang-Banten",
            "38 km Barat Laut Labuan-Banten",
            "62 km Tenggara Anyer-Banten",
            "41 km Timur Laut Cilegon-Banten"
        ]
        
        for i in range(min(limit, 5)):
            demo_earthquakes.append({
                'id': f'demo-{i+1}',
                'magnitude': round(random.uniform(5.0, 7.5), 1),
                'depth': round(random.uniform(10.0, 50.0), 1),
                'latitude': round(random.uniform(-6.8, -6.0), 3),
                'longitude': round(random.uniform(105.0, 106.0), 3),
                'timestamp': base_time - timedelta(hours=i * 2),
                'location': random.choice(locations),
                'source': 'DEMO'
            })
        
        return demo_earthquakes
