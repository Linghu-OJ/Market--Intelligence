"""Manual live test for AmazonCategoryCollector.

Run from the project root with:
    python -m tests.test_amazon_category
"""

from collector.amazon_category import AmazonCategoryCollector


def main() -> None:
    """Run the collector and display a compact view of its raw response."""
    collector = AmazonCategoryCollector()
    raw_data = collector.collect()
    categories = raw_data["data"]["categories"]

    print(f"Returned object type: {type(raw_data)}")
    print(f"Total number of categories: {len(categories)}")
    print("First 10 categories:")

    for category in categories[:10]:
        print(category)


if __name__ == "__main__":
    main()
