from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import json

# MongoDB connection details
username = "followalong"
password = "Password123"
cluster_url = "cluster0.3d5bm.mongodb.net"

# Connection URI
uri = f"mongodb+srv://{username}:{password}@{cluster_url}/?retryWrites=true&w=majority"


def connect_to_mongodb():
    """
    Connect to the MongoDB database and return the client instance.
    """
    client = MongoClient(uri, server_api=ServerApi('1'))
    try:
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
    return client


def insert_metro_data(client, file_path='metro.json'):
    """
    Insert metro data from a JSON file into MongoDB.
    Args:
        client: The MongoDB client instance.
        file_path: Path to the JSON file containing metro data.
    """
    try:
        # Access the database and collection
        db = client['metro_data']
        collection = db['stations']

        # Load data from JSON file
        with open(file_path, 'r') as file:
            data = json.load(file)

        # Insert data into MongoDB
        collection.insert_many(data['nodes'])
        print("Data inserted successfully.")
    except Exception as e:
        print(f"Error during data insertion: {e}")


def fetch_sample_documents(client, limit=5):
    """
    Fetch and print a sample of documents from the MongoDB collection.
    Args:
        client: The MongoDB client instance.
        limit: Number of documents to fetch (default is 5).
    """
    try:
        collection = client['metro_data']['stations']
        documents = collection.find().limit(limit)
        for doc in documents:
            print(doc)
    except Exception as e:
        print(f"Error during data fetch: {e}")


def search_station(db, name):
    """
    Search for a station in MongoDB by name.
    Args:
        db: The MongoDB database instance.
        name: The station name to search for.
    Returns:
        A dictionary with the station details if found, else None.
    """
    try:
        collection = db["stations"]  # Replace "stations" with your actual collection name if different
        return collection.find_one({"text": {"$regex": name, "$options": "i"}})
    except Exception as e:
        print(f"Error during station search: {e}")
        return None


if __name__ == "__main__":
    # Connect to MongoDB and perform operations
    client = connect_to_mongodb()
    if client:
        insert_metro_data(client)
        fetch_sample_documents(client)

        # Example search
        db = client['metro_data']
        station_name = "George V"
        station = search_station(db, station_name)
        if station:
            print(f"Station found: {station}")
        else:
            print("Station not found.")
