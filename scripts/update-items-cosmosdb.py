from azure.cosmos import CosmosClient
from typing import Union
import os
from load_azd_env import load_azd_env
from azure.identity import DefaultAzureCredential

# Load the Azure DevOps environment
load_azd_env()

USE_CHAT_HISTORY_COSMOS = os.getenv("USE_CHAT_HISTORY_COSMOS", "").lower() == "true"
AZURE_COSMOSDB_ACCOUNT = os.getenv("AZURE_COSMOSDB_ACCOUNT")
AZURE_CHAT_HISTORY_DATABASE = os.getenv("AZURE_CHAT_HISTORY_DATABASE")
AZURE_CHAT_HISTORY_CONTAINER = os.getenv("AZURE_CHAT_HISTORY_CONTAINER")

# Initialize the Azure credential
azure_credential = DefaultAzureCredential()

if USE_CHAT_HISTORY_COSMOS:
    if not AZURE_COSMOSDB_ACCOUNT:
        raise ValueError("AZURE_COSMOSDB_ACCOUNT must be set when USE_CHAT_HISTORY_COSMOS is true")
    if not AZURE_CHAT_HISTORY_DATABASE:
        raise ValueError("AZURE_CHAT_HISTORY_DATABASE must be set when USE_CHAT_HISTORY_COSMOS is true")
    if not AZURE_CHAT_HISTORY_CONTAINER:
        raise ValueError("AZURE_CHAT_HISTORY_CONTAINER must be set when USE_CHAT_HISTORY_COSMOS is true")
    
    cosmos_client = CosmosClient(url=f"https://{AZURE_COSMOSDB_ACCOUNT}.documents.azure.com:443/", credential=azure_credential)
    cosmos_db = cosmos_client.get_database_client(AZURE_CHAT_HISTORY_DATABASE)
    container = cosmos_db.get_container_client(AZURE_CHAT_HISTORY_CONTAINER)

    # Query to get all documents
    query = "SELECT * FROM c"

    # Iterate through all documents and update each one to include the isDeleted field
    for item in container.query_items(query, enable_cross_partition_query=True):
        item['isDeleted'] = 0
        container.upsert_item(item)

    print("All documents have been updated to include the isDeleted field with a value of 0.")
else:
    print("USE_CHAT_HISTORY_COSMOS is not set to true. No updates were made.")