"""Collect Amazon UK's top-level Shop by Department categories."""

from __future__ import annotations

from datetime import UTC, datetime
import re
from time import monotonic
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from playwright.sync_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


class AmazonDepartmentCollectorError(RuntimeError):
    """Base exception for Amazon department collection failures."""


class AmazonDepartmentBrowserError(AmazonDepartmentCollectorError):
    """Raised when Chromium cannot be launched for collection."""


class AmazonDepartmentNavigationTimeout(AmazonDepartmentCollectorError):
    """Raised when Amazon UK does not render within the configured timeout."""


class AmazonDepartmentAccessBlockedError(AmazonDepartmentCollectorError):
    """Raised when Amazon UK presents a CAPTCHA or Robot Check page."""


class AmazonDepartmentHamburgerMenuError(AmazonDepartmentCollectorError):
    """Raised when Amazon UK's main All menu is unavailable."""


class AmazonDepartmentSectionError(AmazonDepartmentCollectorError):
    """Raised when the Shop by Department section is unavailable."""


class AmazonDepartmentParsingError(AmazonDepartmentCollectorError):
    """Raised when Amazon UK's rendered department navigation cannot be parsed."""


class AmazonDepartmentCollector:
    """Collect raw top-level Shop by Department entries from Amazon UK."""

    _HOME_URL = "https://www.amazon.co.uk/"
    _REQUEST_TIMEOUT_MS = 15_000
    _USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    _VIEWPORT = {"width": 1440, "height": 900}
    _HAMBURGER_SELECTORS = (
        "#nav-hamburger-menu",
        "a[aria-label='All']",
        "a.nav-hamburger-menu",
    )
    _MENU_PANEL_SELECTORS = (
        "#hmenu-content",
        "#hmenu-container",
        "#nav-flyout-shopAll",
    )
    _NON_DEPARTMENT_NAMES = {
        "main menu",
        "see all",
        "see less",
        "back",
        "customer service",
        "sign in",
        "account",
        "orders",
        "help",
    }

    def __init__(self, headless: bool = True) -> None:
        """Initialize the collector with headless Chromium enabled by default."""
        self._headless = headless

    def collect(self) -> dict[str, Any]:
        """Return Amazon UK's top-level Shop by Department categories."""
        html = self._fetch_html()
        categories = self._remove_duplicates(self._parse_department_links(html))

        if not categories:
            raise AmazonDepartmentParsingError(
                "No departments were found in the Shop by Department section."
            )

        return {
            "source": "amazon_department",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {"categories": categories},
        }

    def _fetch_html(self) -> str:
        """Open Amazon UK, render the department menu, and return page HTML."""
        try:
            with sync_playwright() as playwright:
                browser = self._launch_browser(playwright)
                try:
                    page = browser.new_page(
                        locale="en-GB",
                        timezone_id="Europe/London",
                        user_agent=self._USER_AGENT,
                        viewport=self._VIEWPORT,
                    )
                    page.set_default_timeout(self._REQUEST_TIMEOUT_MS)
                    response = page.goto(
                        self._HOME_URL,
                        wait_until="domcontentloaded",
                        timeout=self._REQUEST_TIMEOUT_MS,
                    )
                    if response is not None and response.status >= 400:
                        raise AmazonDepartmentAccessBlockedError(
                            f"Amazon UK returned HTTP {response.status}."
                        )

                    self._accept_cookie_consent(page)
                    self._detect_access_block(page.content())
                    self._open_all_menu(page)
                    self._expand_see_all(page)
                    html = page.content()
                    self._detect_access_block(html)
                finally:
                    try:
                        browser.close()
                    except PlaywrightError:
                        pass
        except (
            AmazonDepartmentAccessBlockedError,
            AmazonDepartmentBrowserError,
            AmazonDepartmentHamburgerMenuError,
        ):
            raise
        except PlaywrightTimeoutError as error:
            raise AmazonDepartmentNavigationTimeout(
                "Amazon UK did not render within the configured timeout."
            ) from error
        except PlaywrightError as error:
            raise AmazonDepartmentBrowserError(
                "Playwright could not complete Amazon UK browser collection."
            ) from error

        if not html.strip():
            raise AmazonDepartmentParsingError("Amazon UK returned empty rendered HTML.")
        return html

    def _launch_browser(self, playwright: Any) -> Any:
        """Launch Chromium with the configured headless setting."""
        try:
            return playwright.chromium.launch(headless=self._headless)
        except PlaywrightError as error:
            raise AmazonDepartmentBrowserError("Chromium could not be launched.") from error

    def _accept_cookie_consent(self, page: Any) -> None:
        """Dismiss Amazon's cookie dialog before interacting with navigation."""
        accept_selectors = ("#sp-cc-accept", "input#sp-cc-accept")
        decline_selectors = (
            "#sp-cc-rejectall-link",
            "input#sp-cc-rejectall-link",
        )
        dialog = page.locator("#sp-cc").first
        deadline = monotonic() + 5
        dialog_seen = False

        while monotonic() < deadline:
            dialog_seen = dialog_seen or (dialog.count() and dialog.is_visible())
            button = self._visible_cookie_button(page, accept_selectors)
            if button is None:
                button = self._visible_cookie_button(page, decline_selectors)

            if button is not None:
                try:
                    button.click()
                    dialog.wait_for(
                        state="hidden",
                        timeout=max(1, int((deadline - monotonic()) * 1000)),
                    )
                    return
                except (PlaywrightError, PlaywrightTimeoutError) as error:
                    raise AmazonDepartmentSectionError(
                        "Amazon UK's cookie consent dialog could not be dismissed."
                    ) from error

            page.wait_for_timeout(100)

        if dialog_seen:
            raise AmazonDepartmentSectionError(
                "Amazon UK's cookie consent dialog could not be dismissed."
            )

    @staticmethod
    def _visible_cookie_button(page: Any, selectors: tuple[str, ...]) -> Any | None:
        """Return the first visible cookie-consent control for ordered selectors."""
        for selector in selectors:
            button = page.locator(selector).first
            if button.count() and button.is_visible():
                return button
        return None

    def _open_all_menu(self, page: Any) -> None:
        """Open the visible main All hamburger menu."""
        for selector in self._HAMBURGER_SELECTORS:
            menu = page.locator(selector).first
            try:
                menu.wait_for(state="visible", timeout=self._REQUEST_TIMEOUT_MS)
                menu.click()
                self._wait_for_menu_panel(page)
                return
            except PlaywrightTimeoutError:
                continue

        raise AmazonDepartmentHamburgerMenuError(
            "Amazon UK's main All hamburger menu was not found."
        )

    def _wait_for_menu_panel(self, page: Any) -> None:
        """Wait for one of Amazon's rendered hamburger-menu panel containers."""
        for selector in self._MENU_PANEL_SELECTORS:
            panel = page.locator(selector).first
            try:
                panel.wait_for(state="visible", timeout=self._REQUEST_TIMEOUT_MS)
                return
            except PlaywrightTimeoutError:
                continue

        raise AmazonDepartmentSectionError(
            "Amazon UK's department menu panel did not render."
        )

    def _expand_see_all(self, page: Any) -> None:
        """Expand and verify the full visible Shop by Department menu."""
        for selector in self._MENU_PANEL_SELECTORS:
            panel = page.locator(selector).first
            if not panel.count():
                continue

            see_all = panel.get_by_text("See all", exact=True).first
            if see_all.count() and see_all.is_visible():
                see_all.click()
            self._wait_for_expanded_departments(page)
            return

        raise AmazonDepartmentSectionError(
            "Amazon UK's department menu panel was not found for expansion."
        )

    def _wait_for_expanded_departments(self, page: Any) -> None:
        """Wait until more than 20 visible department entries are rendered."""
        try:
            page.wait_for_function(
                """() => {
                    const items = document.querySelectorAll(
                        '#hmenu-content .hmenu-item'
                    );
                    let collecting = false;
                    let count = 0;

                    for (const item of items) {
                        const text = item.innerText.trim().replace(/\\s+/g, ' ');
                        if (text === 'Shop by Department') {
                            collecting = true;
                            continue;
                        }
                        if (collecting && text === 'See less') {
                            break;
                        }
                        if (collecting && text !== 'See all' && item.offsetParent !== null) {
                            count += 1;
                        }
                    }
                    return count > 20;
                }""",
                timeout=self._REQUEST_TIMEOUT_MS,
            )
        except PlaywrightTimeoutError as error:
            raise AmazonDepartmentSectionError(
                "Shop by Department did not expand beyond 20 visible entries."
            ) from error

    @staticmethod
    def _detect_access_block(html: str) -> None:
        """Raise when Amazon renders a CAPTCHA or Robot Check response."""
        text = html.casefold()
        markers = (
            "robot check",
            "validatecaptcha",
            "enter the characters you see below",
        )
        if any(marker in text for marker in markers):
            raise AmazonDepartmentAccessBlockedError(
                "Amazon UK presented a CAPTCHA or Robot Check page."
            )

    @staticmethod
    def _locate_department_section(html: str) -> Tag:
        """Locate the rendered visible Shop by Department section."""
        soup = BeautifulSoup(html, "html.parser")
        labelled_sections = soup.find_all(
            lambda tag: isinstance(tag, Tag)
            and tag.name != "a"
            and "shop by department"
            in " ".join(
                str(value)
                for value in (
                    tag.get("aria-label"),
                    tag.get("id"),
                    " ".join(tag.get("class", [])),
                )
                if value
            ).casefold()
        )
        if labelled_sections:
            return labelled_sections[0]

        heading = soup.find(
            string=lambda text: isinstance(text, str)
            and "shop by department" in text.casefold()
        )
        if heading is not None:
            section = heading.find_parent(["section", "nav", "div", "ul"])
            if isinstance(section, Tag):
                return section

        raise AmazonDepartmentSectionError(
            "Amazon UK's Shop by Department section was not found."
        )

    def _parse_department_links(
        self,
        html: str,
    ) -> list[dict[str, str | int | None]]:
        """Parse links between Shop by Department and See less in menu order."""
        soup = BeautifulSoup(html, "html.parser")
        menu = soup.select_one("#hmenu-content")
        if not isinstance(menu, Tag):
            raise AmazonDepartmentSectionError(
                "Amazon UK's rendered hamburger menu was not found."
            )

        categories: list[dict[str, str | int | None]] = []
        collecting = False
        for item in menu.select(".hmenu-item"):
            name = " ".join(item.get_text(" ", strip=True).split())
            normalized_name = name.casefold()

            if normalized_name == "shop by department":
                collecting = True
                continue
            if collecting and normalized_name == "see less":
                break
            if collecting and normalized_name == "see all":
                continue
            if not collecting or not name:
                continue

            link = item if item.name == "a" else item.find("a", href=True)
            if not isinstance(link, Tag):
                continue

            url = self._normalize_url(link.get("href", ""))
            if url is None:
                continue

            categories.append(
                {
                    "id": self._department_id(url, name),
                    "name": name,
                    "parent": None,
                    "level": 1,
                    "url": url,
                }
            )
        return categories

    @staticmethod
    def _is_nested_link(link: Tag, section: Tag) -> bool:
        """Return whether a link is inside a nested department list item."""
        item = link.find_parent("li")
        if not isinstance(item, Tag):
            return False

        parent = item.parent
        while isinstance(parent, Tag) and parent is not section:
            if parent.name == "li":
                return True
            parent = parent.parent
        return False

    @staticmethod
    def _normalize_url(href: str) -> str | None:
        """Normalize one public department URL to absolute Amazon UK form."""
        url = urljoin(AmazonDepartmentCollector._HOME_URL, href)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return None
        if parsed.hostname not in {"amazon.co.uk", "www.amazon.co.uk"}:
            return None
        if "/dp/" in parsed.path or "/gp/product/" in parsed.path:
            return None
        return url

    @staticmethod
    def _department_id(url: str, name: str) -> str:
        """Prefer Amazon's browse-node identifier, or make a stable name slug."""
        parsed = urlparse(url)
        node = parse_qs(parsed.query).get("node", [None])[0]
        if node:
            return node

        path_match = re.search(r"/(?:node|browse)/([A-Za-z0-9-]+)", parsed.path)
        if path_match:
            return path_match.group(1)
        return AmazonDepartmentCollector._slug(name)

    @staticmethod
    def _slug(name: str) -> str:
        """Return a stable lowercase slug for a department name."""
        slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
        return slug or "department"

    @staticmethod
    def _remove_duplicates(
        categories: list[dict[str, str | int | None]],
    ) -> list[dict[str, str | int | None]]:
        """Remove duplicate departments while preserving their rendered order."""
        unique_categories: list[dict[str, str | int | None]] = []
        seen_ids: set[str] = set()
        seen_names: set[str] = set()

        for category in categories:
            category_id = category["id"]
            category_name = category["name"]
            if not isinstance(category_id, str) or not isinstance(category_name, str):
                continue
            if category_id in seen_ids or category_name.casefold() in seen_names:
                continue

            seen_ids.add(category_id)
            seen_names.add(category_name.casefold())
            unique_categories.append(category)
        return unique_categories
