"""Manual integration test for AmazonDepartmentCollector.

Run from the project root with:
    python -m tests.test_amazon_department
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from collector.amazon_department import AmazonDepartmentCollector


def main() -> None:
    """Collect, validate, display, and report Amazon UK departments."""
    result = AmazonDepartmentCollector(headless=False).collect()

    assert isinstance(result, dict)
    assert result["source"] == "amazon_department"
    categories = result["data"]["categories"]
    assert isinstance(categories, list)
    assert categories

    department_ids = set()
    for category in categories:
        assert {"id", "name", "parent", "level", "url"} <= category.keys()
        assert isinstance(category["name"], str) and category["name"]
        assert category["parent"] is None
        assert category["level"] == 1
        assert category["url"].startswith(("https://amazon.co.uk/", "https://www.amazon.co.uk/"))
        assert category["id"] not in department_ids
        department_ids.add(category["id"])

    print(f"Total departments: {len(categories)}")
    print("First 10 departments:")
    for category in categories[:10]:
        print(f"{category['name']}: {category['url']}")

    report_path = Path("reports/amazon_department_report.html")
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(_report_html(result), encoding="utf-8")
    print(f"Report generated: {report_path.resolve()}")


def _report_html(result: dict) -> str:
    """Build the requested clickable department table report."""
    categories = result["data"]["categories"]
    rows = "".join(
        "<tr>"
        f"<td>{escape(str(category['id']))}</td>"
        f"<td>{escape(category['name'])}</td>"
        f"<td>{category['level']}</td>"
        f'<td><a href="{escape(category["url"], quote=True)}" target="_blank" '
        f'rel="noopener">{escape(category["url"])}</a></td>'
        "</tr>"
        for category in categories
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Amazon UK Departments</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2937; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #d1d5db; padding: 10px; text-align: left; }}
    th {{ background: #1f4c8f; color: white; position: sticky; top: 0; }}
    tr:nth-child(even) {{ background: #f8fafc; }}
  </style>
</head>
<body>
  <h1>Amazon UK Departments</h1>
  <p>Source: {escape(result['source'])}</p>
  <p>Timestamp: {escape(result['timestamp'])}</p>
  <p>Total department count: {len(categories)}</p>
  <div class="table-wrap">
    <table>
      <thead><tr><th>ID</th><th>Department name</th><th>Level</th><th>URL</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</body>
</html>"""


if __name__ == "__main__":
    main()
