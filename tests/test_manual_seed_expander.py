"""Manual test for ManualSeedExpander."""

from processor.manual_seed_expander import ManualSeedExpander


def main() -> None:
    """Expand the configured seeds and verify their category records."""
    result = ManualSeedExpander().expand()

    assert isinstance(result, dict)
    assert result["source"] == "manual_seed_expander"
    categories = result["data"]["categories"]
    assert isinstance(categories, list)
    assert [category["name"] for category in categories] == ["Pet", "Office"]
    assert [category["id"] for category in categories] == ["pet", "office"]

    for category in categories:
        assert category["parent"] is None
        assert category["parent_name"] is None
        assert category["level"] == 1
        assert category["url"] is None
        assert category["origin"] == "manual_seed"

    category_ids = [category["id"] for category in categories]
    assert len(category_ids) == len(set(category_ids))

    print("Generated categories:")
    for category in categories:
        print(category["name"])


if __name__ == "__main__":
    main()
