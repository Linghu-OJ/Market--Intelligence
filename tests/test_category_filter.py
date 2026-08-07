"""Manual test for filtering a saved Google Trends category snapshot.

Run from the project root with:
    python -m tests.test_category_filter
"""

from __future__ import annotations

from html import escape
import json
from pathlib import Path
from typing import Any

from pipeline.category_filter import CategoryFilter


def main() -> None:
    """Filter saved Trends output and create JSON and HTML reports."""
    snapshot_path = Path("reports/category_trends_output.json")
    if not snapshot_path.exists():
        raise FileNotFoundError(
            "Google Trends snapshot not found: reports/category_trends_output.json"
        )

    trends_output = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if not isinstance(trends_output, list) or not trends_output:
        raise ValueError("Google Trends snapshot must contain a non-empty list.")

    filtered_categories = CategoryFilter().filter(trends_output)
    ranked_categories = _sorted_results(filtered_categories)
    reports_path = Path("reports")
    reports_path.mkdir(exist_ok=True)

    output_path = reports_path / "category_filter_output.json"
    output_path.write_text(
        json.dumps(filtered_categories, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )

    report_path = reports_path / "category_filter_report.html"
    report_path.write_text(_html_report(ranked_categories), encoding="utf-8")

    pass_count = sum(
        result["filter"]["status"] == "PASS" for result in filtered_categories
    )
    excluded_count = sum(
        result["filter"].get("reason") == "Excluded category."
        for result in filtered_categories
    )
    unavailable_count = sum(
        result["filter"].get("reason") == "Google Trends data is unavailable."
        for result in filtered_categories
    )

    print(f"Total categories: {len(filtered_categories)}")
    print(f"PASS: {pass_count}")
    print(f"FAIL: {len(filtered_categories) - pass_count}")
    print(f"Excluded categories: {excluded_count}")
    print(f"Unavailable Google Trends data: {unavailable_count}")
    print(f"JSON output path: {output_path.resolve()}")
    print(f"HTML report path: {report_path.resolve()}")
    _print_ranking(ranked_categories)


def _html_report(results: list[dict[str, Any]]) -> str:
    """Render the sorted reporting copy of CategoryFilter results."""
    rows = "".join(_table_row(result) for result in results)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Category Filter Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2937; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #d1d5db; padding: 10px; text-align: left; }}
    th {{ background: #1f4c8f; color: #fff; position: sticky; top: 0; }}
    tr.pass {{ background: #dcfce7; }}
    tr.fail {{ background: #fee2e2; }}
  </style>
</head>
<body>
  <h1>Category Filter Report</h1>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Category ID</th><th>Category Name</th><th>Parent</th><th>Level</th>
          <th>Origin</th><th>Average Interest Score</th><th>Growth Score</th>
          <th>Filter Score</th><th>Status</th><th>Reason</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</body>
</html>"""


def _table_row(result: dict[str, Any]) -> str:
    """Render one escaped filter-result row without modifying category fields."""
    category = result["category"]
    metrics = result["filter"]
    status = metrics["status"]
    row_class = "pass" if status == "PASS" else "fail"
    return (
        f'<tr class="{row_class}"><td>{_display(category.get("id"))}</td>'
        f"<td>{_display(category.get('name'))}</td>"
        f"<td>{_display(category.get('parent'))}</td>"
        f"<td>{_display(category.get('level'))}</td>"
        f"<td>{_display(category.get('origin'))}</td>"
        f"<td>{_score(metrics.get('average_interest_score'))}</td>"
        f"<td>{_score(metrics.get('growth_score'))}</td>"
        f"<td>{_score(metrics.get('filter_score'))}</td>"
        f"<td>{_display(status)}</td>"
        f"<td>{_display(metrics.get('reason'))}</td></tr>"
    )


def _score(value: Any) -> str:
    """Format a score for display, leaving missing values as a dash."""
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        return f"{value:.2f}"
    return escape(str(value))


def _display(value: Any) -> str:
    """Escape an HTML cell value and show missing values as a dash."""
    return "-" if value is None else escape(str(value))


def _sorted_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create a descending filter-score copy without changing filter output."""
    return sorted(
        results,
        key=lambda result: result["filter"].get("filter_score")
        if result["filter"].get("filter_score") is not None
        else float("-inf"),
        reverse=True,
    )


def _print_ranking(results: list[dict[str, Any]]) -> None:
    """Print score-ranked categories and threshold-tuning summary statistics."""
    print("===== Filter Score Ranking =====")
    for index, result in enumerate(results, start=1):
        category = result["category"]
        metrics = result["filter"]
        print(f"{index}. {category.get('name', '-')}")
        print(f"   Average Interest: {_terminal_score(metrics.get('average_interest_score'))}")
        print(f"   Growth Score: {_terminal_score(metrics.get('growth_score'))}")
        print(f"   Filter Score: {_terminal_score(metrics.get('filter_score'))}")
        print(f"   Status: {metrics.get('status', '-')}")

    scores = [
        result["filter"].get("filter_score")
        for result in results
        if result["filter"].get("filter_score") is not None
    ]
    pass_count = sum(result["filter"].get("status") == "PASS" for result in results)
    print(f"Highest Filter Score: {_terminal_score(max(scores) if scores else None)}")
    print(f"Lowest Filter Score: {_terminal_score(min(scores) if scores else None)}")
    print(f"PASS count: {pass_count}")
    print(f"FAIL count: {len(results) - pass_count}")


def _terminal_score(value: Any) -> str:
    """Format a score for terminal output without altering the stored value."""
    return "-" if value is None else f"{value:.2f}"


if __name__ == "__main__":
    main()
