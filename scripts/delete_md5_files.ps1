# Define the parent folder path
$parentFolderPath = "C:\Code\Entelligage\pai-mortgagemanuals-prod\data"

# Get all .md5 files in the folder and subfolders
$md5Files = Get-ChildItem -Path $parentFolderPath -Recurse -Filter "*.md5"

# Delete each .md5 file
foreach ($file in $md5Files) {
    Remove-Item -Path $file.FullName -Force
}

Write-Host "All .md5 files have been deleted from $parentFolderPath and its subfolders."