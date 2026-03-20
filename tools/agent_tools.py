# tools/agent_tools.py — All @tool decorated functions
from datetime import datetime
from typing import Any, Dict, Union

import pandas as pd
from smolagents import tool

from catalog.catalog import find_catalog_item

from database.engine import db_engine
from database.helper_fns import (
    DatabaseError,
    create_transaction,
    get_all_inventory,
    get_cash_balance,
    get_stock_level,
    search_quote_history,
    get_supplier_delivery_date,
    generate_financial_report,
)
from utils.logging import get_logger

logger = get_logger(__name__)


"""Set up tools for your agents to use, these should be methods that combine the database functions above
 and apply criteria to them to ensure that the flow of the system is correct."""

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

    # First check if item is in catalog
    catalog_item = find_catalog_item(item_name)
    in_catalog = 1 if catalog_item is not None else 0
    canonical_name = catalog_item["item_name"] if catalog_item else item_name

    # If not in catalog, return with in_catalog=0 and stock_position=0
    if not in_catalog:
        return {
            "item_name": canonical_name,
            "requested_item_name": item_name,
            "request_date": request_date,
            "in_catalog": 0,
            "stock_position": 0,
        }
    
    # If in catalog, return stock position from database
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
    # First check if item is in catalog
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

    # If in catalog, return inventory position from database
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
    # First check if item is in catalog
    catalog_item = find_catalog_item(item_name)
    if catalog_item is None:
        return f"{item_name} is not in catalog"

    canonical_name = catalog_item["item_name"]
    # Return quote history matching the item name
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

    # First check if item is in catalog
    catalog_item = find_catalog_item(item_name)
    if catalog_item is None:
        return {"error": f"{item_name} is not in catalog", "in_catalog": 0}

    canonical_name = catalog_item["item_name"]
    try:
        # Create a sales transaction record in the database
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

    # First check if item is in catalog
    catalog_item = find_catalog_item(item_name)
    if catalog_item is None:
        return {"error": f"{item_name} is not in catalog", "in_catalog": 0}

    canonical_name = catalog_item["item_name"]
    price = quantity * catalog_item["unit_price"]

    try:
        # Create a stock order transaction record in the database
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
    # First check if item is in catalog
    catalog_item = find_catalog_item(item_name)
    if catalog_item is None:
        return f"{item_name} is not in catalog"
    
    # If in catalog, return delivery date based on quantity and lead times
    return get_supplier_delivery_date(request_date, quantity)


@tool
def prepare_financial_report(as_of_date: Union[str, datetime]) -> Dict:
    """
    Generate a complete financial report as of a specific date.

    Args:
        as_of_date (str or datetime): The report date.

    Returns:
        Dict with cash_balance, inventory_value, total_assets, inventory_summary,
        top_selling_products.
    """

    return generate_financial_report(as_of_date)
