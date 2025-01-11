from weather_api import fetch_weather

# Test coordinates for a station (e.g., Paris)
lat = 45.8566  # Latitude for Paris
lon = 2.3522   # Longitude for Paris

# Fetch weather data for the station (this will check the cache first)
weather_data = fetch_weather(lat, lon)
print(f"Weather data for station ({lat}, {lon}): {weather_data}")

# Run the same query again to check cache usage
weather_data = fetch_weather(lat, lon)
print(f"Weather data for station ({lat}, {lon}) after cache: {weather_data}")
