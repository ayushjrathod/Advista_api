from db import AstraDB
from dotenv import load_dotenv
import os

def main():
    load_dotenv()
    admin_token = os.getenv('ASTRA_DB_ADMIN_TOKEN')
    if not admin_token:
        raise ValueError("ASTRA_DB_ADMIN_TOKEN not set in .env")
    
    AstraDB.setup_database(admin_token)
    print("Database setup complete")

if __name__ == "__main__":
    main()
