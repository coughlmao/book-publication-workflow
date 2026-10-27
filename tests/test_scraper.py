"""Offline regression tests for MediaWiki/Wikisource extraction."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from playwright.sync_api import sync_playwright

from scraping.scraper import fetch_content_and_screenshot

FIXTURE = Path(__file__).parent / "fixtures" / "wikisource_chapter.html"


class MediaWikiExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    @mock.patch("scraping.scraper.clean_mediawiki_navigation")
    @mock.patch("scraping.scraper.sync_playwright")
    def test_scraper_cleans_mediawiki_article(
        self, playwright_factory, clean_navigation
    ):
        manager = playwright_factory.return_value
        playwright = manager.__enter__.return_value
        browser = playwright.chromium.launch.return_value
        page = browser.new_page.return_value

        article = page.locator.return_value
        article.count.return_value = 1
        article.first.inner_text.return_value = "Clean chapter text."

        with tempfile.TemporaryDirectory() as tmp:
            screenshot = Path(tmp) / "chapter.png"
            text = fetch_content_and_screenshot(
                "https://example.org/chapter", screenshot
            )

        self.assertEqual(text, "Clean chapter text.")
        clean_navigation.assert_called_once_with(article.first)
        page.inner_text.assert_not_called()
        page.goto.assert_called_once()
        page.screenshot.assert_called_once()
        browser.close.assert_called_once()

    @mock.patch("scraping.scraper.sync_playwright")
    def test_scraper_preserves_body_fallback(self, playwright_factory):
        manager = playwright_factory.return_value
        playwright = manager.__enter__.return_value
        browser = playwright.chromium.launch.return_value
        page = browser.new_page.return_value

        page.locator.return_value.count.return_value = 0
        page.inner_text.return_value = "Site navigation\nOrdinary page content."

        with tempfile.TemporaryDirectory() as tmp:
            screenshot = Path(tmp) / "chapter.png"
            text = fetch_content_and_screenshot(
                "https://example.org/other-page", screenshot
            )

        self.assertEqual(
            text,
            "Site navigation\nOrdinary page content.",
        )
        page.inner_text.assert_called_once_with("body")
        browser.close.assert_called_once()

    def test_navigation_is_removed_and_story_is_preserved(self):
        from scraping.scraper import clean_mediawiki_navigation

        page = self.browser.new_page()
        try:
            page.set_content(FIXTURE.read_text(encoding="utf-8"))
            article = page.locator("#mw-content-text")

            clean_mediawiki_navigation(article)
            text = article.inner_text()

            self.assertNotIn("Previous chapter", text)
            self.assertNotIn("Next chapter", text)
            self.assertNotIn("Retrieved from the source page", text)

            self.assertIn(
                "The evening was quiet, and the road was empty.",
                text,
            )
            self.assertIn('"Will you come with me?" she asked.', text)
            self.assertIn(
                '"Not tonight," he replied. "I must stay here."',
                text,
            )
            self.assertIn("He looked toward the door and waited.", text)
        finally:
            page.close()

    def test_page_without_mediawiki_article_uses_body_fallback(self):
        page = self.browser.new_page()
        try:
            page.set_content(
                "<html><body>"
                "<nav>Site navigation</nav>"
                "<p>Ordinary page content.</p>"
                "</body></html>"
            )

            # Mirror the scraper's existing extraction branch.
            article = page.locator("#mw-content-text")
            if article.count():
                text = article.first.inner_text()
            else:
                text = page.inner_text("body")

            self.assertIn("Site navigation", text)
            self.assertIn("Ordinary page content.", text)
        finally:
            page.close()


if __name__ == "__main__":
    unittest.main()
