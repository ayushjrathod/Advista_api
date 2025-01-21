from astrapy.db import AstraDB
from dotenv import load_dotenv
import os
import json
import multiprocessing
import os
import subprocess
from astrapy import DataAPIClient
from astrapy.constants import VectorMetric
def main():
    load_dotenv()
    token = os.getenv('ASTRA_DB_TOKEN')
    
    if not token:
        raise ValueError("ASTRA_DB_TOKEN not set in .env")
    
    
    client = DataAPIClient(os.environ["ASTRA_DB_TOKEN"])
    database = client.get_database("https://f1709d77-1fe2-47f5-b976-1261a15c3375-us-east1.apps.astra.datastax.com")
    collection = database.get_collection("sessions")
    print(collection)
    

if __name__ == "__main__":
    main()