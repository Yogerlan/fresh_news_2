import logging
import os
import re
from datetime import datetime
from hashlib import sha1

from RPA.Browser.Selenium import Selenium
from RPA.Calendar import Calendar
from RPA.Excel.Files import Files
from selenium.common.exceptions import (ElementClickInterceptedException,
                                        NoSuchElementException,
                                        StaleElementReferenceException)
from selenium.webdriver.common.by import By

OUTPUT_DIR = "output"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


class News:
    ATTEMPTS = 5

    def __init__(self, element, search_phrase, files):
        self.__element = element
        self.__search_phrase = search_phrase
        self.__files = files
        self.__get_title()
        self.__get_date()
        self.__get_description()
        self.__get_picture()
        self.__get_count()
        self.__get_money()

    def __get_title(self):
        """Gets the title"""
        attempts = self.ATTEMPTS

        while attempts:
            try:
                self.__title = self.__element.find_element(
                    by=By.CLASS_NAME,
                    value="PagePromo-title"
                ).find_element(
                    by=By.CLASS_NAME,
                    value="PagePromoContentIcons-text"
                ).text

                break
            except (NoSuchElementException, StaleElementReferenceException) as ex:
                attempts -= 1
                self.__title = ""
                logging.info(
                    f"News__get_title ({ex}) remaining attempts: {attempts}"
                )

    def __get_date(self):
        """Gets the date from timestamp"""
        attempts = self.ATTEMPTS

        while attempts:
            try:
                timestamp = self.__element.find_element(
                    by=By.TAG_NAME,
                    value="bsp-timestamp"
                ).get_attribute("data-timestamp")

                self.__date = datetime.fromtimestamp(
                    int(timestamp) // 1000
                ).strftime(DATE_FORMAT)

                break
            except (NoSuchElementException, StaleElementReferenceException) as ex:
                attempts -= 1
                self.__date = ""
                logging.info(
                    f"News__get_date ({ex}) remaining attempts: {attempts}"
                )

    def __get_description(self):
        """Gets the description"""
        attempts = self.ATTEMPTS

        while attempts:
            try:
                self.__description = self.__element.find_element(
                    by=By.CLASS_NAME,
                    value="PagePromo-description"
                ).find_element(
                    by=By.CLASS_NAME,
                    value="PagePromoContentIcons-text"
                ).text

                break
            except (NoSuchElementException, StaleElementReferenceException) as ex:
                attempts -= 1
                self.__description = ""
                logging.info(
                    f"News__get_description ({ex}) remaining attempts: {attempts}"
                )

    def __get_picture(self):
        """Gets the picture and saves it"""
        attempts = self.ATTEMPTS

        while attempts:
            try:
                picture_element = self.__element.find_element(
                    by=By.TAG_NAME,
                    value="img"
                )

                pic_bytes = picture_element.screenshot_as_png
                pic_sha1 = sha1(pic_bytes).hexdigest()
                picture = f"{pic_sha1}.png"

                with open(os.path.join(OUTPUT_DIR, picture), "wb") as f:
                    f.write(pic_bytes)

                self.__picture = picture

                break
            except NoSuchElementException as ex:
                logging.info(f"News__get_picture ({ex})")
                self.__picture = ""

                break
            except StaleElementReferenceException as ex:
                attempts -= 1
                self.__picture = ""
                logging.info(
                    f"News__get_picture ({ex}) remaining attempts: {attempts}"
                )

    def __get_count(self):
        """Counts the occurrences of the search phrase in the title and description"""
        self.__count = (self.__title.count(self.__search_phrase) +
                        self.__description.count(self.__search_phrase))

    def __get_money(self):
        """Detects money occurrences in the title or description"""
        """Possible formats: $11.1|$111,111.11|11 dollars|11 USD"""
        pattern = "|".join(["\$(\d|[1-9]\d*)\.\d($|\D)",
                            "\$(\d|[1-9]\d{0,2}(,\d{3})*)\.\d\d($|\D)",
                            "(^|\D)(\d|[1-9]\d*) dollars",
                            "(^|\D)(\d|[1-9]\d*) USD"])
        self.__money = (re.search(pattern, self.__title) or
                        re.search(pattern, self.__description)) is not None

    @property
    def date(self):
        return self.__date

    def save_elements(self):
        self.__files.append_rows_to_worksheet({
            "title": [self.__title],
            "date": [f"{self.__date}"],
            "description": [self.__description],
            "picture": [self.__picture],
            "count": [self.__count],
            "money": [f"{self.__money}"]
        })


class APNewsCollector:
    """
    News collector engine for THE ASSOCIATED PRESS website.

    The engine queries the site using a search phrase, then sorts and filters the results,
    and performs the news recollection.
    """

    URL = "https://apnews.com/"
    WB_PATH = os.path.join(OUTPUT_DIR, "apnews.xlsx")
    ATTEMPTS = 5
    ONE_TRUST_ACCEPT_BTN = "css:button#onetrust-accept-btn-handler"
    FANCYBOX_CLOSE_ANCHOR = "css:a.fancybox-item.fancybox-close"
    FAULTS_TOLERANCE = 5

    def __init__(self, search_phrase, categories="", months=0, sort_by="Newest", timeout=170):
        self.__search_phrase = search_phrase
        self.__categories = categories
        self.__months = months if months == 0 else months - 1
        now = datetime.now()
        self.__now = now.strftime(DATE_FORMAT)
        self.__timeout = now.timestamp() + timeout
        self.__sort_by = sort_by
        self.__selenium = Selenium()
        self.__calendar = Calendar()
        self.__files = Files()

    def collect_news(self):
        self.__files.create_workbook(self.WB_PATH, sheet_name="Fresh News")
        self.__files.append_rows_to_worksheet({
            "title": ["Title"],
            "date": ["Date"],
            "description": ["Description"],
            "picture": ["Picture"],
            "count": ["Count"],
            "money": ["Money"]
        })
        self.__open_website()
        self.__search_news()
        self.__filter_news()
        self.__get_news()
        self.__files.save_workbook()

    def __open_website(self):
        """Opens the browser instance & navigates to the news website"""
        self.__selenium.open_browser(
            self.URL,
            "headlessfirefox",
            service_log_path=os.path.join(OUTPUT_DIR, "geckodriver.log")
        )
        self.__selenium.set_selenium_implicit_wait(5)

    def __check_modals(self):
        # Accept onetrust modal
        if self.__selenium.is_element_visible(self.ONE_TRUST_ACCEPT_BTN):
            self.__selenium.click_button(self.ONE_TRUST_ACCEPT_BTN)
            logging.info("OneTrust modal accepted.")

        # Close fancybox modal
        if self.__selenium.is_element_visible(self.FANCYBOX_CLOSE_ANCHOR):
            self.__selenium.click_link(self.FANCYBOX_CLOSE_ANCHOR)
            logging.info("Fancybox modal closed.")

    def __secure_click_element(self, locator):
        attempts = self.ATTEMPTS

        while attempts:
            try:
                self.__selenium.click_element(locator)

                break
            except ElementClickInterceptedException as ex:
                self.__check_modals()
                attempts -= 1
                logging.exception(
                    f"APNewsCollector__secure_click_element ({ex}) remaining attempts: {attempts}"
                )
            except (NoSuchElementException, StaleElementReferenceException) as ex:
                attempts -= 1
                logging.exception(
                    f"APNewsCollector__secure_click_element ({ex}) remaining attempts: {attempts}"
                )

    def __secure_input_text(self, locator, text):
        attempts = self.ATTEMPTS

        while attempts:
            try:
                self.__selenium.input_text(
                    locator,
                    text
                )

                break
            except ElementClickInterceptedException as ex:
                self.__check_modals()
                attempts -= 1
                logging.exception(
                    f"APNewsCollector__secure_input_text ({ex}) remaining attempts: {attempts}"
                )
            except (NoSuchElementException, StaleElementReferenceException) as ex:
                attempts -= 1
                logging.exception(
                    f"APNewsCollector__secure_input_text ({ex}) remaining attempts: {attempts}"
                )

    def __secure_select_from_list_by_label(self, locator, labels):
        attempts = self.ATTEMPTS

        while attempts:
            try:
                self.__selenium.select_from_list_by_label(
                    locator,
                    labels
                )

                break
            except ElementClickInterceptedException as ex:
                self.__check_modals()
                attempts -= 1
                logging.exception(
                    f"APNewsCollector__secure_select_from_list_by_label ({ex}) remaining attempts: {attempts}"
                )
            except (NoSuchElementException, StaleElementReferenceException) as ex:
                attempts -= 1
                logging.exception(
                    f"APNewsCollector__secure_select_from_list_by_label ({ex}) remaining attempts: {attempts}"
                )

    def __search_news(self):
        """Seeks news using the search phrase"""
        self.__secure_click_element("css:button.SearchOverlay-search-button")
        self.__secure_input_text(
            'css:input.SearchOverlay-search-input[name="q"]',
            self.__search_phrase
        )
        self.__secure_click_element("css:button.SearchOverlay-search-submit")

    def __filter_news(self):
        """Sorts the search results & filters them by categories"""
        if self.__sort_by:
            self.__secure_select_from_list_by_label(
                'css:select.Select-input[name="s"]',
                self.__sort_by
            )

        categories = {category.lower()
                      for category in self.__categories.split(",")}
        found = True

        while found and len(categories):
            found = False
            self.__secure_click_element("css:div.SearchFilter-heading")

            for element in self.__selenium.get_webelements(
                "css:div.SearchFilterInput div.CheckboxInput label.CheckboxInput-label"
            ):
                element_text = element.text.lower()

                if element_text in categories:
                    self.__secure_click_element(element)
                    found = True
                    categories.remove(element_text)

                    break

    def __get_news(self):
        """Gets the news list within the requested months"""
        remaining_faults = self.FAULTS_TOLERANCE

        while remaining_faults > 0:
            for element in self.__selenium.get_webelements(
                "css:div.SearchResultsModule-results div.PageList-items-item"
            ):
                if datetime.now().timestamp() >= self.__timeout or not remaining_faults:
                    return

                self.__selenium.wait_until_page_contains_element(element, 5)
                news = News(element, self.__search_phrase, self.__files)

                if not news.date:
                    remaining_faults -= 1

                    continue

                months_diff = self.__calendar.time_difference_in_months(
                    news.date,
                    self.__now,
                )

                if months_diff > self.__months:
                    remaining_faults -= 1

                    continue

                news.save_elements()
                remaining_faults = self.FAULTS_TOLERANCE

            current, total = self.__selenium.get_webelement(
                "css:div.Pagination-pageCounts"
            ).text.split(" of ")

            if current < total:
                self.__secure_click_element("css:div.Pagination-nextPage")
            else:
                return
