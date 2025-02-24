import os
from azure.storage.blob import BlobServiceClient
from load_azd_env import load_azd_env

# Load the Azure DevOps environment
load_azd_env()

# Connection string for Azure Storage
connection_string = os.getenv("BLOB_CONN_STR")

# Initialize the BlobServiceClient
blob_service_client = BlobServiceClient.from_connection_string(connection_string)

# Container name (specify if known)
container_name = os.getenv("BLOB_CONTAINER_NAME")  # Adjust this if you know your container name

# Determine the project root directory and set the download directory to the "data" folder one level up
project_root_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
download_directory = os.path.join(project_root_directory, 'data')

# Ensure the download directory exists
if not os.path.exists(download_directory):
    os.makedirs(download_directory)

# List all blobs in the container and download them
def download_blobs(container_name):
    container_client = blob_service_client.get_container_client(container_name)
    
    # List blobs in the container
    blob_list = container_client.list_blobs()
    
    for blob in blob_list:
        # Construct the full local path
        local_file_path = os.path.join(download_directory, blob.name)
        
        # Ensure the subdirectory exists
        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
        
        # Download the blob
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob.name)
        with open(local_file_path, "wb") as download_file:
            download_file.write(blob_client.download_blob().readall())
        print(f"Downloaded {blob.name} to {local_file_path}")

download_blobs(container_name)