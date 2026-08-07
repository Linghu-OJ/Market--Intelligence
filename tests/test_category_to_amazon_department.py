"""Manual test for canonical category-to-Amazon department configuration."""

from config.category_to_amazon_department import (
    AMAZON_TOP_LEVEL_DEPARTMENTS,
    CATEGORY_TO_AMAZON_DEPARTMENT,
)


def main() -> None:
    """Validate configuration targets and display categories by department."""
    assert len(CATEGORY_TO_AMAZON_DEPARTMENT) == 26
    assert len(AMAZON_TOP_LEVEL_DEPARTMENTS) == 12
    assert all(
        department in AMAZON_TOP_LEVEL_DEPARTMENTS
        for department in CATEGORY_TO_AMAZON_DEPARTMENT.values()
    )
    assert set(CATEGORY_TO_AMAZON_DEPARTMENT.values()) == AMAZON_TOP_LEVEL_DEPARTMENTS
    assert CATEGORY_TO_AMAZON_DEPARTMENT["Pet"] == "Home, Garden & DIY"
    assert CATEGORY_TO_AMAZON_DEPARTMENT["Office"] == "Business, Industry & Science"
    assert (
        CATEGORY_TO_AMAZON_DEPARTMENT["Electronics"]
        == CATEGORY_TO_AMAZON_DEPARTMENT["Computers"]
    )
    assert {
        CATEGORY_TO_AMAZON_DEPARTMENT[category]
        for category in ("Home", "Kitchen", "Garden", "DIY")
    } == {"Home, Garden & DIY"}

    for department in sorted(AMAZON_TOP_LEVEL_DEPARTMENTS):
        categories = [
            category
            for category, target in CATEGORY_TO_AMAZON_DEPARTMENT.items()
            if target == department
        ]
        print(f"{department}: {', '.join(categories)}")


if __name__ == "__main__":
    main()
