from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from neo4j import GraphDatabase
import redis
import json
import requests

# MongoDB setup
MONGO_USERNAME = "followalong"
MONGO_PASSWORD = "Password123"
MONGO_CLUSTER_URL = "cluster0.3d5bm.mongodb.net"
MONGO_URI = f"mongodb+srv://{MONGO_USERNAME}:{MONGO_PASSWORD}@{MONGO_CLUSTER_URL}/?retryWrites=true&w=majority"

# Neo4j setup
NEO4J_URI = "neo4j+ssc://71694c64.databases.neo4j.io"
NEO4J_AUTH = ("neo4j", "67K_YaJF3anGhvRJ63gLW3Qdx0B_AuTFSVUgWc-V7z4")

# Redis setup
REDIS_HOST = "redis-14767.c100.us-east-1-4.ec2.redns.redis-cloud.com"
REDIS_PORT = 14767
REDIS_USERNAME = "default"
REDIS_PASSWORD = "ZnvOdRoTWWFhmDToxBcncijbb3UE8WJL"

# Weather setup
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# Connect to MongoDB
def connect_to_mongodb():
    client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
    try:
        client.admin.command('ping')
        print("Connected to MongoDB!")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
    return client


def insert_into_mongodb(client, metro_lines, metro_stops):
    db = client["metro_data"]  # Database name
    lines_collection = db["lines"]  # Collection for lines
    stops_collection = db["stops"]  # Collection for stops

    try:
        # Insert or update lines
        if metro_lines:
            for line in metro_lines:
                lines_collection.update_one(
                    {"name": line["name"]},  # Check for duplicates by name
                    {"$set": line},          # Update data or insert if not exists
                    upsert=True              # Create the entry if it doesn't exist
                )
            print(f"Upserted {len(metro_lines)} metro lines into MongoDB.")

        # Insert or update stops
        if metro_stops:
            for stop in metro_stops:
                stops_collection.update_one(
                    {"name": stop["name"]},  # Check for duplicates by name
                    {"$set": stop},          # Update data or insert if not exists
                    upsert=True              # Create the entry if it doesn't exist
                )
            print(f"Upserted {len(metro_stops)} metro stops into MongoDB.")

    except Exception as e:
        print(f"Failed to insert or update MongoDB: {e}")


# Connect to Neo4j
def connect_to_neo4j():
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    try:
        driver.verify_connectivity()
        print("Connected to Neo4j!")
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}")
        driver = None
    return driver

# Connect to Redis
def connect_to_redis():
    client = redis.StrictRedis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        username=REDIS_USERNAME,
        password=REDIS_PASSWORD,
        decode_responses=True
    )
    try:
        client.ping()
        print("Connected to Redis!")
    except redis.exceptions.ConnectionError as e:
        print(f"Failed to connect to Redis: {e}")
        client = None
    return client

def insert_into_neo4j(driver, metro_lines, metro_stops):
    """
    Inserts stations, lines, and relationships into Neo4j.
    Handles multi-line stations by setting the position property on the SERVICED_BY relationship.
    """

    def create_station(tx, station):
        """
        Create or update a station node in Neo4j.
        """
        query = """
        MERGE (s:Station {name: $name})
        SET s.latitude = $latitude, s.longitude = $longitude
        """
        tx.run(query, name=station["name"], latitude=station["latitude"], longitude=station["longitude"])

    def create_line(tx, line):
        """
        Create or update a line node in Neo4j.
        """
        query = """
        MERGE (l:Line {name: $name})
        """
        tx.run(query, name=line["name"])

    def connect_station_line(tx, station_name, line_name, position):
        """
        Create a SERVICED_BY relationship between a station and a line and set the position on the relationship.
        """
        query = """
        MATCH (s:Station {name: $station_name}), (l:Line {name: $line_name})
        MERGE (s)-[r:SERVICED_BY]->(l)
        SET r.position = $position
        """
        tx.run(query, station_name=station_name, line_name=line_name, position=position)

    with driver.session() as session:
        # Insert stations
        for station in metro_stops:
            session.execute_write(create_station, station)

        # Insert lines and connect them to stations
        for line in metro_lines:
            session.execute_write(create_line, line)
            normalized_line_name = line["name"].lower().replace(" ", "-")

            for station in metro_stops:
                for line_info in station["lines"]:
                    if line_info["line"] == normalized_line_name:
                        # Safely handle missing position fields
                        position = line_info.get("position", None)
                        if position is not None:
                            session.execute_write(
                                connect_station_line,
                                station["name"],
                                line["name"],
                                position
                            )
                        else:
                            print(f"Warning: Missing position for station '{station['name']}' on line '{line_info['line']}'")

    print("Data insertion completed successfully.")

# Fetch live weather data
def insert_into_redis(client, metro_stops):
    for station in metro_stops:
        station_name = station.get("name")
        if not station_name:
            print("Station name is missing. Skipping.")
            continue

        station_data = {
            "latitude": station["latitude"],
            "longitude": station["longitude"],
            "lines": station["lines"]
        }

        # Cache station data
        key = f"station:{station_name}"
        try:
            client.set(key, json.dumps(station_data))
            print(f"Inserted station '{station_name}' into Redis.")
        except redis.exceptions.RedisError as e:
            print(f"Failed to insert station '{station_name}' into Redis: {e}")
            continue

        # Fetch and cache weather data
        weather_data = fetch_weather_data(station["latitude"], station["longitude"])
        if weather_data:
            cache_weather_data(client, station, weather_data)


def fetch_weather_data(latitude, longitude):
    url = WEATHER_URL
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current_weather": True
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json().get("current_weather")
    else:
        print(f"Failed to fetch weather data for coordinates ({latitude}, {longitude}): {response.status_code}")
        return None

def cache_weather_data(client, station, weather_data):
    """
    Cache weather data in Redis for a specific metro station.

    Args:
        client (redis.Redis): The Redis client instance.
        station (dict): The metro station data, including `name` as the identifier.
        weather_data (dict): The weather data to be cached.

    Raises:
        redis.exceptions.RedisError: If there is an issue with caching the data.
    """
    # Construct the Redis key using the station name
    station_name = station.get("name")
    if not station_name:
        print("Station name is missing. Cannot cache weather data.")
        return

    key = f"weather:{station_name}"

    try:
        # Cache the weather data as a JSON string with a 1-hour expiry
        client.set(key, json.dumps(weather_data), ex=3600)
        print(f"Cached weather data for station '{station_name}'")
    except redis.exceptions.RedisError as e:
        print(f"Failed to cache weather data for station '{station_name}': {e}")


def main():
    # Connect to databases
    mongo_client = connect_to_mongodb()
    neo4j_driver = connect_to_neo4j()
    redis_client = connect_to_redis()

    # Load data from files
    with open("metro-lines.json", "r") as file:
        metro_lines = json.load(file)

    with open("metro-stops.json", "r") as file:
        metro_stops = json.load(file)

    # Insert into databases
    if mongo_client:
        insert_into_mongodb(mongo_client, metro_lines, metro_stops)

    if neo4j_driver:
        insert_into_neo4j(neo4j_driver, metro_lines, metro_stops)

    if redis_client:
        insert_into_redis(redis_client, metro_stops)

    # Close connections
    if neo4j_driver:
        neo4j_driver.close()


if __name__ == "__main__":
    main()


