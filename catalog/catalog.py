# catalog/catalog.py — Paper supplies catalog and lookup utilities

from typing import Dict, List, Optional

# List containing the different kinds of papers
paper_supplies: List[Dict] = [
    # Paper Types (priced per sheet unless specified)
    {"item_name": "A4 paper",                         "category": "paper",        "unit_price": 0.05},
    {"item_name": "Letter-sized paper",              "category": "paper",        "unit_price": 0.06},
    {"item_name": "Cardstock",                        "category": "paper",        "unit_price": 0.15},
    {"item_name": "Colored paper",                    "category": "paper",        "unit_price": 0.10},
    {"item_name": "Glossy paper",                     "category": "paper",        "unit_price": 0.20},
    {"item_name": "Matte paper",                      "category": "paper",        "unit_price": 0.18},
    {"item_name": "Recycled paper",                   "category": "paper",        "unit_price": 0.08},
    {"item_name": "Eco-friendly paper",               "category": "paper",        "unit_price": 0.12},
    {"item_name": "Poster paper",                     "category": "paper",        "unit_price": 0.25},
    {"item_name": "Banner paper",                     "category": "paper",        "unit_price": 0.30},
    {"item_name": "Kraft paper",                      "category": "paper",        "unit_price": 0.10},
    {"item_name": "Construction paper",               "category": "paper",        "unit_price": 0.07},
    {"item_name": "Wrapping paper",                   "category": "paper",        "unit_price": 0.15},
    {"item_name": "Glitter paper",                    "category": "paper",        "unit_price": 0.22},
    {"item_name": "Decorative paper",                 "category": "paper",        "unit_price": 0.18},
    {"item_name": "Letterhead paper",                 "category": "paper",        "unit_price": 0.12},
    {"item_name": "Legal-size paper",                 "category": "paper",        "unit_price": 0.08},
    {"item_name": "Crepe paper",                      "category": "paper",        "unit_price": 0.05},
    {"item_name": "Photo paper",                      "category": "paper",        "unit_price": 0.25},
    {"item_name": "Uncoated paper",                   "category": "paper",        "unit_price": 0.06},
    {"item_name": "Butcher paper",                    "category": "paper",        "unit_price": 0.10},
    {"item_name": "Heavyweight paper",                "category": "paper",        "unit_price": 0.20},
    {"item_name": "Standard copy paper",              "category": "paper",        "unit_price": 0.04},
    {"item_name": "Bright-colored paper",             "category": "paper",        "unit_price": 0.12},
    {"item_name": "Patterned paper",                  "category": "paper",        "unit_price": 0.15},

    # Product Types (priced per unit)
    {"item_name": "Paper plates",                     "category": "product",      "unit_price": 0.10},
    {"item_name": "Paper cups",                       "category": "product",      "unit_price": 0.08},
    {"item_name": "Paper napkins",                    "category": "product",      "unit_price": 0.02},
    {"item_name": "Disposable cups",                  "category": "product",      "unit_price": 0.10},
    {"item_name": "Table covers",                     "category": "product",      "unit_price": 1.50},
    {"item_name": "Envelopes",                        "category": "product",      "unit_price": 0.05},
    {"item_name": "Sticky notes",                     "category": "product",      "unit_price": 0.03},
    {"item_name": "Notepads",                         "category": "product",      "unit_price": 2.00},
    {"item_name": "Invitation cards",                 "category": "product",      "unit_price": 0.50},
    {"item_name": "Flyers",                           "category": "product",      "unit_price": 0.15},
    {"item_name": "Party streamers",                  "category": "product",      "unit_price": 0.05},
    {"item_name": "Decorative adhesive tape (washi tape)", "category": "product", "unit_price": 0.20},
    {"item_name": "Paper party bags",                 "category": "product",      "unit_price": 0.25},
    {"item_name": "Name tags with lanyards",          "category": "product",      "unit_price": 0.75},
    {"item_name": "Presentation folders",             "category": "product",      "unit_price": 0.50},

    # Large-format items (priced per unit)
    {"item_name": "Large poster paper (24x36 inches)", "category": "large_format", "unit_price": 1.00},
    {"item_name": "Rolls of banner paper (36-inch width)", "category": "large_format", "unit_price": 2.50},

    # Specialty papers
    {"item_name": "100 lb cover stock",               "category": "specialty",    "unit_price": 0.50},
    {"item_name": "80 lb text paper",                 "category": "specialty",    "unit_price": 0.40},
    {"item_name": "250 gsm cardstock",                "category": "specialty",    "unit_price": 0.30},
    {"item_name": "220 gsm poster paper",             "category": "specialty",    "unit_price": 0.35},
]

def find_catalog_item(item_name: str) -> Optional[Dict]:
    """Return catalog entry for item_name (case-insensitive), or None."""
    return next(
        (item for item in paper_supplies
         if item["item_name"].strip().lower() == item_name.strip().lower()),
        None
    )


def get_canonical_name(item_name: str) -> Optional[str]:
    """Return canonical catalog name for item_name, or None if not found."""
    item = find_catalog_item(item_name)
    return item["item_name"] if item else None


