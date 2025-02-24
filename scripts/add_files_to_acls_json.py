import os
import json

# Path to the existing JSON file
json_file_path = 'c:/Code/Entelligage/pai-mortgagemanuals-prod/scripts/sampleacls.json'

# Load the existing JSON structure
with open(json_file_path, 'r') as file:
    data = json.load(file)

# Path to the directory containing data
data_directory = 'c:/Code/Entelligage/pai-mortgagemanuals-prod/data/'

# Initialize the 'files' dictionary if not already present
data.setdefault('files', {})

# Function to add files and subdirectories to the JSON data
def add_files_and_subdirectories(parent_directory, parent_directory_name):
    # Walk through the directory and its subdirectories
    for dirpath, _, filenames in os.walk(parent_directory):
        # Compute the relative directory path from the data directory
        relative_dir = os.path.relpath(dirpath, data_directory).replace("\\", "/")
        
        # Skip processing if relative_dir is just ".", which corresponds to the root of data_directory
        if relative_dir == ".":
            continue
        
        # Ensure the subdirectory is recorded in 'directories' with inherited groups
        if relative_dir not in data['directories']:
            data['directories'][relative_dir] = {
                "groups": data['directories'].get(parent_directory_name, {}).get("groups", [])
            }
        
        # Add each file to the 'files' dictionary with directory information
        for file_name in filenames:
            data['files'][file_name] = {
                "directory": relative_dir
            }

# Iterate over a copy of the directory keys in the JSON structure
for directory_name in list(data['directories'].keys()):
    if directory_name == '/':
        continue

    # Full path to the directory
    directory_path = os.path.join(data_directory, directory_name)
    
    # Check if the directory exists and add files and subdirectories
    if os.path.exists(directory_path):
        add_files_and_subdirectories(directory_path, directory_name)

# Convert any double backslashes to forward slashes in existing files' directory paths
for file_info in data['files'].values():
    file_info['directory'] = file_info['directory'].replace("\\", "/")

# Save the updated JSON structure back to the file
with open(json_file_path, 'w') as file:
    json.dump(data, file, indent=4)

print("JSON file updated with subdirectories, forward slashes, and directory information.")