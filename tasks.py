import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

from robocorp import workitems
from robocorp.tasks import task
from RPA.Browser.Selenium import Selenium
from RPA.HTTP import HTTP

from utils import convert_timestamp_to_datetime, load_config, save_to_excel

# setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%d-%m-%Y %H:%M:%S",
)
logger = logging.getLogger(__name__)


class NewsScraper:
    def __init__(self):
        self.browser = Selenium(auto_close=False)
        self.http = HTTP()

    def apply_search_phrase(self, search_phrase):
        try:
            # toggle search input box
            search_btn_locator = "css:button[data-element='search-button']"
            self.browser.wait_until_element_is_visible(search_btn_locator, timeout=15)
            self.browser.click_button(search_btn_locator)

            # input search phrase
            query_input_locator = "css:input[data-element='search-form-input']"
            self.browser.wait_until_element_is_enabled(query_input_locator, timeout=15)
            self.browser.input_text(query_input_locator, search_phrase)

            # click on submit button
            search_submit_locator = "css:button[data-element='search-submit-button']"
            self.browser.wait_until_element_is_visible(
                search_submit_locator, timeout=15
            )
            self.browser.click_button(search_submit_locator)

            logger.info("successfully applied search phrase")
        except AssertionError as e:
            logger.error(
                f"could not apply search phrase due to the following error: {e}"
            )
            raise

    def apply_category_filter(self, category):
        try:
            # click on category input checkbox
            category_locator = f"//label[span[text()='{category}']]/input"
            self.browser.wait_until_element_is_enabled(category_locator, timeout=15)
            self.browser.click_element(category_locator)

            logger.info("successfully applied category filter")
        except AssertionError as e:
            logger.error(
                f"could not apply category filter due to the following error: {e}"
            )

    def get_news_articles(self, search_phrase, category, end_date, max_pages):
        self.browser.open_available_browser("https://www.latimes.com/")
        self.browser.maximize_browser_window()

        self.apply_search_phrase(search_phrase)

        if category:
            logger.info(f"category filter to apply: {category}")
            self.apply_category_filter(category)
        else:
            logger.info("category was not provided")

        news_articles = []

        current_page = 1
        while current_page <= max_pages:
            logger.info(f"extracting news articles from page # {current_page}")

            news_item_locator = "data:content-type:article"
            self.browser.wait_until_element_is_enabled(news_item_locator, timeout=15)
            news_items = self.browser.find_elements(news_item_locator)
            for item_idx, news_item in enumerate(news_items):
                # to handle stale element error
                news_item = self.browser.find_elements(news_item_locator)[item_idx]

                news_timestamp = self.browser.find_element(
                    "css:p.promo-timestamp", news_item
                ).get_attribute("data-timestamp")
                news_date = convert_timestamp_to_datetime(news_timestamp)
                if news_date < end_date:
                    continue

                news_title = self.browser.find_element(
                    "css:h3.promo-title", news_item
                ).text.strip()

                news_description = self.browser.find_element(
                    "css:p.promo-description", news_item
                ).text.strip()

                news_text = news_title + " " + news_description
                news_text = news_text.lower()
                search_phrase_count = news_text.count(search_phrase.lower())
                contains_money = bool(
                    re.search(
                        r"\$[\d,.]+|\d+\s*(dollars|USD)", news_text, re.IGNORECASE
                    )
                )

                news_image = self.browser.find_element("css:img.image", news_item)
                news_image_url = news_image.get_attribute("src")
                file_name = news_image_url.split("%2F")[-1]

                # download image
                self.http.download(news_image_url, str(Path("output", file_name)))

                news_articles.append(
                    {
                        "title": news_title,
                        "date": news_date.strftime("%d-%m-%Y"),
                        "description": news_description,
                        "file_name": file_name,
                        "search_phrase_count": search_phrase_count,
                        "contains_money": contains_money,
                    }
                )

            # handling pagination
            next_page_locator = "css:div.search-results-module-next-page a"
            try:
                current_page += 1

                if current_page <= max_pages:
                    self.browser.wait_until_element_is_enabled(
                        next_page_locator, timeout=5
                    )
                    self.browser.click_element(next_page_locator)
            except AssertionError:
                logger.error(f"could not find next page, skipping next pages")
                break

        return news_articles

    def run_scraper(self):
        work_item = workitems.inputs.current
        payload = work_item.payload

        if payload:  # read process parameters from work item
            search_phrase = payload["search_phrase"]
            category = payload.get("category", "")
            months = int(payload.get("months", 0))
            max_pages = payload.get("max_pages", None)
            logger.info("successfully read process parameters from work item")
            if max_pages:
                max_pages = int(max_pages)
                logger.info(f"max_pages set to {max_pages}")
            else:
                max_pages = 5
                logger.warning(
                    f"max_pages parameter was not provided, defaulting to max_pages={max_pages}"
                )
        else:  # read process parameters from config file
            config_file = Path("config/config.json")
            config = load_config(config_file)
            search_phrase = config["search_phrase"]
            category = config["category"]
            months = config["months"]
            max_pages = config["max_pages"]
            logger.info("successfully read process parameters from config file")

        current_datetime = datetime.now()
        if months == 0:
            end_date = current_datetime - timedelta(days=30)
        else:
            end_date = current_datetime - timedelta(days=30 * months)

        logging.info(
            f"scraping news articles for the search phrase: {search_phrase} from {current_datetime.strftime('%d-%m-%Y')} till {end_date.strftime('%d-%m-%Y')}"
        )

        try:
            news_articles = self.get_news_articles(
                search_phrase, category, end_date, max_pages
            )
            save_to_excel(news_articles)
            logger.info("successfully saved scraped articles into excel file")
        except Exception as e:
            logger.error(f"uncaught exception: {e}")
            raise
        finally:
            self.browser.close_browser()


@task
def main():
    scraper = NewsScraper()
    scraper.run_scraper()
