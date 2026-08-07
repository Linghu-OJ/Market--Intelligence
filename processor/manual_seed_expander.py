"""Generate canonical category records from manually defined seed names."""

from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any


class ManualSeedExpander:
    """Expand configured manual category seeds into category records."""

    MANUAL_SEEDS = [
        "Pet",
        "Office",
    ]

    def expand(self) -> dict[str, Any]:
        """Return one canonical category record for each unique manual seed."""
        categories = self._categories_from_seeds()
        return {
            "source": "manual_seed_expander",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {"categories": categories},
        }

    def _categories_from_seeds(self) -> list[dict[str, Any]]:
        """Validate and expand seeds while preserving their first-seen order."""
        categories: list[dict[str, Any]] = []
        seen_seeds: set[str] = set()

        for seed in self.MANUAL_SEEDS:
            self._validate_seed(seed)
            normalized_seed = seed.casefold()
            if normalized_seed in seen_seeds:
                continue

            seen_seeds.add(normalized_seed)
            categories.append(
                {
                    "id": self._slug(seed),
                    "name": seed,
                    "parent": None,
                    "parent_name": None,
                    "level": 1,
                    "url": None,
                    "origin": "manual_seed",
                }
            )
        return categories

    @staticmethod
    def _validate_seed(seed: Any) -> None:
        """Raise when a configured seed is not a non-empty string."""
        if not isinstance(seed, str) or not seed.strip():
            raise ValueError("Manual seeds must be non-empty strings.")

    @staticmethod
    def _slug(seed: str) -> str:
        """Create a stable lowercase slug identifier for a manual seed."""
        return re.sub(r"[^a-z0-9]+", "-", seed.casefold()).strip("-")
