"""Manual integration test for the snapshot-to-Google-Trends category pipeline."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.category_feed_to_trends import CategoryOrchestrator


def main() -> None:
    """Run the complete category trends pipeline and save its raw results."""
    results = CategoryOrchestrator().run(
        collect_trends=True,
        refresh_departments=False,
    )

    assert isinstance(results, list)
    assert results

    status_counts = {"SUCCESS": 0, "NO_DATA": 0, "ERROR": 0}
    for item in results:
        assert "category" in item
        assert "google_trends" in item

        category = item["category"]
        trends = item["google_trends"]
        assert "id" in category
        assert "name" in category
        assert "status" in trends
        assert "interest_over_time" in trends
        assert trends["status"] in status_counts

        status_counts[trends["status"]] += 1

    output_path = Path("reports/category_trends_output.json")
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )

    print(f"Total categories: {len(results)}")
    print(f"SUCCESS: {status_counts['SUCCESS']}")
    print(f"NO_DATA: {status_counts['NO_DATA']}")
    print(f"ERROR: {status_counts['ERROR']}")
    print(f"Output path: {output_path.resolve()}")


if __name__ == "__main__":
    main()
