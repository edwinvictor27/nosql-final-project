import requests
from weather_cache import get_weather_from_cache, add_weather_to_cache

# Open-Meteo API URL for weather data
API_URL = "https://api.open-meteo.com/v1/forecast"

def fetch_weather(lat, lon):
    """Fetch weather data for a given latitude and longitude."""
    # First, check if the weather data is in the Redis cache
    cached_weather = get_weather_from_cache(lat, lon)
    
    if cached_weather:
        print(f"Using cached data for {lat}, {lon}")
        return cached_weather  # Return cached weather data if available

    # If not cached, fetch weather data from Open-Meteo API
    print(f"Fetching new weather data for {lat}, {lon}")
    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": True  # Fetch only current weather
    }
    
    response = requests.get(API_URL, params=params)
    
    if response.status_code == 200:
        weather_data = response.json().get("current_weather", {})
        
        # Add the fetched data to the cache (Redis)
        add_weather_to_cache(lat, lon, weather_data)
        
        return weather_data
    else:
        print(f"Error fetching weather data: {response.status_code}")
        return None
