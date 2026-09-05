MOCK_CATALOG = {
    "electronics": [
        {"id": "item_laptop_001", "name": "MacBook Pro M3", "price": 140000, "merchant_name": "Apple India"},
        {"id": "item_laptop_002", "name": "Dell XPS 15", "price": 110000, "merchant_name": "Dell Store"},
        {"id": "item_laptop_003", "name": "Lenovo ThinkPad", "price": 65000, "merchant_name": "Amazon India"},
        {"id": "item_phone_001", "name": "iPhone 15", "price": 80000, "merchant_name": "Apple India"},
    ],
    "furniture": [
        {"id": "item_chair_001", "name": "Ergonomic Office Chair", "price": 15000, "merchant_name": "IKEA"},
        {"id": "item_desk_001", "name": "Standing Desk", "price": 35000, "merchant_name": "Pepperfry"},
    ],
    "software": [
        {"id": "item_sub_001", "name": "GitHub Copilot Yearly", "price": 10000, "merchant_name": "GitHub"},
        {"id": "item_sub_002", "name": "Adobe Creative Cloud", "price": 50000, "merchant_name": "Adobe Systems"},
    ]
}

def get_catalog_str() -> str:
    """Returns a string representation of the catalog for the LLM prompt."""
    import json
    return json.dumps(MOCK_CATALOG, indent=2)
