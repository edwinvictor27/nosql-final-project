import streamlit as st
from metro_navigation_system import connect_to_mongodb, connect_to_neo4j, connect_to_redis, fetch_weather_data
from math import radians, cos, sin, sqrt, atan2

# Database connections
mongo_client = connect_to_mongodb()
neo4j_driver = connect_to_neo4j()
redis_client = connect_to_redis()

# Haversine formula to calculate the distance between two points
def calculate_distance(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    radius_of_earth_km = 6371  # Radius of the Earth in kilometers
    return radius_of_earth_km * c

#mongodb queries
def get_station_coordinates(station_name):
    """
    Fetch latitude and longitude of a station from MongoDB.
    """
    db = mongo_client["metro_data"]
    station = db["stops"].find_one({"name": station_name}, {"latitude": 1, "longitude": 1, "_id": 0})
    if station:
        return station
    else:
        return None

def find_distance_between_stations(station1, station2):
    """
    Find the distance between two metro stations.
    """
    coords1 = get_station_coordinates(station1)
    coords2 = get_station_coordinates(station2)

    if not coords1:
        return f"Station '{station1}' not found.", False
    if not coords2:
        return f"Station '{station2}' not found.", False

    lat1, lon1 = coords1["latitude"], coords1["longitude"]
    lat2, lon2 = coords2["latitude"], coords2["longitude"]

    distance = calculate_distance(lat1, lon1, lat2, lon2)
    return round(distance, 2), True

def get_all_station_names():
    db = mongo_client["metro_data"]
    stations = db["stops"].find({}, {"name": 1, "_id": 0})
    return [station["name"] for station in stations]

def normalize_line_name(line_name):
    """
    Normalize line names to match between metro-lines.json and metro-stops.json.
    """
    return line_name.lower().replace(" ", "-")

def get_stations_by_line(line_name):
    """
    Fetch all stations served by a specific line from MongoDB, ordered by position.
    """
    normalized_line_name = normalize_line_name(line_name)
    db = mongo_client["metro_data"]
    stations = db["stops"].find(
        {"lines.line": normalized_line_name},  # Match normalized line name
        {"name": 1, "lines": 1, "_id": 0}
    )

    # Extract position for the given line and sort stations by it
    station_list = []
    for station in stations:
        for line in station["lines"]:
            if line["line"] == normalized_line_name:
                station_list.append((station["name"], line.get("position", float('inf'))))
                break

    # Sort by position
    station_list.sort(key=lambda x: x[1])
    return [station[0] for station in station_list]

def get_all_lines():
    """
    Fetch all unique line names from the MongoDB lines collection.
    """
    db = mongo_client["metro_data"]
    lines = db["lines"].find({}, {"name": 1, "_id": 0})
    return sorted([line["name"] for line in lines])

#neo4j queries
def shortest_path_between_stations(driver, start_station, end_station):
    """
    Find the shortest path between two metro stations using Neo4j.

    Args:
        driver: Neo4j driver instance.
        start_station (str): Name of the starting station.
        end_station (str): Name of the destination station.

    Returns:
        list: Ordered list of station names representing the shortest route.
    """
    with driver.session() as session:
        query = """
        MATCH (start:Station {name: $start_station}), (end:Station {name: $end_station}),
        path = shortestPath((start)-[*]-(end))
        RETURN [n IN nodes(path) | n.name] AS route
        """
        result = session.run(query, start_station=start_station, end_station=end_station)
        route = result.single()
        if route:
            return route["route"]
        else:
            return None

def find_station_neighbors(driver, station_name):
    """
    Find neighbors dynamically for a station based on its line and position in Neo4j.
    """
    query = """
    MATCH (s:Station {name: $station_name})-[r1:SERVICED_BY]->(l:Line)<-[r2:SERVICED_BY]-(neighbor:Station)
    WHERE abs(r1.position - r2.position) = 1
    RETURN neighbor.name AS neighbor, l.name AS line_name
    """
    with driver.session() as session:
        result = session.run(query, station_name=station_name)
        neighbors = [{"neighbor": record["neighbor"], "line": record["line_name"]} for record in result]
        return neighbors


#redis queries

def get_station_weather(station_name):
    """
    Fetch and display the weather for a station.
    """
    station = get_station_coordinates(station_name)
    if not station:
        return f"Station '{station_name}' not found.", False

    weather = fetch_weather_data(station["latitude"], station["longitude"])
    if weather:
        return weather, True
    else:
        return "Weather data not available.", False

def record_station_query(station_name):
    """
    Increment the query count for a station in Redis.
    """
    redis_client.zincrby("station_queries", 1, station_name)

def get_top_queried_stations(limit=5):
    """
    Retrieve the top queried stations from Redis.
    """
    return redis_client.zrevrange("station_queries", 0, limit - 1, withscores=True)

# Streamlit interface
st.title("Metro Navigation System")

all_lines = get_all_lines()

# Section: Find Stations by Line
st.header("Stations by Line")
selected_line = st.selectbox("Select a Line", all_lines)

if st.button("Show Ordered Stations"):
    stations = get_stations_by_line(selected_line)
    if stations:
        st.success(f"Stations on {selected_line} (Ordered by Position):")
        for idx, station in enumerate(stations, start=1):
            st.write(f"{idx}. {station}")
    else:
        st.error(f"No stations found for {selected_line}.")

# Add some space between sections
st.markdown("---")

# Sidebar sections
st.sidebar.header("Distance Between Stations")
station1 = st.sidebar.text_input("Enter First Station Name", "")
station2 = st.sidebar.text_input("Enter Second Station Name", "")


if st.sidebar.button("Find Distance"):
    if not station1 or not station2:
        st.error("Please provide both station names.")
    else:
        distance, success = find_distance_between_stations(station1, station2)
        if success:
            st.success(f"The distance between {station1} and {station2} is {distance} km.")
        else:
            st.error(distance)

if st.sidebar.button("Find Shortest Route"):
    if not station1 or not station2:
        st.error("Please provide both the starting and destination station names.")
    else:
        route = shortest_path_between_stations(neo4j_driver, station1, station2)
        if route:
            st.success(f"The shortest route from {station1} to {station2} is:")
            st.write(" → ".join(route))
        else:
            st.error(f"No route found between {station1} and {station2}.")

st.sidebar.markdown("---")

st.sidebar.header("Weather for Stations")
station_names = get_all_station_names()

if station_names:
    selected_station = st.sidebar.selectbox("Select a Station", station_names)

    if st.sidebar.button("Show Weather"):
        weather, success = get_station_weather(selected_station)
        if success:
            st.success(f"Weather for {selected_station}:")
            st.write(f"Temperature: {weather['temperature']}°C")
            st.write(f"Wind Speed: {weather['windspeed']} km/h")
            st.write(f"Weather Code: {weather['weathercode']}")
        else:
            st.error(weather)
else:
    st.sidebar.error("No stations found in the database.")

# Section: Find Neighboring Stations
st.header("Neighboring Stations")
station_name_for_neighbors = st.text_input("Enter Station Name")

if st.button("Find Neighboring Stations"):
    if not station_name_for_neighbors:
        st.error("Please enter a station name.")
    else:
        neighbors = find_station_neighbors(neo4j_driver, station_name_for_neighbors)
        if neighbors:
            st.success(f"Stations directly connected to {station_name_for_neighbors}:")
            grouped_neighbors = {}
            for neighbor in neighbors:
                line = neighbor["line"]
                if line not in grouped_neighbors:
                    grouped_neighbors[line] = []
                grouped_neighbors[line].append(neighbor["neighbor"])

            for line, stations in grouped_neighbors.items():
                st.write(f"**Line {line}:**")
                for station in stations:
                    st.write(f"- {station}")
        else:
            st.warning(f"No neighbors found for {station_name_for_neighbors}.")

