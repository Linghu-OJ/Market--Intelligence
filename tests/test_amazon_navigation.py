"""Manual experiment for one Amazon UK Kitchen navigation entry."""

from collector.amazon_navigation import AmazonNavigationCollector


def main() -> None:
    """Collect and validate two-depth navigation nodes for one Kitchen entry."""
    entry = {
        "canonical_category": "Kitchen",
        "amazon_department": "Home, Garden & DIY",
        "url": "https://www.amazon.co.uk/b?node=11052681",
    }
    result = AmazonNavigationCollector(headless=False, max_depth=2).collect(entry)

    assert isinstance(result, dict)
    assert result["source"] == "amazon_navigation"
    nodes = result["data"]["nodes"]
    assert nodes

    excluded_names = {
        "best sellers", "deals", "today's deals", "new releases", "shop now",
        "sign in", "account", "orders", "customer service", "help", "gift cards",
        "prime", "see all", "see less", "back",
    }
    for node in nodes:
        assert node["depth"] <= 2
        assert node["url"].startswith(("https://amazon.co.uk/", "https://www.amazon.co.uk/"))
        assert "/dp/" not in node["url"]
        assert "/gp/product/" not in node["url"]
        assert node["name"].casefold() not in excluded_names

    depth_one_count = sum(node["depth"] == 1 for node in nodes)
    depth_two_count = sum(node["depth"] == 2 for node in nodes)
    print(f"Total nodes: {len(nodes)}")
    print(f"Depth=1 nodes: {depth_one_count}")
    print(f"Depth=2 nodes: {depth_two_count}")
    print(f"Errors: {len(result['data']['errors'])}")

    for node in nodes[:20]:
        print(f"[{node['depth']}] {node['parent_name']} -> {node['name']} -> {node['url']}")


if __name__ == "__main__":
    main()
