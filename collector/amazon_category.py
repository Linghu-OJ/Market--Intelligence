"""Collector for Amazon UK category links exposed by Best Sellers navigation."""

from __future__ import annotations

from datetime import UTC, datetime
from collections import deque
from html.parser import HTMLParser
from socket import timeout as SocketTimeout
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import ParseResult, urljoin, urlparse
from urllib.request import Request, urlopen


class _AmazonCategoryCollectorError(RuntimeError):
    """Base error raised when Amazon category collection cannot complete."""


class _AmazonCategoryNetworkError(_AmazonCategoryCollectorError):
    """Raised when Amazon UK cannot be reached successfully."""


class _AmazonCategoryParsingError(_AmazonCategoryCollectorError):
    """Raised when Amazon UK's category directory cannot be parsed."""


class _BestSellersNavigationParser(HTMLParser):
    """Extract anchor text and URLs from Amazon's Best Sellers navigation."""

    _VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.found_navigation = False
        self._navigation_depth: int | None = None
        self._navigation_tag: str | None = None
        self._open_tags: list[str] = []
        self._active_href: str | None = None
        self._active_text: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)
        if tag not in self._VOID_TAGS:
            self._open_tags.append(tag)

        if attributes.get("aria-label") == "Navigation Tree":
            self.found_navigation = True
            self._navigation_depth = len(self._open_tags)
            self._navigation_tag = tag

        if (
            self._navigation_depth is not None
            and tag == "a"
            and attributes.get("href")
        ):
            self._active_href = attributes["href"]
            self._active_text = []

    def handle_data(self, data: str) -> None:
        if self._active_href is not None:
            self._active_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._active_href is not None:
            self.links.append((" ".join(self._active_text), self._active_href))
            self._active_href = None
            self._active_text = []

        if self._navigation_depth is not None:
            is_navigation_end = (
                len(self._open_tags) == self._navigation_depth
                and self._navigation_tag == tag
            )
            if is_navigation_end:
                self._navigation_depth = None
                self._navigation_tag = None

        for index in range(len(self._open_tags) - 1, -1, -1):
            if self._open_tags[index] == tag:
                del self._open_tags[index:]
                break


class AmazonCategoryCollector:
    """Collect Amazon UK categories exposed by public Best Sellers navigation."""

    _ROOT_URL = "https://www.amazon.co.uk/gp/bestsellers"
    _REQUEST_TIMEOUT_SECONDS = 8
    _USER_AGENT = (
        "Mozilla/5.0 (compatible; AmazonCategoryCollector/1.0; "
        "+https://example.invalid/collector)"
    )

    def __init__(self) -> None:
        self._headers = {
            "Accept-Language": "en-GB,en;q=0.9",
            "User-Agent": self._USER_AGENT,
        }

    def collect(self) -> dict[str, Any]:
        """Return raw Amazon UK category data from public navigation pages.

        Raises:
            _AmazonCategoryNetworkError: If Amazon UK cannot be retrieved.
            _AmazonCategoryParsingError: If Amazon UK's page cannot be parsed.
        """
        html, page_url = self._fetch_page(self._ROOT_URL)
        roots = self._parse_categories(
            html=html,
            page_url=page_url,
            parent=None,
            level=1,
        )
        if not roots:
            raise _AmazonCategoryParsingError(
                "No categories were found in Amazon UK's root navigation. "
                "The page structure may have changed."
            )
        return {
            "source": "amazon",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {"categories": roots},
        }

    def _fetch_page(self, url: str) -> tuple[str, str]:
        """Request one public Amazon UK Best Sellers category page."""
        request = Request(url, headers=self._headers)

        try:
            with urlopen(
                request,
                timeout=self._REQUEST_TIMEOUT_SECONDS,
            ) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                html = response.read().decode(charset, errors="replace")
                page_url = response.geturl()
        except (SocketTimeout, TimeoutError) as error:
            raise _AmazonCategoryNetworkError(
                "Timed out while requesting an Amazon UK category page."
            ) from error
        except HTTPError as error:
            raise _AmazonCategoryNetworkError(
                f"Amazon UK returned HTTP {error.code} for a category page."
            ) from error
        except (URLError, OSError) as error:
            raise _AmazonCategoryNetworkError(
                "Could not retrieve an Amazon UK category page."
            ) from error

        if not html.strip():
            raise _AmazonCategoryParsingError(
                "Amazon UK returned an empty category-page response."
            )

        return html, page_url

    def _collect_category_tree(
        self,
        roots: list[dict[str, str | int | None]],
    ) -> list[dict[str, str | int | None]]:
        """Traverse category navigation until every reachable node is visited."""
        categories: list[dict[str, str | int | None]] = []
        pending = deque(roots)
        visited_urls: set[str] = set()

        while pending:
            category = pending.popleft()
            category_url = category["url"]
            if not isinstance(category_url, str):
                raise _AmazonCategoryParsingError(
                    "Amazon returned a category without a usable URL."
                )

            visit_key = self._visit_key(category_url)
            if visit_key in visited_urls:
                continue

            visited_urls.add(visit_key)
            categories.append(category)

            html, page_url = self._fetch_page(category_url)
            category_id = category["id"]
            category_level = category["level"]
            children = self._parse_categories(
                html=html,
                page_url=page_url,
                parent=category_id if isinstance(category_id, str) else None,
                level=category_level + 1
                if isinstance(category_level, int)
                else None,
            )
            pending.extend(children)

        return categories

    def _parse_categories(
        self,
        html: str,
        page_url: str,
        parent: str | None,
        level: int | None,
    ) -> list[dict[str, str | int | None]]:
        """Extract category links from one Best Sellers navigation tree."""
        parser = _BestSellersNavigationParser()
        parser.feed(html)
        parser.close()

        if not parser.found_navigation:
            raise _AmazonCategoryParsingError(
                "Amazon UK's category navigation was not found. "
                "The page may have changed or blocked this request."
            )

        categories: list[dict[str, str | int | None]] = []
        for name, href in parser.links:
            category = self._to_category(
                name=name.strip(),
                href=href,
                page_url=page_url,
                parent=parent,
                level=level,
            )
            if category is not None:
                categories.append(category)

        return categories

    def _to_category(
        self,
        name: str,
        href: str,
        page_url: str,
        parent: str | None,
        level: int | None,
    ) -> dict[str, str | int | None] | None:
        """Convert one public directory link to a raw category record."""
        url = urljoin(page_url, href)
        parsed_url = urlparse(url)

        if not self._is_amazon_category_url(parsed_url):
            return None

        category_id = self._category_id(parsed_url)

        return {
            "id": category_id,
            "name": name or None,
            "parent": parent,
            "level": level,
            "url": url,
        }

    @staticmethod
    def _is_amazon_category_url(parsed_url: ParseResult) -> bool:
        """Identify category URLs without following product or content links."""
        hostname = parsed_url.hostname or ""
        if hostname not in {"amazon.co.uk", "www.amazon.co.uk"}:
            return False

        if "/dp/" in parsed_url.path or "/gp/product/" in parsed_url.path:
            return False

        path_parts = [part for part in parsed_url.path.split("/") if part]
        if "zgbs" not in path_parts or not path_parts[-1].startswith("ref="):
            return False

        browse_index = path_parts.index("zgbs")
        return bool(path_parts[browse_index + 1:-1])

    @staticmethod
    def _category_id(parsed_url: ParseResult) -> str | None:
        """Return Amazon's visible Best Sellers category identifier, if present."""
        path_parts = [part for part in parsed_url.path.split("/") if part]
        browse_index = path_parts.index("zgbs")
        category_parts = path_parts[browse_index + 1:-1]

        if not category_parts:
            return None

        return category_parts[-1]

    @staticmethod
    def _visit_key(url: str) -> str:
        """Return a stable visit key without Amazon's tracking path segment."""
        parsed_url = urlparse(url)
        path_parts = [part for part in parsed_url.path.split("/") if part]
        browse_index = path_parts.index("zgbs")
        category_parts = path_parts[:browse_index + 1]
        category_parts.extend(path_parts[browse_index + 1:-1])
        return f"{parsed_url.scheme}://{parsed_url.netloc}/{'/'.join(category_parts)}"
