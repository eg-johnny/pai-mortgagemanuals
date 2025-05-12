import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
from urllib.parse import urlparse, urljoin
from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig

from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
import hashlib
import logging
import requests
from bs4 import BeautifulSoup
from sitemap_spider import get_sitemap_urls

## REMINDER ##
# In order for this to work you must run post-installation setup crawl4ai-setup and crawl4ai-doctor to verify

# Set environment variables
os.environ['ComSpec'] = 'C:\\Windows\\System32\\cmd.exe'
os.environ['SystemRoot'] = 'C:\\Windows'

# Load environment variables from the .env file in the local directory
script_dir = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

# Get environment variables
# connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
# container_name = os.getenv("AZURE_STORAGE_CONTAINER")

# Configure logging
logging.basicConfig(
    level=logging.ERROR,  # Change log level to ERROR
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("crawl.log")
        #,logging.StreamHandler()
    ]
)

# Initialize the BlobServiceClient
# blob_service_client = BlobServiceClient.from_connection_string(connection_string)
# scrape_container_client = blob_service_client.get_container_client(container_name)

def md5_hash(data):
    if isinstance(data, bytes):
        return hashlib.md5(data).hexdigest()
    return hashlib.md5(data.encode('utf-8')).hexdigest()

def format_file_name(url):
    parsed_url = urlparse(url)
    path = parsed_url.path.strip('/').replace('/', '_')
    return f"../data/Web_Markdown/{path if path else parsed_url.netloc}.md"

def store_data(url, data):
    file_name = format_file_name(url)
    new_md5 = md5_hash(data)

    if os.path.exists(file_name):
        with open(file_name, 'rb') as f:
            existing_md5 = md5_hash(f.read())
        if new_md5 == existing_md5:
            return

    os.makedirs(os.path.dirname(file_name), exist_ok=True)
    with open(file_name, 'w', encoding='utf-8') as f:
        f.write(data)


def get_page_urls_from_sitemap(sitemap_url):
    page_urls = []

    try:
        response = requests.get(sitemap_url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'lxml')
            page_urls = [loc.text for loc in soup.find_all('loc')]
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to retrieve sitemap: {e}")

    # page_urls = ['https://coastlineclean.com']
    return page_urls

async def main():
    base_url = input("Enter the base URL: ")
    sitemap_urls = get_sitemap_urls(base_url)
    print(sitemap_urls)
    # to_visit = []

    # for sitemap_url in sitemap_urls:
    #     to_visit.extend(get_page_urls_from_sitemap(sitemap_url))

    # Configure the crawler run
    crawler_run_config = CrawlerRunConfig(
        # extraction_strategy=None,  # Disable JSON extraction
        check_robots_txt=True,
        stream=True,
        cache_mode=CacheMode.BYPASS,
    )

    # Create the crawler instance
    # async with AsyncWebCrawler(config=browser_config) as crawler:
    #     results = await crawler.arun_many(
    #         urls=to_visit,
    #         config=crawler_run_config,
    #     )

    async with AsyncWebCrawler() as crawler:
        # Stream results as they complete
        async for result in await crawler.arun_many(urls=sitemap_urls, config=crawler_run_config):
            if result.success:
                if result.markdown:
                    print(f"[OK] {result.url}, length: {len(result.markdown)}")
                    markdown_text = result.markdown
                    # print(markdown_text)
                    store_data(result.url, markdown_text)
                else:
                    print(f"[OK] {result.url}, no markdown available")
            else:
                print(f"[ERROR] {result.url} => {result.error_message}")
    

if __name__ == "__main__":
    asyncio.run(main())
