from neo4j import GraphDatabase
import json
from math import radians, sin, cos, sqrt, atan2

# Neo4j connection details
URI = "replace with your details.databases.neo4j.io"
AUTH = ("neo4j", "replace with your password")


# Establish connection to Neo4j
def connect_to_neo4j():
    """
    Connect to the Neo4j database and return the driver instance.
    """
    driver = GraphDatabase.driver(URI, auth=AUTH)
    try:
        driver.verify_connectivity()
        print("Connected to Neo4j successfully!")
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}")
        driver = None
    return driver


# Load metro data from a JSON file
def load_metro_data(file_path):
    """
    Load metro data from the given JSON file with UTF-8 encoding.
    Args:
        file_path: Path to the JSON file.
    Returns:
        List of nodes (stations) from the file.
    """
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)
    print(f"Loaded {len(data['nodes'])} stations from {file_path}.")
    return data["nodes"]


# Bulk insert nodes into Neo4j
def bulk_insert_nodes(tx, nodes):
    """
    Insert stations as nodes into the Neo4j database.
    Args:
        tx: The transaction instance.
        nodes: List of station nodes to insert.
    """
    query = """
    UNWIND $nodes AS node
    MERGE (s:Station {id: node.id})
    SET s.name = node.text,
        s.longitude = node.longitude,
        s.latitude = node.latitude,
        s.size = node.size,
        s.x = node.x,
        s.y = node.y,
        s.visited = COALESCE(node.visited, false)
    """
    tx.run(query, nodes=nodes)


# Generate relationships based on proximity
def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points on the Earth in km.
    Args:
        lat1, lon1: Latitude and longitude of the first point.
        lat2, lon2: Latitude and longitude of the second point.
    Returns:
        Distance in kilometers.
    """
    R = 6371  # Earth's radius in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon1 - lon2)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


def generate_relationships(stations, distance_threshold=1.5):
    """
    Generate relationships between stations based on proximity.
    Args:
        stations: List of station nodes.
        distance_threshold: Maximum distance (in km) to create a relationship.
    Returns:
        List of relationships with distance details.
    """
    relationships = []
    for i, station1 in enumerate(stations):
        for j, station2 in enumerate(stations):
            if i >= j:  # Avoid duplicate pairs and self-relations
                continue
            distance = haversine(
                station1["latitude"], station1["longitude"],
                station2["latitude"], station2["longitude"]
            )
            if distance <= distance_threshold:
                relationships.append({
                    "from": station1["id"],
                    "to": station2["id"],
                    "distance": distance,
                    "line": "default"  # Replace with actual line data if available
                })
    return relationships


# Bulk insert relationships into Neo4j
def bulk_insert_relationships(tx, relationships):
    """
    Insert relationships between stations into the Neo4j database.
    Args:
        tx: The transaction instance.
        relationships: List of relationships to insert.
    """
    query = """
    UNWIND $relationships AS rel
    MATCH (a:Station {id: rel.from}), (b:Station {id: rel.to})
    CREATE (a)-[:CONNECTED_TO {distance: rel.distance, line: rel.line}]->(b)
    """
    tx.run(query, relationships=relationships)


# Get connected stations for a specific station
def get_connected_stations(driver, station_name):
    """
    Retrieve connected stations for a given station with distances.
    Args:
        driver: The Neo4j driver instance.
        station_name: Name of the station to search connections for.
    Returns:
        List of connected stations with their details, including distances.
    """
    query = """
    MATCH (start:Station {name: $station_name})-[r:CONNECTED_TO]->(neighbor)
    RETURN DISTINCT neighbor.name AS name, neighbor.latitude AS latitude,
                    neighbor.longitude AS longitude, r.distance AS distance
    """
    with driver.session() as session:
        result = session.run(query, station_name=station_name)
        return [
            {
                "name": record["name"],
                "latitude": record["latitude"],
                "longitude": record["longitude"],
                "distance": record["distance"],
            }
            for record in result
        ]



# Find the shortest route between two stations
def find_shortest_route(driver, start_station, end_station):
    """
    Find the shortest route between two stations.
    Args:
        driver: The Neo4j driver instance.
        start_station: Name of the starting station.
        end_station: Name of the destination station.
    Returns:
        List of station names in the shortest route.
    """
    query = """
    MATCH (start:Station {name: $start_station}), (end:Station {name: $end_station})
    MATCH path = shortestPath((start)-[:CONNECTED_TO*]-(end))
    RETURN [node IN nodes(path) | node.name] AS stations
    """
    with driver.session() as session:
        result = session.run(query, start_station=start_station, end_station=end_station)
        for record in result:
            return record["stations"]  # Return the station names in the shortest path
    return None


# Execute a query in Neo4j
def execute_query(driver, query):
    """
    Execute a query on the Neo4j database and return the results.
    Args:
        driver: The Neo4j driver instance.
        query: The Cypher query to execute.
    Returns:
        List of query results.
    """
    with driver.session() as session:
        result = session.run(query)
        return [record for record in result]

def get_neo4j_driver():
    """
    Return the Neo4j driver instance to be used in the Streamlit app.
    """
    return connect_to_neo4j()

if __name__ == "__main__":
    # Connect to Neo4j
    driver = connect_to_neo4j()

    if driver is not None:
        # Load data
        file_path = "metro.json"
        nodes = load_metro_data(file_path)

        # Insert nodes into Neo4j
        with driver.session() as session:
            session.execute_write(bulk_insert_nodes, nodes)
        print(f"Inserted {len(nodes)} stations into Neo4j.")

        # Generate relationships
        relationships = generate_relationships(nodes, distance_threshold=1.5)
        print(f"Generated {len(relationships)} relationships.")

        # Insert relationships into Neo4j
        with driver.session() as session:
            session.execute_write(bulk_insert_relationships, relationships)
        print(f"Inserted {len(relationships)} relationships into Neo4j.")

        # Example: Count stations
        query = "MATCH (s:Station) RETURN count(s) AS station_count"
        results = execute_query(driver, query)
        for record in results:
            print(f"Number of Station nodes: {record['station_count']}")

        # Example: Retrieve connected stations
        print("Connected stations:", get_connected_stations(driver, "Central Station"))
