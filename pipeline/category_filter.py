"""Filter orchestrated categories using existing Google Trends data only."""

from __future__ import annotations

import math
from statistics import fmean
from typing import Any


class CategoryFilter:
    """Score category demand signals to gate Product Collector work."""

    EXCLUDED_CATEGORIES = [
        "Amazon Fresh",
        "Grocery",
        "Food",
        "Fresh Food",
        "Alcohol",
        "Medicine",
        "Pharmacy",
        "Medical Devices",
        "Health",
        "Highly Regulated Categories",
    ]

    EXCLUDED_NON_PHYSICAL_CATEGORIES = [
        "Alexa Skills",
        "Apps & Games",
        "Audible Audiobooks",
        "Books",
        "CDs & Vinyl",
        "Digital Music",
        "DVD & Blu-ray",
        "Gift Cards",
        "Kindle Store",
        "Prime Video",
        "Software",
    ]

    EXCLUDED_PLATFORM_CATEGORIES = [
        "Amazon Devices",
        "Amazon Global Store",
        "Amazon Haul",
        "Amazon Resale",
    ]

    FILTER_THRESHOLD = 63

    def filter(self, orchestrator_output: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return filter results for every item from ``CategoryOrchestrator``.

        This method uses only the Google Trends interest-over-time values already
        present in ``orchestrator_output``. It does not collect, remove, or
        otherwise modify category data.
        """
        if not isinstance(orchestrator_output, list):
            raise ValueError("Category filter input must be a list of orchestrator items.")

        return [self._filter_item(item) for item in orchestrator_output]

    def _filter_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Build one category result while preserving the original category."""
        category = item.get("category") if isinstance(item, dict) else None
        if not isinstance(category, dict):
            raise ValueError("Each orchestrator item must contain a category dictionary.")

        category_name = category.get("name")
        if not isinstance(category_name, str) or not category_name:
            raise ValueError("Each category must contain a non-empty name.")

        if self._is_excluded(category_name):
            return {"category": category, "filter": self._unavailable_filter("Excluded category.")}

        trends = item.get("google_trends")
        if not isinstance(trends, dict) or trends.get("status") != "SUCCESS":
            return {
                "category": category,
                "filter": self._unavailable_filter("Google Trends data is unavailable."),
            }

        values = self._interest_values(trends.get("interest_over_time"))
        if not values:
            return {
                "category": category,
                "filter": self._unavailable_filter("Google Trends data is unavailable."),
            }

        average_score = fmean(values)
        growth_score = self._growth_score(values)
        filter_score = (
            0.60 * average_score
            + 0.40 * growth_score
        )

        return {
            "category": category,
            "filter": {
                "average_interest_score": average_score,
                "growth_score": growth_score,
                "filter_score": filter_score,
                "status": "PASS" if filter_score >= self.FILTER_THRESHOLD else "FAIL",
                }
        }

    def _is_excluded(self, category_name: str) -> bool:
        """Check the category against all configurable exclusion lists."""
        category = category_name.casefold()

        excluded = {
            name.casefold()
            for name in (
                self.EXCLUDED_CATEGORIES
                + self.EXCLUDED_NON_PHYSICAL_CATEGORIES
                + self.EXCLUDED_PLATFORM_CATEGORIES
            )
        }

        return category in excluded

    @staticmethod
    def _unavailable_filter(reason: str) -> dict[str, Any]:
        """Return a non-passing result when no score can be calculated."""
        return {
                "average_interest_score": None,
                "growth_score": None,
                "filter_score": None,
                "status": "FAIL",
                "reason": reason,
            }           

    @staticmethod
    def _interest_values(timeline: Any) -> list[float]:
        """Read raw normalized interest values from a Google Trends timeline."""
        if not isinstance(timeline, list):
            return []

        values: list[float] = []
        for observation in timeline:
            value = CategoryFilter._interest_value(observation)
            if value is None:
                return []
            values.append(value)
        return values

    @staticmethod
    def _interest_value(observation: Any) -> float | None:
        """Extract one raw value from SerpAPI's timeline observation format."""
        if not isinstance(observation, dict):
            return None

        if "value" in observation:
            return CategoryFilter._numeric_value(observation["value"])

        values = observation.get("values")
        if not isinstance(values, list) or len(values) != 1:
            return None

        raw_value = values[0]
        if not isinstance(raw_value, dict):
            return None
        return CategoryFilter._numeric_value(
            raw_value.get("extracted_value", raw_value.get("value"))
        )

    @staticmethod
    def _numeric_value(value: Any) -> float | None:
        """Convert a raw numeric interest value without changing its meaning."""
        if isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _growth_score(values: list[float]) -> float:
        """Calculate the bounded OLS slope score for the interest timeline."""
        if len(values) == 1:
            slope = 0.0
        else:
            times = range(len(values))
            mean_time = (len(values) - 1) / 2
            mean_value = fmean(values)
            numerator = sum(
                (time - mean_time) * (value - mean_value)
                for time, value in zip(times, values)
            )
            denominator = sum((time - mean_time) ** 2 for time in times)
            slope = numerator / denominator

        return 50 + 50 * math.tanh(slope / 5)


