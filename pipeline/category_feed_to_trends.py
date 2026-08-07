from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from collector.amazon_department import AmazonDepartmentCollector
from collector.google_trends import GoogleTrendsCollector
from processor.category_merger import CategoryMerger
from processor.department_splitter import DepartmentSplitter
from processor.manual_seed_expander import ManualSeedExpander


class CategoryOrchestrator:
    """Build the final category list and optionally collect Google Trends data."""

    DEPARTMENT_SNAPSHOT_PATH = Path("data/amazon_departments.json")

    def __init__(self) -> None:
        self.amazon = AmazonDepartmentCollector()
        self.splitter = DepartmentSplitter()
        self.manual_seed_expander = ManualSeedExpander()
        self.category_merger = CategoryMerger()
        self.google_trends = GoogleTrendsCollector()

    def run(
        self,
        collect_trends: bool = True,
        refresh_departments: bool = False,
    ) -> dict[str, Any] | list[dict[str, Any]]:

        department_output = self._get_department_output(
            refresh_departments=refresh_departments
        )

        splitter_output = self.splitter.split(department_output)
        manual_seed_output = self.manual_seed_expander.expand()

        merged_output = self.category_merger.merge(
            splitter_output,
            manual_seed_output,
        )

        categories = merged_output["data"]["categories"]

        print(f"Final merged category count: {len(categories)}")

        if not collect_trends:
            return merged_output

        output: list[dict[str, Any]] = []
        total_categories = len(categories)

        for index, category in enumerate(categories, start=1):
            trends_data = self._collect_trends(category)
            status = trends_data.get("status", "ERROR")

            print(
                f"[{index}/{total_categories}] "
                f"{category['name']} ........ {status}"
            )

            output.append(
                {
                    "category": category,
                    "google_trends": trends_data,
                }
            )

        return output

    def _get_department_output(
        self,
        refresh_departments: bool,
    ) -> dict[str, Any]:

        if refresh_departments:
            department_output = self.amazon.collect()
            self._save_department_snapshot(department_output)
            return department_output

        if self.DEPARTMENT_SNAPSHOT_PATH.exists():
            return self._load_department_snapshot()

        department_output = self.amazon.collect()
        self._save_department_snapshot(department_output)
        return department_output

    def _save_department_snapshot(
        self,
        department_output: dict[str, Any],
    ) -> None:

        self.DEPARTMENT_SNAPSHOT_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.DEPARTMENT_SNAPSHOT_PATH.write_text(
            json.dumps(
                department_output,
                indent=4,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def _load_department_snapshot(self) -> dict[str, Any]:

        try:
            data = json.loads(
                self.DEPARTMENT_SNAPSHOT_PATH.read_text(
                    encoding="utf-8"
                )
            )
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(
                "Could not load Amazon department snapshot."
            ) from error

        if not isinstance(data, dict):
            raise RuntimeError(
                "Amazon department snapshot has an invalid format."
            )

        return data

    def _collect_trends(
        self,
        category: dict[str, Any],
    ) -> dict[str, Any]:

        try:
            return self.google_trends.collect(category["name"])
        except Exception as error:
            return {
                "status": "ERROR",
                "interest_over_time": [],
                "raw_response": None,
                "reason": str(error),
            }