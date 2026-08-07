"""Split broad Amazon departments into canonical analysis categories."""

from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any


class DepartmentSplitter:
    """Convert mapped top-level department records into smaller categories."""

    DEPARTMENT_MAPPING = {
        "electronics-computers": [
            "Electronics",
            "Computers",
        ],
        "home-garden-diy": [
            "Home",
            "Kitchen",
            "Garden",
            "DIY",
        ],
        "toys-children-baby": [
            "Toys",
            "Baby",
        ],
        "clothes-shoes-watches": [
            "Clothing",
            "Shoes",
            "Watches",
        ],
        "sports-outdoors": [
            "Sports",
            "Outdoors",
        ],
        "food-grocery": [
            "Grocery",
        ],
        "health-beauty": [
            "Health",
            "Beauty",
        ],
        "car-motorbike": [
            "Automotive",
            "Motorbike",
        ],
        "business-industry-science": [
            "Business",
            "Industrial",
            "Science",
        ],
    }

    def split(self, collector_output: dict[str, Any]) -> dict[str, Any]:
        """Return canonical categories derived from collector department output.

        Mapped departments become their configured level-two categories. Unmapped
        department dictionaries are retained without changes.
        """
        categories = self._categories_from(collector_output)
        split_categories: list[dict[str, Any]] = []

        for category in categories:
            self._validate_category(category)
            split_categories.extend(self._split_category(category))

        return {
            "source": "department_splitter",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {"categories": self._remove_duplicates(split_categories)},
        }

    @staticmethod
    def _categories_from(collector_output: dict[str, Any]) -> list[dict[str, Any]]:
        """Validate and return the collector category list."""
        if not isinstance(collector_output, dict):
            raise ValueError("Collector output must be a dictionary.")

        data = collector_output.get("data")
        if not isinstance(data, dict):
            raise ValueError("Collector output requires a data dictionary.")

        categories = data.get("categories")
        if not isinstance(categories, list):
            raise ValueError("Collector output data.categories must be a list.")
        return categories

    @staticmethod
    def _validate_category(category: Any) -> None:
        """Validate the required original department identifier and name."""
        if not isinstance(category, dict):
            raise ValueError("Each category must be a dictionary.")

        for field in ("id", "name"):
            value = category.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Each category requires a non-empty {field}.")

    def _split_category(self, category: dict[str, Any]) -> list[dict[str, Any]]:
        """Create mapped children, or retain one unmapped department."""
        department_id = category["id"]
        mapped_names = self.DEPARTMENT_MAPPING.get(department_id)
        if mapped_names is None:
            return [category]

        return [
            {
                "id": self._slug(name),
                "name": name,
                "parent": department_id,
                "parent_name": category["name"],
                "level": 2,
                "url": category.get("url"),
            }
            for name in mapped_names
        ]

    @staticmethod
    def _slug(name: str) -> str:
        """Create a stable lowercase slug from a mapped category name."""
        slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
        return slug

    @staticmethod
    def _remove_duplicates(categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove repeated output identifiers while retaining their first order."""
        unique_categories: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for category in categories:
            category_id = category["id"]
            if category_id in seen_ids:
                continue
            seen_ids.add(category_id)
            unique_categories.append(category)
        return unique_categories
