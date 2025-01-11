import redis
import json
import hashlib

cache = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

def generate_cache_key(lat, lon):
    """Generate a unique cache key for a station based on latitude and longitude."""
    return hashlib.md5(f"{lat},{lon}".encode()).hexdigest()

def get_weather_from_cache(lat, lon):
    """Get weather data from Redis cache."""
    cache_key = generate_cache_key(lat, lon)
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return json.loads(cached_data)
    return None

def add_weather_to_cache(lat, lon, weather_data):
    """Add weather data to Redis cache."""
    cache_key = generate_cache_key(lat, lon)
    cache.setex(cache_key, 3600, json.dumps(weather_data))  # Cache for 1 hour

def clear_cache():
    """Clear all cached data in Redis."""
    cache.flushdb()
