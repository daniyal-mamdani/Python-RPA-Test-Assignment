import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from robocorp.tasks import task
from RPA.Browser.Selenium import Selenium
from RPA.HTTP import HTTP

# setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class NewsScraper:
    def __init__(self):
        self.browser = Selenium(auto_close=False)
        self.http = HTTP()

    def load_config(self, config_file):
        with open(config_file) as f:
            return json.load(f)

    def convert_timestamp_to_datetime(self, timestamp):
        timestamp_seconds = int(timestamp) / 1000
        return datetime.fromtimestamp(timestamp_seconds)

    def get_search_results(
        self, search_phrase: str, category: str, end_date: datetime, max_pages=3
    ) -> list:
        self.browser.open_available_browser("https://www.latimes.com/")
        self.browser.maximize_browser_window()

        # enter search phrase in search box
        search_btn_locator = "css:button[data-element='search-button']"
        self.browser.wait_until_element_is_visible(search_btn_locator, timeout=15)
        self.browser.click_button(search_btn_locator)

        query_input_locator = "css:input[data-element='search-form-input']"
        self.browser.wait_until_element_is_enabled(query_input_locator, timeout=15)
        self.browser.input_text(query_input_locator, search_phrase)

        search_submit_locator = "css:button[data-element='search-submit-button']"
        self.browser.wait_until_element_is_visible(search_submit_locator, timeout=15)
        self.browser.click_button(search_submit_locator)

        if category:
            # apply category filter
            category_filter_locator = f"//label[span[text()='{category}']]/input"
            self.browser.wait_until_element_is_enabled(
                category_filter_locator, timeout=15
            )
            self.browser.click_element(category_filter_locator)

        news_articles = []

        current_page = 1
        while True:
            if current_page >= max_pages:
                break

            logger.info(f"On page -> {current_page}")

            # wait for results to load
            self.browser.wait_until_element_is_visible(
                "data:content-type:article", timeout=15
            )

            # using bs4 to parse news articles
            parsed_items = self.parse_articles(search_phrase, end_date)

            news_articles += parsed_items

            # handling pagination
            try:
                next_page_locator = "css:div.search-results-module-next-page a"
                self.browser.wait_until_element_is_enabled(next_page_locator, timeout=5)
                self.browser.click_element(next_page_locator)

                current_page += 1
            except:
                break

        return news_articles

    def parse_articles(self, search_phrase: str, end_date: datetime) -> list:
        soup = BeautifulSoup(self.browser.get_source(), "html.parser")

        news_items = []
        articles = soup.find_all("ps-promo", {"data-content-type": "article"})
        for article in articles:
            timestamp = article.find("p", {"class": "promo-timestamp"})[
                "data-timestamp"
            ]
            date = self.convert_timestamp_to_datetime(timestamp)
            if date < end_date:
                continue

            title = article.find("h3", {"class": "promo-title"}).text.strip()
            description = article.find("p", {"class": "promo-description"}).text.strip()
            image = article.find("img", {"class": "image"})
            image_src = image["src"]
            image_name = image_src.split("%2F")[-1]

            news_content = title + " " + description
            news_content = news_content.lower()
            search_phrase_count = news_content.count(search_phrase.lower())
            has_money = bool(
                re.search(r"\$[\d,.]+|\d+\s*(dollars|USD)", news_content, re.IGNORECASE)
            )

            news_items.append(
                {
                    "title": title,
                    "description": description,
                    "date": date.strftime("%d-%m-%Y"),
                    "img_url": image_src,
                    "img_name": image_name,
                    "phrase_count": search_phrase_count,
                    "contains_money": has_money,
                }
            )

        return news_items

    def save_to_excel(self, news_items):
        output_file = Path("output/news_articles.xlsx")
        for news_item in news_items:
            image_src = news_item["img_url"]
            file_name = news_item["img_name"]
            self.http.download(image_src, str(Path("output", file_name)))

        df = pd.DataFrame(news_items)
        df.drop(columns=["img_url"], inplace=True)
        output_file = Path("output/news_articles.xlsx")
        df.to_excel(output_file, index=False, header=True)

    def run_scraper(self):
        try:
            config = self.load_config("config/config.json")
            search_phrase = config["search_phrase"]
            category = config["category"]
            months = config["months"]

            if months == 0:
                end_date = datetime.now() - timedelta(days=30)
            else:
                end_date = datetime.now() - timedelta(days=30 * months)

            news_articles = self.get_search_results(search_phrase, category, end_date)
            self.save_to_excel(news_articles)

            logger.info("Scraping and data extraction completed successfully.")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            raise
        finally:
            self.browser.close_browser()


@task
def main():
    scraper = NewsScraper()
    scraper.run_scraper()
