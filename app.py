import streamlit as st
from database.redis_setup import connect_to_redis, get_cached_weather_data
from database.mongodb_setup import connect_to_mongodb, search_station
from database.neo4j_setup import get_connected_stations, find_shortest_route, get_neo4j_driver

# Connect to MongoDB
mongo_client = connect_to_mongodb()
mongo_db = mongo_client["metro_data"]

# Connect to Redis
redis_client = connect_to_redis()

# Connect to Neo4j
neo4j_driver = get_neo4j_driver()

# Streamlit UI
st.title("Metro Station Information")

# Get user input for station name
station_name = st.text_input("Enter Station Name:")

if station_name:
    # Search for station in MongoDB
    station = search_station(mongo_db, station_name)

    if station:
        st.write(f"Station Found: {station['text']}")

        # Display latitude and longitude
        st.write(f"Latitude: {station['latitude']}, Longitude: {station['longitude']}")

        # Retrieve weather data from Redis
        cached_weather = get_cached_weather_data(redis_client, station["id"])
        if cached_weather:
            st.write(f"Weather: {cached_weather['temperature']}°C, {cached_weather['weathercode']}")
        else:
            st.write("No cached weather data available.")

        # Fetch connected stations from Neo4j
        connected_stations = get_connected_stations(neo4j_driver, station_name)

        if connected_stations:
            st.write("Connected Stations (with distance):")
            for connection in connected_stations:
                st.write(f"{connection['name']} - Distance: {connection['distance']} km")
        else:
            st.write("No connected stations found.")
    else:
        st.write(f"Station '{station_name}' not found.")

# Streamlit UI for shortest path between two stations
st.title("Find Shortest Path Between Stations")

start_station_name = st.text_input("Enter Start Station Name:")
end_station_name = st.text_input("Enter End Station Name:")

if start_station_name and end_station_name:
    # Find the shortest route using Neo4j
    shortest_route = find_shortest_route(neo4j_driver, start_station_name, end_station_name)

    if shortest_route:
        st.write("Shortest Route:")
        for station in shortest_route:
            st.write(station)
    else:
        st.write("No route found between the stations.")
