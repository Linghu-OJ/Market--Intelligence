"""Manual test for CategoryMerger."""

from copy import deepcopy
from html import escape
from pathlib import Path

from processor.department_splitter import DepartmentSplitter
from processor.manual_seed_expander import ManualSeedExpander
from processor.category_merger import CategoryMerger


def main() -> None:
    """Merge hardcoded categories and validate first-occurrence behavior."""
    department_fixture = _department_fixture()
    splitter_output = DepartmentSplitter().split(department_fixture)
    manual_seed_output = ManualSeedExpander().expand()
    splitter_before = deepcopy(splitter_output)
    manual_before = deepcopy(manual_seed_output)

    merged_output = CategoryMerger().merge(
        splitter_output,
        manual_seed_output,
    )
    categories = merged_output["data"]["categories"]

    assert merged_output["source"] == "category_merger"
    assert isinstance(categories, list)
    assert categories
    assert splitter_output == splitter_before
    assert manual_seed_output == manual_before

    ids = [category["id"] for category in categories]
    names = [category["name"].casefold() for category in categories]
    assert len(ids) == len(set(ids))
    assert len(names) == len(set(names))

    report_path = Path("reports/category_merger_report.html")
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(
        _report_html(
            result=merged_output,
            splitter_count=len(splitter_output["data"]["categories"]),
            manual_seed_count=len(manual_seed_output["data"]["categories"]),
        ),
        encoding="utf-8",
    )

    print("Merged categories:")
    for category in categories:
        print(category["name"])
    print(f"Total merged categories: {len(categories)}")
    print(f"Report path: {report_path.resolve()}")


def _department_fixture() -> dict:
    """Return fixed Amazon UK top-level departments for merger testing."""
    return {
        "source": "amazon_department",
        "timestamp": "2026-08-07T00:00:00+00:00",
        "data": {
            "categories": [
                _department("amazon-fresh", "Amazon Fresh"),
                _department("books", "Books"),
                _department("films-tv-music-games", "Films, TV, Music & Games"),
                _department("electronics-computers", "Electronics & Computers"),
                _department("home-garden-diy", "Home, Garden & DIY"),
                _department("toys-children-baby", "Toys, Children & Baby"),
                _department("clothes-shoes-watches", "Clothes, Shoes & Watches"),
                _department("sports-outdoors", "Sports & Outdoors"),
                _department("food-grocery", "Food & Grocery"),
                _department("health-beauty", "Health & Beauty"),
                _department("car-motorbike", "Car & Motorbike"),
                _department(
                    "business-industry-science",
                    "Business, Industry & Science",
                ),
            ]
        },
    }


def _department(identifier: str, name: str) -> dict:
    """Create one realistic top-level Amazon department fixture record."""
    return {
        "id": identifier,
        "name": name,
        "parent": None,
        "level": 1,
        "url": f"https://www.amazon.co.uk/gp/browse.html?node={identifier}",
    }


def _report_html(
    result: dict,
    splitter_count: int,
    manual_seed_count: int,
) -> str:
    """Create an HTML table that preserves merged category order."""
    categories = result["data"]["categories"]
    rows = "".join(_table_row(category) for category in categories)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Category Merger Report</title>
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
  <h1>Category Merger Report</h1>
  <p>Source: {escape(str(result['source']))}</p>
  <p>Timestamp: {escape(str(result['timestamp']))}</p>
  <p>Total merged category count: {len(categories)}</p>
  <p>Total categories from DepartmentSplitter: {splitter_count}</p>
  <p>Total categories from ManualSeedExpander: {manual_seed_count}</p>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>ID</th><th>Name</th><th>Parent</th><th>Parent Name</th>
          <th>Level</th><th>Origin</th><th>URL</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</body>
</html>"""


def _table_row(category: dict) -> str:
    """Render one escaped merged-category row without changing its fields."""
    url = category.get("url")
    url_cell = "-"
    if url is not None:
        escaped_url = escape(str(url), quote=True)
        url_cell = f'<a href="{escaped_url}" target="_blank" rel="noopener">{escaped_url}</a>'

    cells = [
        _display_value(category.get("id")),
        _display_value(category.get("name")),
        _display_value(category.get("parent")),
        _display_value(category.get("parent_name")),
        _display_value(category.get("level")),
        _display_value(category.get("origin")),
    ]
    return "<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + f"<td>{url_cell}</td></tr>"


def _display_value(value: object) -> str:
    """Escape a value for HTML, displaying ``None`` as a dash."""
    return "-" if value is None else escape(str(value))


if __name__ == "__main__":
    main()
