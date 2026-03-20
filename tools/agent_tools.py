# tools/agent_tools.py — All @tool decorated functions
from datetime import datetime
from typing import Any, Dict, Union

import pandas as pd
from smolagents import tool

from catalog.catalog import find_catalog_item, paper_supplies
from database.engine import db_engine
from database.queries import (
    DatabaseError,
    create_transaction,
    get_all_inventory,
    get_cash_balance,
    get_stock_level,
    search_quote_history,
    get_supplier_delivery_date,
)
from utils.logging import get_logger

logger = get_logger(__name__)


@tool
def get_catalog_items() -> list:
    """
    Returns the full list of items available in the paper supplies catalog.

    Returns:
        list: List of catalog item dicts with item_name, category, and unit_price.
    """
    return list(paper_supplies)


@tool
def get_stock_position(item_name: str, request_date: str) -> Dict[str, Any]:
    """
    Gets stock position for an item on a given date.

    Args:
        item_name (str): The name of the item to look up.
        request_date (str): ISO-formatted date string (YYYY-MM-DD).

    Returns:
        Dict with item_name, request_date, in_catalog (1/0), stock_position, or error.
    """
    catalog_item = find_catalog_item(item_name)
    in_catalog = 1 if catalog_item is not None else 0
    canonical_name = catalog_item["item_name"] if catalog_item else item_name

    if not in_catalog:
        return {
            "item_name": canonical_name,
            "requested_item_name": item_name,
            "request_date": request_date,
            "in_catalog": 0,
            "stock_position": 0,
        }

    try:
        df = get_stock_level(canonical_name, request_date)
        stock_position = int(df.iloc[0]["current_stock"]) if not df.empty else 0
        return {
            "item_name": canonical_name,
            "requested_item_name": item_name,
            "request_date": request_date,
            "in_catalog": 1,
            "stock_position": stock_position,
        }
    except DatabaseError as e:
        logger.error("get_stock_position error for %s: %s", item_name, e)
        return {
            "error": str(e),
            "item_name": canonical_name,
            "requested_item_name": item_name,
            "request_date": request_date,
            "in_catalog": 1,
            "stock_position": 0,
        }

@tool
def check_item_inventory(item_name: str, request_date: str) -> Dict[str, Any]:
    """
    Checks inventory position for an item on a given date.

    Args:
        item_name (str): The name of the item to look up.
        request_date (str): ISO-formatted date string (YYYY-MM-DD).

    Returns:
        Dict with item_name, in_catalog (1/0), inventory_position, or error.
    """
    catalog_item = find_catalog_item(item_name)
    in_catalog = 1 if catalog_item is not None else 0

    if not in_catalog:
        return {
            "item_name": item_name,
            "requested_item_name": item_name,
            "in_catalog": 0,
            "inventory_position": 0,
        }

    canonical_name = catalog_item["item_name"]

    try:
        all_inventory = get_all_inventory(request_date)
        inventory_position = all_inventory.get(canonical_name, 0)
        if canonical_name not in all_inventory:
            normalized_map = {k.strip().lower(): v for k, v in all_inventory.items()}
            inventory_position = normalized_map.get(canonical_name.strip().lower(), 0)

        return {
            "item_name": canonical_name,
            "requested_item_name": item_name,
            "in_catalog": 1,
            "inventory_position": inventory_position,
        }
    except DatabaseError as e:
        logger.error("check_item_inventory error for %s: %s", item_name, e)
        return {
            "error": str(e),
            "item_name": canonical_name,
            "requested_item_name": item_name,
            "in_catalog": 1,
            "inventory_position": 0,
        }


@tool
def get_item_quote(item_name: str) -> Any:
    """
    Retrieve historical quotes matching the given item name.

    Args:
        item_name (str): The name of the item to look up.

    Returns:
        List of matching quote dicts, or an error string if not in catalog.
    """
    catalog_item = find_catalog_item(item_name)
    if catalog_item is None:
        return f"{item_name} is not in catalog"

    canonical_name = catalog_item["item_name"]
    quote_history = search_quote_history([canonical_name, item_name])
    if not quote_history:
        return f"There is no quote history for item {item_name}"
    return quote_history


@tool
def create_sales_transaction(
    item_name: str, quantity: int, price: float, date: Union[str, datetime]
) -> Dict[str, Any]:
    """
    Records a sales transaction for an item.

    Args:
        item_name (str): The name of the item.
        quantity (int): Number of units sold.
        price (float): Total price of the transaction.
        date (str or datetime): Transaction date in ISO 8601 format.

    Returns:
        Dict with status, transaction_id, and transaction details, or error.
    """
    catalog_item = find_catalog_item(item_name)
    if catalog_item is None:
        return {"error": f"{item_name} is not in catalog", "in_catalog": 0}

    canonical_name = catalog_item["item_name"]
    try:
        transaction_id = create_transaction(canonical_name, "sales", quantity, price, date)
        return {
            "status": "Transaction created successfully",
            "transaction_id": transaction_id,
            "item_name": canonical_name,
            "transaction_type": "sales",
            "quantity": quantity,
            "price": price,
        }
    except DatabaseError as e:
        logger.error("create_sales_transaction error for %s: %s", item_name, e)
        return {"error": str(e), "item_name": canonical_name}


@tool
def create_stock_order_transaction(
    item_name: str, quantity: int, date: Union[str, datetime]
) -> Dict[str, Any]:
    """
    Records a stock order transaction for an item (price computed from catalog).

    Args:
        item_name (str): The name of the item.
        quantity (int): Number of units ordered.
        date (str or datetime): Transaction date in ISO 8601 format.

    Returns:
        Dict with status, transaction_id, and transaction details, or error.
    """
    catalog_item = find_catalog_item(item_name)
    if catalog_item is None:
        return {"error": f"{item_name} is not in catalog", "in_catalog": 0}

    canonical_name = catalog_item["item_name"]
    price = quantity * catalog_item["unit_price"]

    try:
        transaction_id = create_transaction(canonical_name, "stock_orders", quantity, price, date)
        return {
            "status": "Transaction created successfully",
            "transaction_id": transaction_id,
            "item_name": canonical_name,
            "transaction_type": "stock_orders",
            "quantity": quantity,
            "price": price,
        }
    except DatabaseError as e:
        logger.error("create_stock_order_transaction error for %s: %s", item_name, e)
        return {"error": str(e), "item_name": canonical_name}


@tool
def get_item_supplier_delivery_date(item_name: str, request_date: str, quantity: int) -> Any:
    """
    Estimate the supplier delivery date for an item based on quantity and start date.

    Args:
        item_name (str): The name of the item.
        request_date (str): Starting date in ISO format (YYYY-MM-DD).
        quantity (int): Number of units in the order.

    Returns:
        str: Estimated delivery date in ISO format, or error string.
    """
    catalog_item = find_catalog_item(item_name)
    if catalog_item is None:
        return f"{item_name} is not in catalog"

    return get_supplier_delivery_date(request_date, quantity)


@tool
def generate_financial_report(as_of_date: Union[str, datetime]) -> Dict:
    """
    Generate a complete financial report as of a specific date.

    Args:
        as_of_date (str or datetime): The report date.

    Returns:
        Dict with cash_balance, inventory_value, total_assets, inventory_summary,
        top_selling_products.
    """
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.isoformat()

    cash = get_cash_balance(as_of_date)

    inventory_df = pd.read_sql("SELECT * FROM inventory", db_engine)
    inventory_value = 0.0
    inventory_summary = []

    for _, item in inventory_df.iterrows():
        try:
            stock_info = get_stock_level(item["item_name"], as_of_date)
            stock = stock_info["current_stock"].iloc[0]
        except DatabaseError:
            stock = 0
        item_value = stock * item["unit_price"]
        inventory_value += item_value
        inventory_summary.append({
            "item_name": item["item_name"],
            "stock": stock,
            "unit_price": item["unit_price"],
            "value": item_value,
        })

    top_sales_query = """
        SELECT item_name, SUM(units) as total_units, SUM(price) as total_revenue
        FROM transactions
        WHERE transaction_type = 'sales' AND transaction_date <= :date
        GROUP BY item_name
        ORDER BY total_revenue DESC
        LIMIT 5
    """
    top_sales = pd.read_sql(top_sales_query, db_engine, params={"date": as_of_date})

    return {
        "as_of_date": as_of_date,
        "cash_balance": cash,
        "inventory_value": inventory_value,
        "total_assets": cash + inventory_value,
        "inventory_summary": inventory_summary,
        "top_selling_products": top_sales.to_dict(orient="records"),
    }
