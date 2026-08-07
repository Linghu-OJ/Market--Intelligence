from __future__ import annotations

from typing import Any

from pipeline.category_feed_to_trends import CategoryOrchestrator


def main() -> None:
    orchestrator = CategoryOrchestrator()

    result = orchestrator.run(
        collect_trends=True,
        refresh_departments=False
    )

    if not isinstance(result, dict):
        raise AssertionError(
            "Expected merged category output when collect_trends=False."
        )

    assert result.get("source") == "category_merger"

    data = result.get("data")
    assert isinstance(data, dict)

    categories = data.get("categories")
    assert isinstance(categories, list)
    assert categories

    seen_ids: set[str] = set()
    seen_names: set[str] = set()

    print(f"Total categories: {len(categories)}")
    print("Final merged categories:")

    for index, category in enumerate(categories, start=1):
        _validate_category(category)

        category_id = category["id"]
        category_name = category["name"]
        normalized_name = category_name.casefold()

        assert category_id not in seen_ids, (
            f"Duplicate category id: {category_id}"
        )

        assert normalized_name not in seen_names, (
            f"Duplicate category name: {category_name}"
        )

        seen_ids.add(category_id)
        seen_names.add(normalized_name)

        print(
            f"{index}. {category_name} "
            f"(id={category_id}, "
            f"level={category.get('level')}, "
            f"origin={category.get('origin', '-')}, "
            f"parent={category.get('parent')})"
        )

    print("Category orchestrator test passed.")


def _validate_category(category: Any) -> None:
    """Validate the minimum merged category contract."""
    assert isinstance(category, dict)

    category_id = category.get("id")
    category_name = category.get("name")

    assert isinstance(category_id, str)
    assert category_id

    assert isinstance(category_name, str)
    assert category_name

    assert "parent" in category
    assert "level" in category
    assert "url" in category

    level = category["level"]
    assert isinstance(level, int)
    assert level >= 1

    parent = category["parent"]
    assert parent is None or isinstance(parent, str)

    parent_name = category.get("parent_name")
    assert parent_name is None or isinstance(parent_name, str)

    url = category["url"]
    assert url is None or isinstance(url, str)


if __name__ == "__main__":
    main()