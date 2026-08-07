"""Canonical category mappings to Amazon UK's top-level departments."""

from __future__ import annotations


CATEGORY_TO_AMAZON_DEPARTMENT: dict[str, str] = {
    "Amazon Fresh": "Amazon Fresh",
    "Books": "Books",
    "Films, TV, Music & Games": "Films, TV, Music & Games",
    "Electronics": "Electronics & Computers",
    "Computers": "Electronics & Computers",
    "Home": "Home, Garden & DIY",
    "Kitchen": "Home, Garden & DIY",
    "Garden": "Home, Garden & DIY",
    "DIY": "Home, Garden & DIY",
    "Toys": "Toys, Children & Baby",
    "Baby": "Toys, Children & Baby",
    "Clothing": "Clothes, Shoes & Watches",
    "Shoes": "Clothes, Shoes & Watches",
    "Watches": "Clothes, Shoes & Watches",
    "Sports": "Sports & Outdoors",
    "Outdoors": "Sports & Outdoors",
    "Grocery": "Food & Grocery",
    "Health": "Health & Beauty",
    "Beauty": "Health & Beauty",
    "Automotive": "Car & Motorbike",
    "Motorbike": "Car & Motorbike",
    "Business": "Business, Industry & Science",
    "Industrial": "Business, Industry & Science",
    "Science": "Business, Industry & Science",
    "Pet": "Home, Garden & DIY",
    "Office": "Business, Industry & Science",
}

AMAZON_TOP_LEVEL_DEPARTMENTS: set[str] = {
    "Amazon Fresh",
    "Books",
    "Films, TV, Music & Games",
    "Electronics & Computers",
    "Home, Garden & DIY",
    "Toys, Children & Baby",
    "Clothes, Shoes & Watches",
    "Sports & Outdoors",
    "Food & Grocery",
    "Health & Beauty",
    "Car & Motorbike",
    "Business, Industry & Science",
}


def _validate_mapping() -> None:
    """Validate the canonical category-to-department configuration."""
    if len(CATEGORY_TO_AMAZON_DEPARTMENT) != 26:
        raise ValueError("Category mapping must contain exactly 26 categories.")

    for category, department in CATEGORY_TO_AMAZON_DEPARTMENT.items():
        if not isinstance(category, str) or not category.strip():
            raise ValueError("Canonical category keys must be non-empty strings.")
        if not isinstance(department, str) or not department.strip():
            raise ValueError("Amazon department values must be non-empty strings.")
        if department not in AMAZON_TOP_LEVEL_DEPARTMENTS:
            raise ValueError(
                f"Amazon department target is not valid: {department!r}."
            )


_validate_mapping()
