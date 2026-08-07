"""Merge split departments and manual seeds into one category list."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


class CategoryMerger:
    """Combine category outputs while retaining first-seen records."""

    def merge(
        self,
        splitter_output: dict[str, Any],
        manual_seed_output: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge splitter categories first, then non-duplicate manual seeds."""
        splitter_categories = self._categories_from(splitter_output, "splitter_output")
        manual_categories = self._categories_from(
            manual_seed_output,
            "manual_seed_output",
        )

        return {
            "source": "category_merger",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "categories": self._remove_duplicates(
                    splitter_categories + manual_categories
                )
            },
        }

    def _categories_from(
        self,
        output: dict[str, Any],
        output_name: str,
    ) -> list[dict[str, Any]]:
        """Validate and return one input's category list."""
        if not isinstance(output, dict):
            raise ValueError(f"{output_name} must be a dictionary.")

        data = output.get("data")
        if not isinstance(data, dict):
            raise ValueError(f"{output_name}.data must be a dictionary.")

        categories = data.get("categories")
        if not isinstance(categories, list):
            raise ValueError(f"{output_name}.data.categories must be a list.")

        for category in categories:
            self._validate_category(category)
        return categories

    @staticmethod
    def _validate_category(category: Any) -> None:
        """Validate required category identity fields."""
        if not isinstance(category, dict):
            raise ValueError("Each category must be a dictionary.")

        for field in ("id", "name"):
            value = category.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Each category requires a non-empty string {field}.")

    @staticmethod
    def _remove_duplicates(categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Retain the first category for each case-insensitive id or name."""
        merged_categories: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        seen_names: set[str] = set()

        for category in categories:
            category_id = category["id"].casefold()
            category_name = category["name"].casefold()
            if category_id in seen_ids or category_name in seen_names:
                continue

            seen_ids.add(category_id)
            seen_names.add(category_name)
            merged_categories.append(category)
        return merged_categories
