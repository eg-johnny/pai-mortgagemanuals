import msal
import requests
import os
from dotenv import load_dotenv

# Determine the directory of the current script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Specify the path to the .env file in the current script directory
env_path = os.path.join(script_dir, '.env')

# Load environment variables from the specified .env file
load_dotenv(dotenv_path=env_path)

# Replace these values with your app registration details
client_id = os.getenv("AZURE_CLIENT_APP_ID")
client_secret = os.getenv("AZURE_CLIENT_APP_SECRET") 
server_id = os.getenv("AZURE_SERVER_APP_ID")
resource_id="00000003-0000-0000-c000-000000000000" # MS GRAPH API
tenant_id = os.getenv("EXTERNAL_TENANT_ID")
authority = f"https://{tenant_id}.ciamlogin.com/{tenant_id}"
scope = ["https://graph.microsoft.com/.default"]

# Create a confidential client application
app = msal.ConfidentialClientApplication(
    client_id,
    authority=authority,
    client_credential=client_secret,
)

# Acquire a token for the Microsoft Graph API
result = app.acquire_token_for_client(scopes=scope)

if "access_token" in result:
    access_token = result["access_token"]
else:
    raise Exception("Could not acquire access token")

# Define the API endpoint and headers
api_endpoint = f"https://graph.microsoft.com/v1.0/oauth2PermissionGrants"
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json",
}

# Define the payload for granting admin consent
payload = {
    "clientId": client_id,  # The client ID of the application
    "consentType": "AllPrincipals",  # Grant consent for all users in the tenant
    "resourceid": resource_id,
    "scope": "User.Read",  # The scopes to grant consent for
}

# Make the API request to grant admin consent
response = requests.post(api_endpoint, headers=headers, json=payload)

if response.status_code == 201:
    print("Admin consent granted successfully")
else:
    print(f"Failed to grant admin consent: {response.status_code} - {response.text}")
