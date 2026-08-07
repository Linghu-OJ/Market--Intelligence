"""Manual test for DepartmentSplitter."""

from processor.department_splitter import DepartmentSplitter


def main() -> None:
    """Split sample department data and assert the required behavior."""
    sample_input = {
        "source": "amazon_department",
        "timestamp": "2026-08-07T00:00:00+00:00",
        "data": {
            "categories": [
                {
                    "id": "home-garden-diy",
                    "name": "Home, Garden & DIY",
                    "parent": None,
                    "level": 1,
                    "url": "https://www.amazon.co.uk/home",
                },
                {
                    "id": "electronics-computers",
                    "name": "Electronics & Computers",
                    "parent": None,
                    "level": 1,
                    "url": "https://www.amazon.co.uk/electronics",
                },
                {
                    "id": "books",
                    "name": "Books",
                    "parent": None,
                    "level": 1,
                    "url": "https://www.amazon.co.uk/books",
                },
            ]
        },
    }

    result = DepartmentSplitter().split(sample_input)
    categories = result["data"]["categories"]

    assert [category["name"] for category in categories] == [
        "Home",
        "Kitchen",
        "Garden",
        "DIY",
        "Electronics",
        "Computers",
        "Books",
    ]
    assert categories[0]["parent"] == "home-garden-diy"
    assert categories[0]["parent_name"] == "Home, Garden & DIY"
    assert categories[0]["url"] == "https://www.amazon.co.uk/home"
    assert categories[-1] == sample_input["data"]["categories"][-1]

    category_ids = [category["id"] for category in categories]
    assert len(category_ids) == len(set(category_ids))

    print("Resulting categories:")
    for category in categories:
        print(category["name"])


if __name__ == "__main__":
    main()
