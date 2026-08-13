"""Validate Amazon UK's Shop by Department expansion using a shared context."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import re
from time import monotonic
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from playwright.sync_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


class AmazonDepartmentCollectorError(RuntimeError):
    """Raised when the Amazon department navigation check cannot complete."""


class AmazonDepartmentCollector:
    """Reach and validate the expanded Shop by Department drawer section."""

    _URL = "https://www.amazon.co.uk/"
    _TIMEOUT_MS = 15_000
    _FLYOUT_SOURCE_UNAVAILABLE_MARKER = (
        "we're sorry, but this feature is currently unavailable. "
        "please try again later."
    )
    _EXCLUDED_CATEGORIES = {
        "Amazon Fresh",
        "Books",
        "Films, TV, Music & Games",
        "Food & Grocery",
    }
    _STRUCTURAL_ITEM_NAMES = {
        "See All Departments",
        "See all",
        "See less",
        "Back",
        "Main menu",
    }

    def __init__(self, headless: bool = False) -> None:
        """Configure Chromium visibility for this live navigation check."""
        self._headless = headless
        self._consent_bootstrap_handled = False

    def bootstrap_context(self, context: Any) -> dict[str, Any]:
        """Load Amazon once and handle consent for the shared browser context."""
        diagnostics: dict[str, Any] = {"homepage_loaded": False, "cookie_handled": False}
        page = context.new_page()
        try:
            page.set_default_timeout(self._TIMEOUT_MS)
            response = page.goto(
                self._URL,
                wait_until="domcontentloaded",
                timeout=self._TIMEOUT_MS,
            )
            diagnostics["homepage_loaded"] = response is None or response.status < 400
            if diagnostics["homepage_loaded"]:
                self._handle_cookie_consent(page, diagnostics)
                self._consent_bootstrap_handled = True
            return diagnostics
        finally:
            page.close()

    def collect(self) -> dict[str, Any]:
        """Confirm every eligible department opens its next drawer menu layer."""
        diagnostics: dict[str, Any] = {
            "bootstrap_homepage_loaded": False,
            "bootstrap_cookie_handled": False,
            "main_homepage_loaded": False,
            "consent_reappeared": False,
            "drawer_opened": False,
            "shop_by_department_found": False,
            "section_container_found": False,
            "section_items_before_see_all": [],
            "see_all_departments_found": False,
            "see_all_departments_clicked": False,
            "department_section_expanded": False,
            "section_items_after_see_all": [],
            "discovered_category_count": 0,
            "eligible_category_count": 0,
            "skipped_category_count": 0,
            "topic_layer_success_count": 0,
            "topic_layer_failure_count": 0,
            "topic_collection_success_count": 0,
            "topic_collection_failure_count": 0,
            "total_topic_count": 0,
            "topic_navigation_attempt_count": 0,
            "topic_navigation_success_count": 0,
            "topic_navigation_failure_count": 0,
            "topic_page_opened_count": 0,
            "topic_page_unavailable_count": 0,
            "topics_with_top_nav_count": 0,
            "topics_without_top_nav_count": 0,
            "direct_top_nav_total_count": 0,
            "top_nav_collection_failure_count": 0,
            "expandable_top_nav_count": 0,
            "non_expandable_top_nav_count": 0,
            "mega_menu_success_count": 0,
            "mega_menu_not_found_count": 0,
            "mega_menu_collection_failure_count": 0,
            "flyout_source_unavailable_count": 0,
            "level_4_node_total_count": 0,
        }
        categories: list[dict[str, Any]] = []
        try:
            with sync_playwright() as playwright:
                try:
                    browser = playwright.chromium.launch(headless=self._headless)
                except PlaywrightError as error:
                    self._fail("BROWSER_LAUNCH_ERROR", "Chromium could not be launched", error)
                try:
                    context = browser.new_context()
                    bootstrap = self.bootstrap_context(context)
                    diagnostics["bootstrap_homepage_loaded"] = bootstrap["homepage_loaded"]
                    diagnostics["bootstrap_cookie_handled"] = self._consent_bootstrap_handled
                    if not bootstrap["homepage_loaded"]:
                        self._fail("HOMEPAGE_NOT_LOADED", "Bootstrap homepage did not load")

                    page = context.new_page()
                    try:
                        page.set_default_timeout(self._TIMEOUT_MS)
                        response = page.goto(
                            self._URL,
                            wait_until="domcontentloaded",
                            timeout=self._TIMEOUT_MS,
                        )
                        diagnostics["main_homepage_loaded"] = (
                            response is None or response.status < 400
                        )
                        if not diagnostics["main_homepage_loaded"]:
                            self._fail("HOMEPAGE_NOT_LOADED", "Main homepage did not load")
                        self._detect_access_block(page.content())
                        if self._has_visible_consent(page):
                            diagnostics["consent_reappeared"] = True
                            self._handle_cookie_consent(page, diagnostics)

                        section = self._open_expanded_department_section(page, diagnostics)
                        category_names = self._category_names(self._section_items(section))
                        diagnostics["discovered_category_count"] = len(category_names)

                        for index, category_name in enumerate(category_names):
                            if category_name in self._EXCLUDED_CATEGORIES:
                                categories.append(
                                    {
                                        "name": category_name,
                                        "status": "SKIPPED",
                                        "department_found": True,
                                        "department_clicked": False,
                                        "topic_layer_opened": False,
                                        "topic_count": 0,
                                        "topics": [],
                                        "skip_reason": "excluded_category",
                                        "error": None,
                                    }
                                )
                                diagnostics["skipped_category_count"] += 1
                                continue

                            diagnostics["eligible_category_count"] += 1
                            category_result = {
                                "name": category_name,
                                "status": "FAILED",
                                "department_found": False,
                                "department_clicked": False,
                                "topic_layer_opened": False,
                                "topic_count": 0,
                                "topics": [],
                                "error": None,
                            }
                            try:
                                items = self._section_items(section)
                                department = self._find_department(items, category_name)
                                category_result["department_found"] = department is not None
                                if department is None:
                                    raise AmazonDepartmentCollectorError(
                                        "DEPARTMENT_NOT_FOUND: " + category_name
                                    )
                                if self._department_is_compressed(department):
                                    self._expand_see_all(page, section, diagnostics)
                                    items = self._section_items(section)
                                    department = self._find_department(items, category_name)
                                    category_result["department_found"] = department is not None
                                    if department is None or self._department_is_compressed(department):
                                        raise AmazonDepartmentCollectorError(
                                            "DEPARTMENT_NOT_FOUND: " + category_name
                                        )
                                department.click()
                                category_result["department_clicked"] = True
                                category_result["topic_layer_opened"] = (
                                    self._wait_for_department_change(page, category_name)
                                )
                                if not category_result["topic_layer_opened"]:
                                    raise AmazonDepartmentCollectorError(
                                        "TOPIC_LAYER_NOT_OPENED: " + category_name
                                    )
                                diagnostics["topic_layer_success_count"] += 1
                                topics = self._collect_topic_items(page, category_name)
                                if not topics:
                                    raise AmazonDepartmentCollectorError(
                                        "No non-structural visible topic items were found "
                                        "in the active submenu."
                                    )
                                category_result["topics"] = topics
                                category_result["topic_count"] = len(topics)
                                category_result["status"] = "TOPICS_COLLECTED"
                                diagnostics["topic_collection_success_count"] += 1
                                diagnostics["total_topic_count"] += len(topics)
                            except Exception as error:
                                category_result["error"] = f"{type(error).__name__}: {error}"
                                if category_result["topic_layer_opened"]:
                                    category_result["status"] = "TOPIC_COLLECTION_FAILED"
                                    diagnostics["topic_collection_failure_count"] += 1
                                else:
                                    diagnostics["topic_layer_failure_count"] += 1
                            categories.append(category_result)

                            if index < len(category_names) - 1:
                                section = self._return_to_expanded_department_section(
                                    page, diagnostics
                                )
                        self._collect_topic_pages(page, categories, diagnostics)
                    finally:
                        page.close()
                finally:
                    browser.close()
        except AmazonDepartmentCollectorError:
            raise
        except PlaywrightTimeoutError as error:
            self._fail("HOMEPAGE_NOT_LOADED", "Amazon navigation timed out", error)
        except PlaywrightError as error:
            self._fail("PLAYWRIGHT_ERROR", "Playwright could not complete Amazon navigation", error)

        return {
            "source": "amazon_department_topic_layer_check",
            "timestamp": datetime.now(UTC).isoformat(),
            "status": "PASS"
            if not diagnostics["topic_layer_failure_count"]
            and not diagnostics["topic_collection_failure_count"]
            and not diagnostics["topic_navigation_failure_count"]
            and not diagnostics["top_nav_collection_failure_count"]
            and not diagnostics["mega_menu_not_found_count"]
            and not diagnostics["mega_menu_collection_failure_count"]
            else "FAIL",
            "diagnostics": diagnostics,
            "categories": categories,
        }

    @staticmethod
    def _has_visible_consent(page: Any) -> bool:
        """Perform one immediate, non-polling check for an unexpected consent UI."""
        for selector in ("#sp-cc", "[role='dialog']", "[aria-modal='true']"):
            locator = page.locator(selector).first
            if locator.count() and locator.is_visible():
                return True

        return bool(
            page.locator("body *").evaluate_all(
                """elements => elements.some(element => {
                    if (element.offsetParent === null) return false;
                    const text = (element.innerText || element.value || '').trim();
                    if (text === 'Select your cookie preferences') return true;
                    const clickable = element.matches(
                        'a, button, input, [role="button"]'
                    );
                    return clickable && (
                        text === 'Accept' || text === 'Decline'
                    );
                })"""
            )
        )

    @staticmethod
    def _handle_cookie_consent(page: Any, diagnostics: dict[str, Any]) -> None:
        """Dismiss a visible consent panel before any subsequent navigation."""
        diagnostics.update(
            {
                "cookie_dialog_found": False,
                "cookie_button_found": False,
                "cookie_button_text": None,
                "cookie_button_clicked": False,
                "cookie_dialog_closed": False,
                "cookie_error": None,
                "cookie_dialog_clickables": [],
                "consent_timing_samples": [],
            }
        )
        elapsed = 0
        while elapsed <= 5_000:
            visible_dialog_count = sum(
                candidate.is_visible()
                for candidate in page.locator("[role='dialog']").all()
            )
            aria_modal_count = sum(
                candidate.is_visible()
                for candidate in page.locator("[aria-modal='true']").all()
            )
            text_signals = page.locator("body *").evaluate_all(
                """elements => {
                    const visible = element => element.offsetParent !== null;
                    const text = element => element.innerText || element.value || '';
                    const values = elements.filter(visible).map(text);
                    return {
                        selectPreferences: values.some(value =>
                            value.includes('Select your cookie preferences')
                        ),
                        accept: values.some(value => value.trim().startsWith('Accept')),
                        decline: values.some(value => value.trim().startsWith('Decline'))
                    };
                }"""
            )
            sample = {
                "elapsed_ms": elapsed,
                "sp_cc_count": page.locator("#sp-cc").count(),
                "visible_dialog_count": visible_dialog_count,
                "aria_modal_count": aria_modal_count,
                "select_preferences_found": text_signals["selectPreferences"],
                "accept_found": text_signals["accept"],
                "decline_found": text_signals["decline"],
            }
            diagnostics["consent_timing_samples"].append(sample)
            if (
                sample["sp_cc_count"]
                or sample["visible_dialog_count"]
                or sample["aria_modal_count"]
                or sample["select_preferences_found"]
                or sample["accept_found"]
                or sample["decline_found"]
            ):
                break
            if elapsed == 5_000:
                break
            page.wait_for_timeout(250)
            elapsed += 250
        dialog = None
        for candidate in page.locator(
            "#sp-cc, [role='dialog'], [aria-modal='true']"
        ).all():
            if candidate.is_visible():
                dialog = candidate
                diagnostics["cookie_dialog_found"] = True
                break
        if dialog is None:
            return

        controls = [
            control
            for control in dialog.locator("a, button, input, [role='button']").all()
            if control.is_visible()
        ]
        control = None
        for preferred_text in (
            "accept", "accept all", "decline", "decline all", "reject", "reject all",
        ):
            for candidate in controls:
                button_text = candidate.evaluate(
                    "element => element.innerText || element.value || ''"
                ).strip()
                if button_text.casefold() == preferred_text:
                    control = candidate
                    diagnostics["cookie_button_found"] = True
                    diagnostics["cookie_button_text"] = button_text
                    break
            if control is not None:
                break

        if control is None:
            diagnostics["cookie_dialog_clickables"] = dialog.locator(
                "a, button, input, [role='button']"
            ).evaluate_all(
                """elements => elements
                    .filter(element => element.offsetParent !== null)
                    .map(element => ({
                        text: element.innerText || element.value || '',
                        tagName: element.tagName,
                        id: element.id || null,
                        className: element.getAttribute('class'),
                        role: element.getAttribute('role'),
                        ariaLabel: element.getAttribute('aria-label'),
                        outerHTML: element.outerHTML
                    }))"""
            )
            diagnostics["cookie_error"] = "No matching consent action was found."
            raise RuntimeError(diagnostics["cookie_error"])

        control.click()
        diagnostics["cookie_button_clicked"] = True
        elapsed = 0
        while elapsed < AmazonDepartmentCollector._TIMEOUT_MS:
            try:
                dialog_visible = dialog.is_visible()
            except PlaywrightError:
                dialog_visible = False
            if not dialog_visible:
                diagnostics["cookie_handled"] = True
                diagnostics["cookie_dialog_closed"] = True
                return
            page.wait_for_timeout(100)
            elapsed += 100

        diagnostics["cookie_error"] = "Cookie consent panel remained visible."
        raise RuntimeError(diagnostics["cookie_error"])

    def _open_drawer(self, page: Any) -> Any | None:
        """Click All and return the left drawer only after it is visible."""
        header = page.locator("#nav-main, #nav-belt, #navbar").first
        try:
            header.wait_for(state="visible", timeout=self._TIMEOUT_MS)
        except PlaywrightTimeoutError:
            pass

        candidates = (
            ("#nav-hamburger-menu", "#nav-hamburger-menu"),
            ("a#nav-hamburger-menu", "a#nav-hamburger-menu"),
            (
                "a:text-is('All'), button:text-is('All'), [role='button']:text-is('All')",
                "exact visible text All",
            ),
            (
                "a[aria-label*='All' i], button[aria-label*='All' i], "
                "[role='button'][aria-label*='All' i]",
                "aria-label contains All",
            ),
            (
                "a[aria-label*='navigation' i], button[aria-label*='navigation' i], "
                "[role='button'][aria-label*='navigation' i], "
                "a[aria-label*='menu' i], button[aria-label*='menu' i], "
                "[role='button'][aria-label*='menu' i]",
                "aria-label indicates navigation/menu",
            ),
        )
        drawer_step_timeout_ms = 1_250
        for selector, _ in candidates:
            control = page.locator(selector).first
            try:
                control.wait_for(state="visible", timeout=self._TIMEOUT_MS)
            except PlaywrightTimeoutError:
                continue

            for _ in range(2):
                try:
                    control.click()
                except PlaywrightError:
                    continue
                for drawer_selector, _ in (
                    ("#hmenu-content", "hmenu_content"),
                    ("#hmenu-canvas", "hmenu_canvas"),
                ):
                    drawer = page.locator(drawer_selector).first
                    try:
                        drawer.wait_for(
                            state="visible", timeout=drawer_step_timeout_ms
                        )
                    except PlaywrightTimeoutError:
                        continue
                    return drawer

        return None

    @staticmethod
    def _find_header(drawer: Any) -> Any | None:
        """Find the visible, non-clickable Shop by Department section header."""
        for header in drawer.locator(".hmenu-title, [role='heading']").all():
            if header.is_visible() and header.inner_text().strip() == "Shop by Department":
                return header
        return None

    @staticmethod
    def _section_items(section: Any) -> list[Any]:
        """Return visible clickable items from the header's owning container only."""
        return [
            item
            for item in section.locator("a, button, [role='menuitem']").all()
            if item.is_visible()
        ]

    def _find_department(self, items: list[Any], department_name: str) -> Any | None:
        """Find the configured department using only the section's stored locators."""
        for item in items:
            if item.inner_text().strip() == department_name:
                return item
        return None

    def _open_expanded_department_section(
        self,
        page: Any,
        diagnostics: dict[str, Any],
    ) -> Any:
        drawer = self._open_drawer(page)
        diagnostics["drawer_opened"] = drawer is not None
        if drawer is None:
            self._fail("DRAWER_NOT_OPENED", "Amazon hamburger drawer did not open")
        header = self._find_header(drawer)
        if header is None:
            self._fail("SHOP_BY_DEPARTMENT_NOT_FOUND", "Shop by Department was not found")
        diagnostics["shop_by_department_found"] = True
        section = header.locator(
            "xpath=ancestor::section["
            "contains(concat(' ', normalize-space(@class), ' '), "
            "' category-section ')][1]"
        )
        diagnostics["section_container_found"] = section.is_visible()
        if not diagnostics["section_container_found"]:
            self._fail(
                "SECTION_CONTAINER_NOT_FOUND",
                "Shop by Department category-section was not found",
            )
        diagnostics["section_items_before_see_all"] = [
            item.inner_text().strip() for item in self._section_items(section)
        ]
        self._expand_see_all(page, section, diagnostics)
        diagnostics["section_items_after_see_all"] = [
            item.inner_text().strip() for item in self._section_items(section)
        ]
        return section

    def _return_to_expanded_department_section(
        self,
        page: Any,
        diagnostics: dict[str, Any],
    ) -> Any:
        response = page.goto(
            self._URL,
            wait_until="domcontentloaded",
            timeout=self._TIMEOUT_MS,
        )
        if response is not None and response.status >= 400:
            self._fail("HOMEPAGE_NOT_LOADED", f"Amazon UK homepage returned HTTP {response.status}")
        self._detect_access_block(page.content())
        if self._has_visible_consent(page):
            diagnostics["consent_reappeared"] = True
            self._handle_cookie_consent(page, diagnostics)
        return self._open_expanded_department_section(page, diagnostics)

    def _category_names(self, items: list[Any]) -> list[str]:
        structural_names = {
            name.casefold() for name in self._STRUCTURAL_ITEM_NAMES
        }
        return [
            name
            for item in items
            if (name := item.inner_text().strip())
            and name.casefold() not in structural_names
        ]

    @staticmethod
    def _department_is_compressed(department: Any) -> bool:
        return bool(
            department.evaluate(
                """element => {
                    let ancestor = element.parentElement;
                    while (ancestor) {
                        const className = ancestor.className || '';
                        if (
                            ancestor.getAttribute('aria-hidden') === 'true' ||
                            (
                                className.includes('hmenu-compress-section') &&
                                className.includes('compressed')
                            )
                        ) return true;
                        ancestor = ancestor.parentElement;
                    }
                    return false;
                }"""
            )
        )

    def _wait_for_department_change(self, page: Any, department_name: str) -> bool:
        """Confirm the active department submenu from its heading and classes."""
        del department_name
        page.wait_for_timeout(300)
        drawer = page.locator("#hmenu-content").first
        elapsed = 0
        while elapsed < self._TIMEOUT_MS:
            for menu in drawer.locator(":scope > .hmenu").all():
                menu_class = menu.get_attribute("class") or ""
                submenu_active = not any(
                    marker in menu_class
                    for marker in (
                        "hmenu-translateX-right",
                        "hmenu-translateX-left",
                    )
                )
                if not submenu_active:
                    continue
                headings = [
                    heading.inner_text().strip()
                    for heading in menu.locator(".hmenu-title, [role='heading']").all()
                    if heading.is_visible() and heading.inner_text().strip()
                ]
                items = [
                    item.inner_text().strip()
                    for item in menu.locator("a, button, [role='menuitem']").all()
                    if item.is_visible() and item.inner_text().strip()
                ]
                if "Shop by Department" not in headings and (headings or items):
                    return True
            page.wait_for_timeout(100)
            elapsed += 100
        return False

    def _collect_topic_items(
        self,
        page: Any,
        category_name: str,
    ) -> list[dict[str, str | None]]:
        """Collect raw visible topic items from the current active department submenu."""
        drawer = page.locator("#hmenu-content").first
        structural_names = {
            name.casefold() for name in self._STRUCTURAL_ITEM_NAMES
        }
        for menu in drawer.locator(":scope > .hmenu").all():
            menu_class = menu.get_attribute("class") or ""
            if "hmenu-translateX-right" in menu_class or "hmenu-translateX-left" in menu_class:
                continue
            headings = [
                heading.inner_text().strip()
                for heading in menu.locator(".hmenu-title, [role='heading']").all()
                if heading.is_visible() and heading.inner_text().strip()
            ]
            if "Shop by Department" in headings:
                continue
            topics = []
            for item in menu.locator("a, button, [role='menuitem']").all():
                if not item.is_visible():
                    continue
                name = item.inner_text().strip()
                if not name or name.casefold() in structural_names:
                    continue
                href = item.get_attribute("href")
                topics.append(
                    {
                        "id": self._amazon_node_id(href),
                        "name": name,
                        "category": category_name,
                        "href": href,
                    }
                )
            return topics
        return []

    def _collect_topic_pages(
        self,
        page: Any,
        categories: list[dict[str, Any]],
        diagnostics: dict[str, Any],
    ) -> None:
        """Navigate each collected topic and retain only direct local top navigation."""
        for category in categories:
            if category.get("status") != "TOPICS_COLLECTED":
                continue
            for topic in category.get("topics", []):
                if not isinstance(topic, dict):
                    continue
                self._collect_one_topic_page(page, topic, diagnostics)

    def _collect_one_topic_page(
        self,
        page: Any,
        topic: dict[str, Any],
        diagnostics: dict[str, Any],
    ) -> None:
        """Navigate one raw topic and record its direct #nav-subnav state."""
        href = topic.get("href")
        topic.update(
            {
                "navigation_status": "TOPIC_NAVIGATION_SKIPPED",
                "topic_page_url": None,
                "requested_topic_url": None,
                "final_topic_url": None,
                "redirected": False,
                "top_nav_status": "NOT_ATTEMPTED",
                "top_nav_count": 0,
                "top_nav": [],
                "error": None,
            }
        )
        if not isinstance(href, str) or not href.strip():
            topic["skip_reason"] = "missing_href"
            return

        diagnostics["topic_navigation_attempt_count"] += 1
        resolved_url = urljoin(self._URL, href)
        topic["requested_topic_url"] = resolved_url
        parsed_url = urlparse(resolved_url)
        if (
            parsed_url.scheme != "https"
            or parsed_url.hostname not in {"amazon.co.uk", "www.amazon.co.uk"}
            or not parsed_url.path.startswith("/")
        ):
            self._topic_navigation_failed(
                topic, diagnostics, "Invalid Amazon topic href."
            )
            return

        try:
            response = page.goto(
                resolved_url,
                wait_until="domcontentloaded",
                timeout=self._TIMEOUT_MS,
            )
            current_url = urlparse(page.url)
            destination_loaded = current_url.hostname in {
                "amazon.co.uk", "www.amazon.co.uk"
            }
        except (PlaywrightError, PlaywrightTimeoutError) as error:
            self._topic_navigation_failed(topic, diagnostics, str(error))
            return

        topic["final_topic_url"] = page.url
        topic["topic_page_url"] = page.url
        topic["redirected"] = page.url != resolved_url

        if not destination_loaded:
            self._topic_navigation_failed(
                topic, diagnostics, "Amazon topic destination did not open."
            )
            return

        if self._is_topic_page_unavailable(page.content()):
            topic["navigation_status"] = "TOPIC_PAGE_UNAVAILABLE"
            topic["top_nav_status"] = "NOT_APPLICABLE"
            diagnostics["topic_page_unavailable_count"] += 1
            return

        if response is not None and response.status >= 400:
            self._topic_navigation_failed(
                topic, diagnostics, f"Amazon topic returned HTTP {response.status}."
            )
            return

        topic["navigation_status"] = "TOPIC_PAGE_OPENED"
        diagnostics["topic_navigation_success_count"] += 1
        diagnostics["topic_page_opened_count"] += 1
        try:
            top_nav_status, top_nav = self._collect_direct_top_nav(
                page, topic, diagnostics
            )
            topic["top_nav_status"] = top_nav_status
            topic["top_nav"] = top_nav
            topic["top_nav_count"] = len(top_nav)
            diagnostics["direct_top_nav_total_count"] += len(top_nav)
            if top_nav_status == "TOP_NAV_COLLECTED":
                diagnostics["topics_with_top_nav_count"] += 1
            else:
                diagnostics["topics_without_top_nav_count"] += 1
        except Exception as error:
            topic["top_nav_status"] = "TOP_NAV_COLLECTION_FAILED"
            topic["error"] = f"{type(error).__name__}: {error}"
            diagnostics["top_nav_collection_failure_count"] += 1

    @staticmethod
    def _topic_navigation_failed(
        topic: dict[str, Any], diagnostics: dict[str, Any], error: str
    ) -> None:
        topic["navigation_status"] = "TOPIC_NAVIGATION_FAILED"
        topic["top_nav_status"] = "NOT_ATTEMPTED"
        topic["error"] = error
        diagnostics["topic_navigation_failure_count"] += 1

    @staticmethod
    def _is_topic_page_unavailable(html: str) -> bool:
        """Recognize Amazon's own non-functioning-page response after navigation."""
        return "the web address you entered is not a functioning page on our site" in html.casefold()

    def _collect_direct_top_nav(
        self, page: Any, topic: dict[str, Any], diagnostics: dict[str, Any]
    ) -> tuple[str, list[dict[str, Any]]]:
        """Collect only the original direct #nav-subnav anchors for one topic page."""
        subnav_locator = page.locator("#nav-subnav")
        if subnav_locator.count() == 0:
            return "NO_TOP_NAV", []
        subnav = subnav_locator.first
        if not subnav.is_visible():
            return "NO_VISIBLE_TOP_NAV", []

        direct_items = subnav.locator(":scope > ul.subnav-ul > li.subnav-li")
        top_nav = []
        for item in direct_items.all():
            anchor = item.locator(":scope a.nav-a").first
            if anchor.count() == 0:
                continue
            name = anchor.inner_text().strip()
            href = anchor.get_attribute("href")
            if not name or not href:
                continue
            absolute_url = urljoin(self._URL, href)
            node = {
                "id": self._amazon_node_id(absolute_url),
                "name": name,
                "category": topic["category"],
                "topic": topic["name"],
                "level": 3,
                "parent_name": topic["name"],
                "url": absolute_url,
                "mega_menu_status": None,
                "mega_menu_count": 0,
                "mega_menu": [],
                "mega_menu_error": None,
                "data_nav_key": None,
                "expected_flyout_id": None,
                "aria_expanded_before": None,
                "aria_expanded_after": None,
                "associated_flyout_found": False,
                "associated_flyout_visible": False,
                "mega_menu_dom_found": False,
                "associated_flyout_link_count": 0,
                "associated_flyout_visible_link_count": 0,
                "flyout_content_ready": False,
                "flyout_source_unavailable": False,
                "flyout_rendered_text": None,
            }
            self._collect_mega_menu(
                page, item, anchor, node, topic, diagnostics
            )
            top_nav.append(node)
        return "TOP_NAV_COLLECTED", top_nav

    def _collect_mega_menu(
        self,
        page: Any,
        item: Any,
        anchor: Any,
        node: dict[str, Any],
        topic: dict[str, Any],
        diagnostics: dict[str, Any],
    ) -> None:
        """Hover one expandable direct top-nav and collect its exact flyout links."""
        if item.locator(":scope a.nav-a.nav-hasArrow").count() == 0:
            node["mega_menu_status"] = "NOT_EXPANDABLE"
            diagnostics["non_expandable_top_nav_count"] += 1
            return

        diagnostics["expandable_top_nav_count"] += 1
        nav_key_locator = item.locator("div.subnav-div[data-nav-key]")
        arrow_locator = item.locator("button.nav-arrow[aria-haspopup='true']")
        data_nav_key = (
            nav_key_locator.first.get_attribute("data-nav-key")
            if nav_key_locator.count()
            else None
        )
        node["data_nav_key"] = data_nav_key
        if not data_nav_key:
            node["mega_menu_status"] = "MEGA_MENU_COLLECTION_FAILED"
            node["mega_menu_error"] = "Expandable top-nav item has no data-nav-key."
            diagnostics["mega_menu_collection_failure_count"] += 1
            return

        node["expected_flyout_id"] = f"nav-flyout-{data_nav_key}"
        node["aria_expanded_before"] = (
            arrow_locator.first.get_attribute("aria-expanded")
            if arrow_locator.count()
            else None
        )
        started = monotonic()
        try:
            anchor.hover()
            readiness_status, flyout_snapshot = self._wait_for_associated_mega_menu(
                page,
                node["expected_flyout_id"],
            )
            node["aria_expanded_after"] = (
                arrow_locator.first.get_attribute("aria-expanded")
                if arrow_locator.count()
                else None
            )
            node["associated_flyout_found"] = flyout_snapshot["found"]
            node["associated_flyout_visible"] = flyout_snapshot["visible"]
            node["mega_menu_dom_found"] = flyout_snapshot["mega_menu_dom_found"]
            node["associated_flyout_link_count"] = flyout_snapshot["link_count"]
            node["associated_flyout_visible_link_count"] = len(
                flyout_snapshot["links"]
            )
            node["flyout_rendered_text"] = flyout_snapshot["rendered_text"]
            if readiness_status == "SOURCE_UNAVAILABLE":
                node["mega_menu_status"] = "FLYOUT_SOURCE_UNAVAILABLE"
                node["flyout_source_unavailable"] = True
                diagnostics["flyout_source_unavailable_count"] += 1
                return
            if readiness_status != "CONTENT_READY":
                if flyout_snapshot["visible"]:
                    node["mega_menu_status"] = "MEGA_MENU_COLLECTION_FAILED"
                    node["mega_menu_error"] = (
                        "Visible associated flyout contained no usable links after "
                        "bounded wait."
                    )
                    diagnostics["mega_menu_collection_failure_count"] += 1
                else:
                    node["mega_menu_status"] = "MEGA_MENU_NOT_FOUND"
                    node["mega_menu_error"] = "Associated flyout did not become visible."
                    diagnostics["mega_menu_not_found_count"] += 1
                return

            flyout_nodes = self._raw_flyout_nodes(
                flyout_snapshot["links"],
                topic["category"],
                topic["name"],
                node["name"],
            )
            if not flyout_nodes:
                node["mega_menu_status"] = "MEGA_MENU_COLLECTION_FAILED"
                node["mega_menu_error"] = (
                    "Visible associated flyout contained no usable links after "
                    "bounded wait."
                )
                diagnostics["mega_menu_collection_failure_count"] += 1
                return
            node["mega_menu_status"] = "MEGA_MENU_COLLECTED"
            node["mega_menu"] = flyout_nodes
            node["mega_menu_count"] = len(flyout_nodes)
            node["flyout_content_ready"] = True
            diagnostics["mega_menu_success_count"] += 1
            diagnostics["level_4_node_total_count"] += len(flyout_nodes)
        except PlaywrightError as error:
            node["mega_menu_status"] = "MEGA_MENU_COLLECTION_FAILED"
            node["mega_menu_error"] = str(error)
            diagnostics["mega_menu_collection_failure_count"] += 1
        finally:
            node["collection_elapsed_ms"] = round((monotonic() - started) * 1000)

    def _wait_for_associated_mega_menu(
        self,
        page: Any,
        expected_flyout_id: str,
    ) -> tuple[str, dict[str, Any]]:
        """Wait briefly for the exact flyout derived from a live nav key."""
        deadline = monotonic() + 1.0
        snapshot = {
            "found": False,
            "visible": False,
            "mega_menu_dom_found": False,
            "link_count": 0,
            "rendered_text": "",
            "links": [],
        }
        while monotonic() <= deadline:
            snapshot = self._extract_usable_flyout_links(page, expected_flyout_id)
            if snapshot["found"] and snapshot["visible"]:
                if snapshot["links"]:
                    return "CONTENT_READY", snapshot
                if self._is_flyout_source_unavailable(snapshot["rendered_text"]):
                    return "SOURCE_UNAVAILABLE", snapshot
            remaining_ms = int((deadline - monotonic()) * 1000)
            if remaining_ms > 0:
                page.wait_for_timeout(min(50, remaining_ms))
        return "TIMEOUT_NO_CONTENT", snapshot

    def _is_flyout_source_unavailable(self, rendered_text: str) -> bool:
        return (
            self._FLYOUT_SOURCE_UNAVAILABLE_MARKER
            in rendered_text.casefold()
        )

    @staticmethod
    def _extract_usable_flyout_links(
        page: Any,
        expected_flyout_id: str,
    ) -> dict[str, Any]:
        return page.evaluate(
            """expectedFlyoutId => {
                const element = document.getElementById(expectedFlyoutId);
                if (!element) {
                    return {
                        found: false,
                        visible: false,
                        mega_menu_dom_found: false,
                        link_count: 0,
                        rendered_text: '',
                        links: [],
                    };
                }
                const anchors = [...element.querySelectorAll('a[href]')];
                const normalize = value => value.replace(/\s+/g, ' ').trim();
                const linkName = anchor => normalize(anchor.innerText || anchor.textContent || '')
                    || normalize(anchor.getAttribute('aria-label') || '')
                    || normalize((anchor.querySelector('img') || {}).getAttribute?.('alt') || '');
                const visible = anchor => {
                    const style = window.getComputedStyle(anchor);
                    return style.display !== 'none' && style.visibility !== 'hidden';
                };
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                const flyoutVisible = style.display !== 'none'
                    && style.visibility !== 'hidden'
                    && rect.width > 0
                    && rect.height > 0;
                const megaMenu = element.querySelector('.mega-menu');
                return {
                    found: true,
                    visible: flyoutVisible,
                    mega_menu_dom_found: Boolean(
                        megaMenu
                        && window.getComputedStyle(megaMenu).display !== 'none'
                        && window.getComputedStyle(megaMenu).visibility !== 'hidden'
                    ),
                    link_count: anchors.length,
                    rendered_text: (element.innerText || element.textContent || '')
                        .replace(/\s+/g, ' ').trim(),
                    links: anchors
                        .filter(anchor => visible(anchor) && linkName(anchor))
                        .map(anchor => ({name: linkName(anchor), href: anchor.getAttribute('href')})),
                };
            }""",
            expected_flyout_id,
        )

    @staticmethod
    def _find_exact_id_locator(page: Any, expected_id: str) -> Any | None:
        """Return the element whose DOM id exactly equals the supplied value."""
        found = page.evaluate(
            """expectedId => [...document.querySelectorAll('[id]')]
                .some(element => element.id === expectedId)""",
            expected_id,
        )
        if not found:
            return None
        return page.locator(f"[id={json.dumps(expected_id)}]").first

    def _raw_flyout_nodes(
        self,
        links: list[dict[str, str]],
        category_name: str,
        topic_name: str,
        parent_name: str,
    ) -> list[dict[str, Any]]:
        """Return every visible meaningful link in one already-open flyout."""
        nodes = []
        for link in links:
            name = link["name"]
            href = link["href"]
            if not name or not href:
                continue
            absolute_url = urljoin(self._URL, href)
            nodes.append(
                {
                    "id": self._amazon_node_id(absolute_url),
                    "name": name,
                    "category": category_name,
                    "topic": topic_name,
                    "level": 4,
                    "parent_name": parent_name,
                    "url": absolute_url,
                }
            )
        return nodes

    @staticmethod
    def _amazon_node_id(href: str | None) -> str | None:
        """Extract the raw Amazon browse-node query value when it is present."""
        if not href:
            return None
        parsed = urlparse(href)
        node = parse_qs(parsed.query).get("node", [None])[0]
        if node:
            return node
        filters = parse_qs(parsed.query).get("rh", [])
        for value in filters:
            match = re.search(r"(?:^|,)n:(\d+)(?:,|$)", value)
            if match:
                return match.group(1)
        path_match = re.search(r"/(?:node|browse)/(\d+)(?:/|$)", parsed.path)
        return path_match.group(1) if path_match else None

    def _expand_see_all(
        self,
        page: Any,
        section: Any,
        diagnostics: dict[str, Any],
    ) -> None:
        compressed = self._section_is_compressed(section)
        see_all = section.locator("[aria-label='See All Departments']").first
        if see_all.count() and see_all.is_visible():
            diagnostics["see_all_departments_found"] = True
            see_all.click()
            diagnostics["see_all_departments_clicked"] = True
        elif compressed:
            self._fail("SEE_ALL_NOT_FOUND", "See All Departments was required but not found")

        elapsed = 0
        while elapsed < self._TIMEOUT_MS:
            if not self._section_is_compressed(section):
                diagnostics["department_section_expanded"] = True
                return
            page.wait_for_timeout(100)
            elapsed += 100
        self._fail("SEE_ALL_NOT_EXPANDED", "Shop by Department remained compressed")

    @staticmethod
    def _section_is_compressed(section: Any) -> bool:
        return bool(
            section.evaluate(
                """element => [...element.querySelectorAll('a, button, [role="menuitem"]')]
                    .some(item => {
                        let ancestor = item.parentElement;
                        while (ancestor && ancestor !== element.parentElement) {
                            const className = ancestor.className || '';
                            if (
                                ancestor.getAttribute('aria-hidden') === 'true' ||
                                (className.includes('hmenu-compress-section') &&
                                 className.includes('compressed'))
                            ) return true;
                            ancestor = ancestor.parentElement;
                        }
                        return false;
                    })"""
            )
        )

    @staticmethod
    def _detect_access_block(html: str) -> None:
        markers = ("robot check", "validatecaptcha", "enter the characters you see below")
        if any(marker in html.casefold() for marker in markers):
            raise AmazonDepartmentCollectorError(
                "AMAZON_ACCESS_BLOCKED: Amazon UK presented a CAPTCHA or Robot Check page"
            )

    @staticmethod
    def _fail(status: str, message: str, error: Exception | None = None) -> None:
        detail = f": {error}" if error is not None else ""
        raise AmazonDepartmentCollectorError(f"{status}: {message}{detail}")
