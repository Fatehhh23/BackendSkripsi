from app.config import settings

def validate_earthquake_params(
    magnitude: float,
    depth: float,
    latitude: float,
    longitude: float
) -> None:
    """
    Validate earthquake parameters.
    Raises ValueError if invalid.
    """
    # Validate magnitude
    if not (settings.MIN_MAGNITUDE <= magnitude <= settings.MAX_MAGNITUDE):
        raise ValueError(
            f"Magnitudo harus antara {settings.MIN_MAGNITUDE} dan {settings.MAX_MAGNITUDE}"
        )
    
    # Validate depth
    if not (settings.MIN_DEPTH <= depth <= settings.MAX_DEPTH):
        raise ValueError(
            f"Kedalaman harus antara {settings.MIN_DEPTH} dan {settings.MAX_DEPTH} km"
        )
    
    # Validate latitude
    if not (-90.0 <= latitude <= 90.0):
        raise ValueError("Latitude harus antara -90 dan 90")
    
    # Validate longitude
    if not (-180.0 <= longitude <= 180.0):
        raise ValueError("Longitude harus antara -180 dan 180")
    
    # Optional: Validate if within Selat Sunda region
    bounds = settings.SUNDA_STRAIT_BOUNDS
    if not (bounds['min_lat'] <= latitude <= bounds['max_lat'] and
            bounds['min_lon'] <= longitude <= bounds['max_lon']):
        # Just a warning, not an error
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"Koordinat ({latitude}, {longitude}) di luar batas Selat Sunda. "
            "Prediksi mungkin kurang akurat."
        )
