import scrapy
from scrapy.selector import Selector
from urllib.parse import urljoin
from scrapy.crawler import CrawlerProcess
from scrapy import signals
from tqdm import tqdm  # Progress bar

import undetected_chromedriver as uc  # Avoid bot detection
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

MAX_DEPTH = 3  # Limit recursive crawling

class JSRenderedSitemapSpider(scrapy.Spider):
    name = "js_sitemap"

    def __init__(self, start_url=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if start_url is not None:
            self.start_urls = [start_url]
            self.allowed_domains = [start_url.split("//")[1].split("/")[0]]
        else:
            self.start_urls = []
            self.allowed_domains = []
        self.visited_urls = set()

        # Setup undetected Selenium WebDriver (Headless Mode)
        # If you want a visible browser for debugging, remove headless=True:
        self.driver = uc.Chrome(headless=True)

        # Initialize tqdm progress bar
        self.progress_bar = tqdm(
            desc="Crawling Progress",
            unit=" URL",
            dynamic_ncols=True
        )

    def parse(self, response):
        """Extracts all URLs from a JavaScript-rendered page with recursion control."""
        depth = response.meta.get('depth', 0)
        if depth > MAX_DEPTH:
            return  # Stop recursion at max depth
        
        self.visited_urls.add(response.url)
        
        # Load page with Selenium
        try:
            self.driver.get(response.url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except Exception as e:
            self.logger.warning(f"Timeout or error loading {response.url}: {e}")
            return

        # Get the rendered page source via Selenium
        sel = Selector(text=self.driver.page_source)

        # Extract all links and follow them
        for link in sel.css("a::attr(href)").getall():
            absolute_url = urljoin(response.url, link)
            # Only follow internal links (within start_url domain) and avoid repeats
            if (absolute_url.startswith(self.start_urls[0]) 
                and absolute_url not in self.visited_urls):
                
                self.visited_urls.add(absolute_url)
                self.progress_bar.update(1)  # Update progress bar
                
                yield scrapy.Request(
                    url=absolute_url,
                    callback=self.parse,
                    meta={'depth': depth + 1}
                )

    def closed(self, reason):
        """Ensure Selenium WebDriver and progress bar are properly closed."""
        self.driver.quit()
        self.progress_bar.close()


def get_sitemap_urls(base_url):
    """
    Runs the Scrapy + Selenium crawler synchronously and returns a list of URLs.
    Uses signals to retrieve the spider’s visited URLs.
    """
    # We'll capture the spider’s visited_urls here once the crawl is done.
    collected_urls = {}

    def spider_closed(spider, reason):
        # Copy spider.visited_urls into our local dictionary
        collected_urls["visited"] = spider.visited_urls

    process = CrawlerProcess(settings={
        "LOG_LEVEL": "INFO",
        "ROBOTSTXT_OBEY": False,  # or True, depending on your needs
    })

    # Create a Crawler instance from our spider class
    crawler = process.create_crawler(JSRenderedSitemapSpider)

    # Connect the spider_closed signal so we can retrieve the spider’s data
    crawler.signals.connect(spider_closed, signal=signals.spider_closed)

    # Schedule our spider for a run. Here we pass the 'start_url' argument.
    process.crawl(crawler, start_url=base_url)

    # This will run the spider (blocking call) until it finishes
    process.start()

    # Return the collected URLs (sorted)
    return sorted(collected_urls.get("visited", []))


if __name__ == "__main__":
    sitemap_urls = get_sitemap_urls("https://www.a1bestplumbing.com/")
    print(f'Crawled URLs: {len(sitemap_urls)}')
    for url in sitemap_urls:
        print(url)
