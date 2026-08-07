"""Experimental two-depth Amazon UK category navigation collector."""

from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from playwright.sync_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


class AmazonNavigationCollectorError(RuntimeError):
    """Base exception for Amazon navigation collection failures."""


class AmazonNavigationEntryError(AmazonNavigationCollectorError):
    """Raised when the entry page cannot be collected."""


class AmazonNavigationCollector:
    """Collect valid Amazon category navigation nodes to a maximum depth of two."""

    MAX_NODES_PER_PARENT = 30
    MAX_TOTAL_NODES = 200
    _TIMEOUT_MS = 15_000
    _USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    _VIEWPORT = {"width": 1440, "height": 900}
    _NAVIGATION_SELECTORS = (
        "#nav-subnav a",
        "#departments a",
        "#s-refinements a",
        "#hmenu-content a",
        "[data-csa-c-type='widget'] a",
    )
    _EXCLUDED_NAMES = {
        "best sellers",
        "deals",
        "today's deals",
        "new releases",
        "shop now",
        "sign in",
        "account",
        "orders",
        "customer service",
        "help",
        "gift cards",
        "prime",
        "see all",
        "see less",
        "back",
    }

    def __init__(self, headless: bool = False, max_depth: int = 2) -> None:
        """Initialize the experimental navigation collector."""
        if not isinstance(max_depth, int) or max_depth < 0 or max_depth > 2:
            raise ValueError("max_depth must be an integer between 0 and 2.")
        self._headless = headless
        self._max_depth = max_depth

    def collect(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Collect navigation nodes for one Amazon UK category entry."""
        self._validate_entry(entry)
        nodes: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        seen_nodes: set[str] = set()
        visited_urls = {self._normalize_url(entry["url"])}

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=self._headless)
                try:
                    page = browser.new_page(
                        locale="en-GB",
                        timezone_id="Europe/London",
                        user_agent=self._USER_AGENT,
                        viewport=self._VIEWPORT,
                    )
                    page.set_default_timeout(self._TIMEOUT_MS)
                    self._open_entry_page(page, entry["url"])
                    self._accept_cookie_consent(page)

                    if self._max_depth >= 1:
                        depth_one = self._make_nodes(
                            links=self._discover_links(page),
                            entry=entry,
                            parent_id=self._entry_id(entry),
                            parent_name=entry["amazon_department"],
                            depth=1,
                            parent_path=[entry["amazon_department"]],
                            seen_nodes=seen_nodes,
                            remaining=self.MAX_TOTAL_NODES - len(nodes),
                        )
                        nodes.extend(depth_one)

                    if self._max_depth >= 2:
                        self._collect_depth_two(
                            page=page,
                            entry=entry,
                            depth_one=depth_one,
                            nodes=nodes,
                            errors=errors,
                            seen_nodes=seen_nodes,
                            visited_urls=visited_urls,
                        )
                finally:
                    browser.close()
        except AmazonNavigationCollectorError:
            raise
        except (PlaywrightError, PlaywrightTimeoutError) as error:
            raise AmazonNavigationEntryError(
                "Could not open the Amazon UK navigation entry page."
            ) from error

        return {
            "source": "amazon_navigation",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {"entry": entry, "nodes": nodes, "errors": errors},
        }

    def _open_entry_page(self, page: Any, url: str) -> None:
        """Open and validate the single required entry page."""
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=self._TIMEOUT_MS)
        except (PlaywrightError, PlaywrightTimeoutError) as error:
            raise AmazonNavigationEntryError("Amazon UK entry page could not be loaded.") from error

        if response is not None and response.status >= 400:
            raise AmazonNavigationEntryError(
                f"Amazon UK entry page returned HTTP {response.status}."
            )
        if self._is_access_block(page.content()):
            raise AmazonNavigationEntryError(
                "Amazon UK presented a CAPTCHA or Robot Check page."
            )

    def _collect_depth_two(
        self,
        page: Any,
        entry: dict[str, Any],
        depth_one: list[dict[str, Any]],
        nodes: list[dict[str, Any]],
        errors: list[dict[str, Any]],
        seen_nodes: set[str],
        visited_urls: set[str],
    ) -> None:
        """Visit depth-one nodes and append their direct navigation children."""
        for parent in depth_one:
            if len(nodes) >= self.MAX_TOTAL_NODES:
                return
            if parent["url"] in visited_urls:
                continue

            visited_urls.add(parent["url"])
            try:
                self._open_child_page(page, parent["url"])
                children = self._make_nodes(
                    links=self._discover_links(page),
                    entry=entry,
                    parent_id=parent["id"],
                    parent_name=parent["name"],
                    depth=2,
                    parent_path=parent["path"],
                    seen_nodes=seen_nodes,
                    remaining=self.MAX_TOTAL_NODES - len(nodes),
                )
                nodes.extend(children)
            except (PlaywrightError, PlaywrightTimeoutError, AmazonNavigationCollectorError) as error:
                errors.append(
                    {
                        "url": parent["url"],
                        "parent_name": parent["name"],
                        "depth": 1,
                        "reason": str(error),
                    }
                )

    def _open_child_page(self, page: Any, url: str) -> None:
        """Open a depth-one node page for direct child discovery."""
        response = page.goto(url, wait_until="domcontentloaded", timeout=self._TIMEOUT_MS)
        if response is not None and response.status >= 400:
            raise AmazonNavigationCollectorError(
                f"Amazon UK child page returned HTTP {response.status}."
            )
        if self._is_access_block(page.content()):
            raise AmazonNavigationCollectorError(
                "Amazon UK presented a CAPTCHA or Robot Check page."
            )

    def _accept_cookie_consent(self, page: Any) -> None:
        """Accept or decline cookie consent before extracting navigation links."""
        for selector in (
            "#sp-cc-accept",
            "input#sp-cc-accept",
            "#sp-cc-rejectall-link",
            "input#sp-cc-rejectall-link",
        ):
            button = page.locator(selector).first
            if button.count() and button.is_visible():
                button.click()
                return

    def _discover_links(self, page: Any) -> list[dict[str, str]]:
        """Read visible link text and URLs from ordered navigation-area fallbacks."""
        discovered: list[dict[str, str]] = []
        for selector in self._NAVIGATION_SELECTORS:
            links = page.locator(selector).evaluate_all(
                """elements => elements
                    .filter(element => element.offsetParent !== null)
                    .map(element => ({
                        name: element.innerText.trim().replace(/\\s+/g, ' '),
                        href: element.href
                    }))"""
            )
            for link in links:
                if isinstance(link, dict):
                    discovered.append(link)
        return discovered

    def _make_nodes(
        self,
        links: list[dict[str, str]],
        entry: dict[str, Any],
        parent_id: str,
        parent_name: str,
        depth: int,
        parent_path: list[str],
        seen_nodes: set[str],
        remaining: int,
    ) -> list[dict[str, Any]]:
        """Convert direct valid links into bounded, de-duplicated output nodes."""
        nodes: list[dict[str, Any]] = []
        for link in links:
            if len(nodes) >= min(self.MAX_NODES_PER_PARENT, remaining):
                break

            name = link.get("name", "")
            url = self._normalize_url(link.get("href", ""))
            if not self._is_valid_node(name, url):
                continue

            node_id = self._node_id(url, name)
            path = parent_path + [name]
            identity_keys = [f"url:{url}", f"path:{'|'.join(path)}"]
            browse_id = self._browse_node_id(url)
            if browse_id is not None:
                identity_keys.insert(0, f"id:{browse_id}")
            if any(identity in seen_nodes for identity in identity_keys):
                continue

            seen_nodes.update(identity_keys)
            nodes.append(
                {
                    "id": node_id,
                    "name": name,
                    "canonical_category": entry["canonical_category"],
                    "amazon_department": entry["amazon_department"],
                    "parent_id": parent_id,
                    "parent_name": parent_name,
                    "depth": depth,
                    "url": url,
                    "path": path,
                }
            )
        return nodes

    def _is_valid_node(self, name: str, url: str | None) -> bool:
        """Determine whether one visible link is a category browse destination."""
        filter_labels = {
            "prime eligible",
            "free uk delivery",
            "get it tomorrow",
            "delivery day",
            "brands",
            "brand",
        }
        exclusion_terms = (
            "delivering to",
            "update location",
            "warranties",
            "see more",
            "deals",
            "deals & offers",
            "amazon renewed",
        )
        normalized_name = name.casefold()
        if (
            not name
            or normalized_name in self._EXCLUDED_NAMES
            or normalized_name in filter_labels
            or any(term in normalized_name for term in exclusion_terms)
            or url is None
        ):
            return False

        parsed = urlparse(url)
        if "/dp/" in parsed.path or "/gp/product/" in parsed.path:
            return False

        query = parse_qs(parsed.query)
        if "node" in query:
            return True

        if parsed.path == "/s":
            facet_parameters = {"rh", "p_85", "p_90", "p_123", "rnid"}
            if any(parameter in query for parameter in facet_parameters):
                return False
            if any(parameter.startswith("p_n_") for parameter in query):
                return False
            return "i" in query

        return parsed.path.startswith(("/b", "/gp/browse"))

    @staticmethod
    def _normalize_url(href: str) -> str | None:
        """Return an absolute Amazon UK URL or ``None`` for invalid links."""
        url = urljoin("https://www.amazon.co.uk/", href)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return None
        if parsed.hostname not in {"amazon.co.uk", "www.amazon.co.uk"}:
            return None
        return url

    @staticmethod
    def _node_id(url: str, name: str) -> str:
        """Prefer an Amazon browse identifier, falling back to a stable slug."""
        node = AmazonNavigationCollector._browse_node_id(url)
        if node:
            return node

        parsed = urlparse(url)
        match = re.search(r"/(?:node|browse)/([A-Za-z0-9-]+)", parsed.path)
        if match:
            return match.group(1)
        return re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")

    @staticmethod
    def _browse_node_id(url: str) -> str | None:
        """Extract a browse-node identifier when Amazon exposes one in the URL."""
        return parse_qs(urlparse(url).query).get("node", [None])[0]

    def _entry_id(self, entry: dict[str, Any]) -> str:
        """Return a stable parent identifier for depth-one navigation nodes."""
        return self._node_id(entry["url"], entry["amazon_department"])

    @staticmethod
    def _is_access_block(html: str) -> bool:
        """Identify Amazon CAPTCHA and Robot Check pages."""
        text = html.casefold()
        return any(
            marker in text
            for marker in (
                "robot check",
                "validatecaptcha",
                "enter the characters you see below",
            )
        )

    @staticmethod
    def _validate_entry(entry: Any) -> None:
        """Validate the single experimental navigation entry contract."""
        if not isinstance(entry, dict):
            raise ValueError("entry must be a dictionary.")
        for field in ("canonical_category", "amazon_department", "url"):
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"entry requires a non-empty {field}.")
        if AmazonNavigationCollector._normalize_url(entry["url"]) is None:
            raise ValueError("entry.url must be an absolute Amazon UK URL.")
