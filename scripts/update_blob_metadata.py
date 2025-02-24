import os
from azure.storage.filedatalake import DataLakeServiceClient, DataLakeDirectoryClient, FileSystemClient
from dotenv import load_dotenv
import hashlib
import logging
import mimetypes
from azure.identity import DefaultAzureCredential

# Load environment variables from the .env file in the local directory
script_dir = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Print environment information
logger.info("Environment Information:")
logger.info(f"AZURE_STORAGE_ACCOUNT_NAME: {os.getenv('AZURE_STORAGE_ACCOUNT_NAME')}")
logger.info(f"AZURE_STORAGE_CONTAINER: {os.getenv('AZURE_STORAGE_CONTAINER')}")
logger.info(f"AZURE_TENANT_ID: {os.getenv('AZURE_TENANT_ID')}")
logger.info(f"Current Working Directory: {os.getcwd()}")
logger.info(f"Python Executable: {os.path.abspath(os.sys.executable)}")

def get_service_client_token_credential(account_name) -> DataLakeServiceClient:
    account_url = f"https://{account_name}.dfs.core.windows.net"
    token_credential = DefaultAzureCredential()

    service_client = DataLakeServiceClient(account_url, credential=token_credential)

    return service_client

def list_directory_contents(file_system_client: FileSystemClient, directory_name: str):
    paths = file_system_client.get_paths(path=directory_name)

    for path in paths:
        print(path.name + '\n')

# Function to calculate MD5 hash of a blob
def calculate_md5(blob_data):
    md5_hash = hashlib.md5()
    md5_hash.update(blob_data)
    return md5_hash.hexdigest()

# Function to get content type of a blob
def get_content_type(blob_name):
    return mimetypes.guess_type(blob_name)[0] or 'application/octet-stream'

# Function to update blob metadata and last modified timestamp
def update_blob_metadata_and_timestamp(file_client):
    try:
        file_data = file_client.download_file().readall()
        md5_hash = calculate_md5(file_data)
        content_type = get_content_type(file_client.path_name)
        sourceURL = 'https://mortgagemanuals.sharefile.com'
        
        metadata = {
            'md5': md5_hash,
            'isDeleted': 'false',
            'sourceURL': sourceURL,
            'content_type': content_type
        }
        
        file_client.set_metadata(metadata)
        logger.info(f"Metadata and timestamp updated for file: {file_client.path_name}")
    except Exception as e:
        logger.error(f"Failed to update metadata and timestamp for file: {file_client.path_name}, Error: {e}")

# Main function to iterate over files and update metadata
def main():
    # Get environment variables
    adls_account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
    filesystem_name = os.getenv("AZURE_STORAGE_CONTAINER")
    try:
        datalake_service_client = get_service_client_token_credential(adls_account_name)
        filesystem_client = datalake_service_client.get_file_system_client(filesystem_name)
        # list_directory_contents(filesystem_client, "Banker")
        # list_directory_contents(filesystem_client, "Broker Compliance")
        paths = filesystem_client.get_paths(recursive=True)
        for path in paths:
            if not path.is_directory:
                full_path = path.name
                file_client = filesystem_client.get_file_client(full_path)
                update_blob_metadata_and_timestamp(file_client)
    except Exception as e:
        logger.error(f"Failed to process files in filesystem: {filesystem_name}, Error: {e}")

if __name__ == "__main__":
    main()
