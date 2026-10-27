"""Explicit fictional fixtures. Never loaded silently or mixed with real data."""
from pof.models import Product


def demo_products():
    result = []
    for index, (title, category, cost, sale) in enumerate([
        ("Demo USB-C Hub 8 Port", "Electronics", 12, 39.99),
        ("Demo Bottle 750 ml", "Home", 4, 22.99),
        ("Demo Travel Organizer 3 Pack", "Travel", 6, 27.99),
        ("Demo Desk Lamp", "Home", 11, 35.99),
    ]):
        for source, role, price in [("Demo Supplier", "supplier", cost),
                                     ("Demo Retailer A", "retailer", sale),
                                     ("Demo Retailer B", "retailer", sale + 10)]:
            p = Product(source, title, role=role, brand="Demo", model=f"DEMO-{index}",
                gtin=f"000000000000{index}", category=category, price=price, shipping=2 if role == "supplier" else 0,
                moq=1, delivery_days=7, rating=4.3, reviews=85, supplier_country="US",
                availability="in_stock", fragile=False, restricted=False, weight_kg=0.4,
                monthly_searches=1000 + index * 300, competition_index=40, cpc=0.8, demo=True,
                specs={"variant": f"demo-{index}"})
            # Verified means verified within the fictional fixture, never real-world evidence.
            p.states = {k: "verified" for k in p.record()}
            result.append(p)
    return result
