import redis
import json

# Redis connection details
REDIS_HOST = "redis-14767.c100.us-east-1-4.ec2.redns.redis-cloud.com"
REDIS_PORT = 14767
REDIS_USERNAME = "default"
REDIS_PASSWORD = "ZnvOdRoTWWFhmDToxBcncijbb3UE8WJL"

# File path for JSON data
METRO_JSON_PATH = "metro.json"


def connect_to_redis():
    """
    Connect to the Redis database and return the client instance.
    """
    client = redis.StrictRedis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        username=REDIS_USERNAME,
        password=REDIS_PASSWORD,
        decode_responses=True  # Ensures responses are returned as strings
    )
    try:
        client.ping()
        print("Connected to Redis successfully!")
    except redis.exceptions.ConnectionError as e:
        print(f"Failed to connect to Redis: {e}")
        client = None
    return client


def load_metro_data(file_path):
    """
    Load metro data from the JSON file.
    Args:
        file_path: Path to the JSON file.
    Returns:
        List of station nodes from the JSON file.
    """
    with open(file_path, "r", encoding="utf-8") as file:
        metro_data = json.load(file)
    print(f"Loaded {len(metro_data['nodes'])} stations from {file_path}.")
    return metro_data["nodes"]


def cache_weather_data(client, station_id, weather_data):
    """
    Cache weather data in Redis with an expiration time of 1 hour.
    Args:
        client: Redis client instance.
        station_id: Unique station ID for the Redis key.
        weather_data: Weather data dictionary to cache.
    """
    key = f"weather:{station_id}"
    try:
        client.set(key, json.dumps(weather_data), ex=3600)  # Cache for 1 hour
        print(f"Weather data cached for station ID {station_id}.")
    except redis.exceptions.RedisError as e:
        print(f"Failed to cache weather data for station ID {station_id}: {e}")


def get_cached_weather_data(client, station_id):
    """
    Retrieve cached weather data from Redis.
    Args:
        client: Redis client instance.
        station_id: Unique station ID for the Redis key.
    Returns:
        Cached weather data as a dictionary, or None if not found.
    """
    key = f"weather:{station_id}"
    try:
        data = client.get(key)
        if data:
            print(f"Retrieved cached weather data for station ID {station_id}.")
            return json.loads(data)
        else:
            print(f"No cached data found for station ID {station_id}.")
            return None
    except redis.exceptions.RedisError as e:
        print(f"Failed to retrieve cached weather data for station ID {station_id}: {e}")
        return None


if __name__ == "__main__":
    # Connect to Redis
    redis_client = connect_to_redis()
    if redis_client is None:
        exit("Exiting: Unable to connect to Redis.")

    # Load metro data from JSON file
    stations = load_metro_data(METRO_JSON_PATH)

    # Fetch and cache weather data for all stations
    for station in stations:
        station_id = station["id"]

        # Retrieve cached weather data from Redis
        cached_weather = get_cached_weather_data(redis_client, station_id)

        if cached_weather:
            print(f"Weather data for station ID {station_id}: {cached_weather}")
        else:
            print(f"No cached weather data available for station ID {station_id}.")
