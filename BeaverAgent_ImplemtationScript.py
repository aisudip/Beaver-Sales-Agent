import pandas as pd
import numpy as np
import os
import time
import dotenv
import ast
from sqlalchemy.sql import text
from datetime import datetime, timedelta
from typing import Dict, List, Union, Any, Optional, Type, TypeVar
from sqlalchemy import create_engine, Engine

import json
import re
#from dataclasses import dataclass, field, asdict
from pprint import pprint 
from pydantic import BaseModel, Field, ConfigDict


from smolagents import (
    ToolCallingAgent,
    OpenAIServerModel,
    tool,
)

DEBUG_LOG = True

# Data privacy levels - define who can access what data
class PrivacyLevel:
    PUBLIC = 'public'  # Anyone can access
    CUSTOMER = 'customer'  # Only customer and admins can access
    AGENT = 'agent'  # Only agents and admins can access  
    FINANCIAL = 'financial'  # Only financial dept and admins can access
    ADMIN = 'admin'  # Only admins can access

# Define access control
class AccessControl:
    @staticmethod
    def can_access(requester_level: str, data_level: str) -> bool:
        """Check if the requester has access to the data based on privacy levels."""
        # Admin can access everything
        if requester_level == PrivacyLevel.ADMIN:
            return True
            
        # Same level access is allowed
        if requester_level == data_level:
            return True
            
        # Financial can access agent data
        if requester_level == PrivacyLevel.FINANCIAL and data_level == PrivacyLevel.AGENT:
            return True
            
        # Agent can access customer data
        if requester_level == PrivacyLevel.AGENT and data_level == PrivacyLevel.CUSTOMER:
            return True
            
        # Anyone can access public data
        if data_level == PrivacyLevel.PUBLIC:
            return True
            
        # By default, access is denied
        return False

# Create an SQLite database
db_engine = create_engine("sqlite:///munder_difflin.db")

# List containing the different kinds of papers 
paper_supplies = [
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
    {"item_name": "Paper plates",                     "category": "product",      "unit_price": 0.10},  # per plate
    {"item_name": "Paper cups",                       "category": "product",      "unit_price": 0.08},  # per cup
    {"item_name": "Paper napkins",                    "category": "product",      "unit_price": 0.02},  # per napkin
    {"item_name": "Disposable cups",                  "category": "product",      "unit_price": 0.10},  # per cup
    {"item_name": "Table covers",                     "category": "product",      "unit_price": 1.50},  # per cover
    {"item_name": "Envelopes",                        "category": "product",      "unit_price": 0.05},  # per envelope
    {"item_name": "Sticky notes",                     "category": "product",      "unit_price": 0.03},  # per sheet
    {"item_name": "Notepads",                         "category": "product",      "unit_price": 2.00},  # per pad
    {"item_name": "Invitation cards",                 "category": "product",      "unit_price": 0.50},  # per card
    {"item_name": "Flyers",                           "category": "product",      "unit_price": 0.15},  # per flyer
    {"item_name": "Party streamers",                  "category": "product",      "unit_price": 0.05},  # per roll
    {"item_name": "Decorative adhesive tape (washi tape)", "category": "product", "unit_price": 0.20},  # per roll
    {"item_name": "Paper party bags",                 "category": "product",      "unit_price": 0.25},  # per bag
    {"item_name": "Name tags with lanyards",          "category": "product",      "unit_price": 0.75},  # per tag
    {"item_name": "Presentation folders",             "category": "product",      "unit_price": 0.50},  # per folder

    # Large-format items (priced per unit)
    {"item_name": "Large poster paper (24x36 inches)", "category": "large_format", "unit_price": 1.00},
    {"item_name": "Rolls of banner paper (36-inch width)", "category": "large_format", "unit_price": 2.50},

    # Specialty papers
    {"item_name": "100 lb cover stock",               "category": "specialty",    "unit_price": 0.50},
    {"item_name": "80 lb text paper",                 "category": "specialty",    "unit_price": 0.40},
    {"item_name": "250 gsm cardstock",                "category": "specialty",    "unit_price": 0.30},
    {"item_name": "220 gsm poster paper",             "category": "specialty",    "unit_price": 0.35},
]

# Given below are some utility functions you can use to implement your multi-agent system

def generate_sample_inventory(paper_supplies: list, coverage: float = 0.4, seed: int = 137) -> pd.DataFrame:
    """
    Generate inventory for exactly a specified percentage of items from the full paper supply list.

    This function randomly selects exactly `coverage` × N items from the `paper_supplies` list,
    and assigns each selected item:
    - a random stock quantity between 200 and 800,
    - a minimum stock level between 50 and 150.

    The random seed ensures reproducibility of selection and stock levels.

    Args:
        paper_supplies (list): A list of dictionaries, each representing a paper item with
                               keys 'item_name', 'category', and 'unit_price'.
        coverage (float, optional): Fraction of items to include in the inventory (default is 0.4, or 40%).
        seed (int, optional): Random seed for reproducibility (default is 137).

    Returns:
        pd.DataFrame: A DataFrame with the selected items and assigned inventory values, including:
                      - item_name
                      - category
                      - unit_price
                      - current_stock
                      - min_stock_level
    """
    # Ensure reproducible random output
    np.random.seed(seed)

    # Calculate number of items to include based on coverage
    num_items = int(len(paper_supplies) * coverage)

    # Randomly select item indices without replacement
    selected_indices = np.random.choice(
        range(len(paper_supplies)),
        size=num_items,
        replace=False
    )

    # Extract selected items from paper_supplies list
    selected_items = [paper_supplies[i] for i in selected_indices]

    # Construct inventory records
    inventory = []
    for item in selected_items:
        inventory.append({
            "item_name": item["item_name"],
            "category": item["category"],
            "unit_price": item["unit_price"],
            "current_stock": np.random.randint(200, 800),  # Realistic stock range
            "min_stock_level": np.random.randint(50, 150)  # Reasonable threshold for reordering
        })

    # Return inventory as a pandas DataFrame
    return pd.DataFrame(inventory)

def init_database(db_engine: Engine, seed: int = 137) -> Engine:    
    """
    Set up the Munder Difflin database with all required tables and initial records.

    This function performs the following tasks:
    - Creates the 'transactions' table for logging stock orders and sales
    - Loads customer inquiries from 'quote_requests.csv' into a 'quote_requests' table
    - Loads previous quotes from 'quotes.csv' into a 'quotes' table, extracting useful metadata
    - Generates a random subset of paper inventory using `generate_sample_inventory`
    - Inserts initial financial records including available cash and starting stock levels

    Args:
        db_engine (Engine): A SQLAlchemy engine connected to the SQLite database.
        seed (int, optional): A random seed used to control reproducibility of inventory stock levels.
                              Default is 137.

    Returns:
        Engine: The same SQLAlchemy engine, after initializing all necessary tables and records.

    Raises:
        Exception: If an error occurs during setup, the exception is printed and raised.
    """
    try:
        # ----------------------------
        # 1. Create an empty 'transactions' table schema
        # ----------------------------
        transactions_schema = pd.DataFrame({
            "id": [],
            "item_name": [],
            "transaction_type": [],  # 'stock_orders' or 'sales'
            "units": [],             # Quantity involved
            "price": [],             # Total price for the transaction
            "transaction_date": [],  # ISO-formatted date
        })
        transactions_schema.to_sql("transactions", db_engine, if_exists="replace", index=False)

        # Set a consistent starting date
        initial_date = datetime(2025, 1, 1).isoformat()

        # ----------------------------
        # 2. Load and initialize 'quote_requests' table
        # ----------------------------
        quote_requests_df = pd.read_csv("quote_requests.csv")
        quote_requests_df["id"] = range(1, len(quote_requests_df) + 1)
        quote_requests_df.to_sql("quote_requests", db_engine, if_exists="replace", index=False)

        # ----------------------------
        # 3. Load and transform 'quotes' table
        # ----------------------------
        quotes_df = pd.read_csv("quotes.csv")
        quotes_df["request_id"] = range(1, len(quotes_df) + 1)
        quotes_df["order_date"] = initial_date

        # Unpack metadata fields (job_type, order_size, event_type) if present
        if "request_metadata" in quotes_df.columns:
            quotes_df["request_metadata"] = quotes_df["request_metadata"].apply(
                lambda x: ast.literal_eval(x) if isinstance(x, str) else x
            )
            quotes_df["job_type"] = quotes_df["request_metadata"].apply(lambda x: x.get("job_type", ""))
            quotes_df["order_size"] = quotes_df["request_metadata"].apply(lambda x: x.get("order_size", ""))
            quotes_df["event_type"] = quotes_df["request_metadata"].apply(lambda x: x.get("event_type", ""))

        # Retain only relevant columns
        quotes_df = quotes_df[[
            "request_id",
            "total_amount",
            "quote_explanation",
            "order_date",
            "job_type",
            "order_size",
            "event_type"
        ]]
        quotes_df.to_sql("quotes", db_engine, if_exists="replace", index=False)

        # ----------------------------
        # 4. Generate inventory and seed stock
        # ----------------------------
        inventory_df = generate_sample_inventory(paper_supplies, seed=seed)

        # Seed initial transactions
        initial_transactions = []

        # Add a starting cash balance via a dummy sales transaction
        initial_transactions.append({
            "item_name": None,
            "transaction_type": "sales",
            "units": None,
            "price": 50000.0,
            "transaction_date": initial_date,
        })

        # Add one stock order transaction per inventory item
        for _, item in inventory_df.iterrows():
            initial_transactions.append({
                "item_name": item["item_name"],
                "transaction_type": "stock_orders",
                "units": item["current_stock"],
                "price": item["current_stock"] * item["unit_price"],
                "transaction_date": initial_date,
            })

        # Commit transactions to database
        pd.DataFrame(initial_transactions).to_sql("transactions", db_engine, if_exists="append", index=False)

        # Save the inventory reference table
        inventory_df.to_sql("inventory", db_engine, if_exists="replace", index=False)

        return db_engine

    except Exception as e:
        print(f"Error initializing database: {e}")
        raise

def create_transaction(
    item_name: str,
    transaction_type: str,
    quantity: int,
    price: float,
    date: Union[str, datetime],
) -> int:
    """
    This function records a transaction of type 'stock_orders' or 'sales' with a specified
    item name, quantity, total price, and transaction date into the 'transactions' table of the database.

    Args:
        item_name (str): The name of the item involved in the transaction.
        transaction_type (str): Either 'stock_orders' or 'sales'.
        quantity (int): Number of units involved in the transaction.
        price (float): Total price of the transaction.
        date (str or datetime): Date of the transaction in ISO 8601 format.

    Returns:
        int: The ID of the newly inserted transaction.

    Raises:
        ValueError: If `transaction_type` is not 'stock_orders' or 'sales'.
        Exception: For other database or execution errors.
    """
    try:
        # Convert datetime to ISO string if necessary
        date_str = date.isoformat() if isinstance(date, datetime) else date

        # Validate transaction type
        if transaction_type not in {"stock_orders", "sales"}:
            raise ValueError("Transaction type must be 'stock_orders' or 'sales'")

        # Prepare transaction record as a single-row DataFrame
        transaction = pd.DataFrame([{
            "item_name": item_name,
            "transaction_type": transaction_type,
            "units": quantity,
            "price": price,
            "transaction_date": date_str,
        }])

        # Insert the record into the database
        transaction.to_sql("transactions", db_engine, if_exists="append", index=False)

        # Fetch and return the ID of the inserted row
        result = pd.read_sql("SELECT last_insert_rowid() as id", db_engine)
        return int(result.iloc[0]["id"])

    except Exception as e:
        print(f"Error creating transaction: {e}")
        raise

def get_all_inventory(as_of_date: str) -> Dict[str, int]:
    """
    Retrieve a snapshot of available inventory as of a specific date.

    This function calculates the net quantity of each item by summing 
    all stock orders and subtracting all sales up to and including the given date.

    Only items with positive stock are included in the result.

    Args:
        as_of_date (str): ISO-formatted date string (YYYY-MM-DD) representing the inventory cutoff.

    Returns:
        Dict[str, int]: A dictionary mapping item names to their current stock levels.
    """
    # SQL query to compute stock levels per item as of the given date
    query = """
        SELECT
            item_name,
            SUM(CASE
                WHEN transaction_type = 'stock_orders' THEN units
                WHEN transaction_type = 'sales' THEN -units
                ELSE 0
            END) as stock
        FROM transactions
        WHERE item_name IS NOT NULL
        AND transaction_date <= :as_of_date
        GROUP BY item_name
        HAVING stock > 0
    """

    # Execute the query with the date parameter
    result = pd.read_sql(query, db_engine, params={"as_of_date": as_of_date})

    # Convert the result into a dictionary {item_name: stock}
    return dict(zip(result["item_name"], result["stock"]))

def get_stock_level(item_name: str, as_of_date: Union[str, datetime]) -> pd.DataFrame:
    """
    Retrieve the stock level of a specific item as of a given date.

    This function calculates the net stock by summing all 'stock_orders' and 
    subtracting all 'sales' transactions for the specified item up to the given date.

    Args:
        item_name (str): The name of the item to look up.
        as_of_date (str or datetime): The cutoff date (inclusive) for calculating stock.

    Returns:
        pd.DataFrame: A single-row DataFrame with columns 'item_name' and 'current_stock'.
    """
    # Convert date to ISO string format if it's a datetime object
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.isoformat()

    # SQL query to compute net stock level for the item
    stock_query = """
        SELECT
            item_name,
            COALESCE(SUM(CASE
                WHEN transaction_type = 'stock_orders' THEN units
                WHEN transaction_type = 'sales' THEN -units
                ELSE 0
            END), 0) AS current_stock
        FROM transactions
        WHERE item_name = :item_name
        AND transaction_date <= :as_of_date
    """

    # Execute query and return result as a DataFrame
    return pd.read_sql(
        stock_query,
        db_engine,
        params={"item_name": item_name, "as_of_date": as_of_date},
    )

def get_supplier_delivery_date(input_date_str: str, quantity: int) -> str:
    """
    Estimate the supplier delivery date based on the requested order quantity and a starting date.

    Delivery lead time increases with order size:
        - ≤10 units: same day
        - 11–100 units: 1 day
        - 101–1000 units: 4 days
        - >1000 units: 7 days

    Args:
        input_date_str (str): The starting date in ISO format (YYYY-MM-DD).
        quantity (int): The number of units in the order.

    Returns:
        str: Estimated delivery date in ISO format (YYYY-MM-DD).
    """
    # Debug log (comment out in production if needed)
    print(f"FUNC (get_supplier_delivery_date): Calculating for qty {quantity} from date string '{input_date_str}'")

    # Attempt to parse the input date
    try:
        input_date_dt = datetime.fromisoformat(input_date_str.split("T")[0])
    except (ValueError, TypeError):
        # Fallback to current date on format error
        print(f"WARN (get_supplier_delivery_date): Invalid date format '{input_date_str}', using today as base.")
        input_date_dt = datetime.now()

    # Determine delivery delay based on quantity
    if quantity <= 10:
        days = 0
    elif quantity <= 100:
        days = 1
    elif quantity <= 1000:
        days = 4
    else:
        days = 7

    # Add delivery days to the starting date
    delivery_date_dt = input_date_dt + timedelta(days=days)

    # Return formatted delivery date
    return delivery_date_dt.strftime("%Y-%m-%d")

def get_cash_balance(as_of_date: Union[str, datetime]) -> float:
    """
    Calculate the current cash balance as of a specified date.

    The balance is computed by subtracting total stock purchase costs ('stock_orders')
    from total revenue ('sales') recorded in the transactions table up to the given date.

    Args:
        as_of_date (str or datetime): The cutoff date (inclusive) in ISO format or as a datetime object.

    Returns:
        float: Net cash balance as of the given date. Returns 0.0 if no transactions exist or an error occurs.
    """
    try:
        # Convert date to ISO format if it's a datetime object
        if isinstance(as_of_date, datetime):
            as_of_date = as_of_date.isoformat()

        # Query all transactions on or before the specified date
        transactions = pd.read_sql(
            "SELECT * FROM transactions WHERE transaction_date <= :as_of_date",
            db_engine,
            params={"as_of_date": as_of_date},
        )

        # Compute the difference between sales and stock purchases
        if not transactions.empty:
            total_sales = transactions.loc[transactions["transaction_type"] == "sales", "price"].sum()
            total_purchases = transactions.loc[transactions["transaction_type"] == "stock_orders", "price"].sum()
            return float(total_sales - total_purchases)

        return 0.0

    except Exception as e:
        print(f"Error getting cash balance: {e}")
        return 0.0

@tool
def generate_financial_report(as_of_date: Union[str, datetime]) -> Dict:
    """
    Generate a complete financial report for the company as of a specific date.

    This includes:
    - Cash balance
    - Inventory valuation
    - Combined asset total
    - Itemized inventory breakdown
    - Top 5 best-selling products

    Args:
        as_of_date (str or datetime): The date (inclusive) for which to generate the report.

    Returns:
        Dict: A dictionary containing the financial report fields:
            - 'as_of_date': The date of the report
            - 'cash_balance': Total cash available
            - 'inventory_value': Total value of inventory
            - 'total_assets': Combined cash and inventory value
            - 'inventory_summary': List of items with stock and valuation details
            - 'top_selling_products': List of top 5 products by revenue
    """
    # Normalize date input
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.isoformat()

    # Get current cash balance
    cash = get_cash_balance(as_of_date)

    # Get current inventory snapshot
    inventory_df = pd.read_sql("SELECT * FROM inventory", db_engine)
    inventory_value = 0.0
    inventory_summary = []

    # Compute total inventory value and summary by item
    for _, item in inventory_df.iterrows():
        stock_info = get_stock_level(item["item_name"], as_of_date)
        stock = stock_info["current_stock"].iloc[0]
        item_value = stock * item["unit_price"]
        inventory_value += item_value

        inventory_summary.append({
            "item_name": item["item_name"],
            "stock": stock,
            "unit_price": item["unit_price"],
            "value": item_value,
        })

    # Identify top-selling products by revenue
    top_sales_query = """
        SELECT item_name, SUM(units) as total_units, SUM(price) as total_revenue
        FROM transactions
        WHERE transaction_type = 'sales' AND transaction_date <= :date
        GROUP BY item_name
        ORDER BY total_revenue DESC
        LIMIT 5
    """
    top_sales = pd.read_sql(top_sales_query, db_engine, params={"date": as_of_date})
    top_selling_products = top_sales.to_dict(orient="records")

    return {
        "as_of_date": as_of_date,
        "cash_balance": cash,
        "inventory_value": inventory_value,
        "total_assets": cash + inventory_value,
        "inventory_summary": inventory_summary,
        "top_selling_products": top_selling_products,
    }


def search_quote_history(search_terms: List[str], limit: int = 5) -> List[Dict]:
    """
    Retrieve a list of historical quotes that match any of the provided search terms.

    The function searches both the original customer request (from `quote_requests`) and
    the explanation for the quote (from `quotes`) for each keyword. Results are sorted by
    most recent order date and limited by the `limit` parameter.

    Args:
        search_terms (List[str]): List of terms to match against customer requests and explanations.
        limit (int, optional): Maximum number of quote records to return. Default is 5.

    Returns:
        List[Dict]: A list of matching quotes, each represented as a dictionary with fields:
            - original_request
            - total_amount
            - quote_explanation
            - job_type
            - order_size
            - event_type
            - order_date
    """
    conditions = []
    params = {}

    # Build SQL WHERE clause using LIKE filters for each search term
    for i, term in enumerate(search_terms):
        param_name = f"term_{i}"
        conditions.append(
            f"(LOWER(qr.response) LIKE :{param_name} OR "
            f"LOWER(q.quote_explanation) LIKE :{param_name})"
        )
        params[param_name] = f"%{term.lower()}%"

    # Combine conditions; fallback to always-true if no terms provided
    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Final SQL query to join quotes with quote_requests
    query = f"""
        SELECT
            qr.response AS original_request,
            q.total_amount,
            q.quote_explanation,
            q.job_type,
            q.order_size,
            q.event_type,
            q.order_date
        FROM quotes q
        JOIN quote_requests qr ON q.request_id = qr.id
        WHERE {where_clause}
        ORDER BY q.order_date DESC
        LIMIT {limit}
    """

    # Execute parameterized query
    with db_engine.connect() as conn:
        result = conn.execute(text(query), params)
        return [dict(row._mapping) for row in result]

########################
########################
########################
# YOUR MULTI AGENT STARTS HERE
########################
########################
########################


# Set up and load your env parameters and instantiate your model.
# Load your OpenAI API key
dotenv.load_dotenv()
openai_api_key = os.getenv("UDACITY_OPENAI_API_KEY")

model = OpenAIServerModel(
    model_id="gpt-4o-mini",
    temperature=0.0,
    top_p=1.0,
    seed=42,
    api_base="https://openai.vocareum.com/v1",
    api_key=openai_api_key,
)



class OrderItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    item_name: str
    description: str = ""
    order_quantity: int = 0
    order_unit: str = ""
    in_catalog: int = 0
    stock_position: int = 0
    unit_price: float = 0.0
    discount: float | int | str | None = None
    discount_val: float = 0.0
    price_matching_confidence: str = ""
    quote_price: float = 0.0
    item_status: str = "Order Not Fulfilled"
    estimated_delivery: str = ""
    output_message: str = ""
    sales_transaction_id: float | int | str | None = None

class Order(BaseModel):
    model_config = ConfigDict(extra="ignore")

    order_id: str
    order_items: List[OrderItem] = Field(default_factory=list)
    request_date: Optional[str] = None
    delivery_required_date: Optional[str] = None
    order_context: str = ""

class OrderState(BaseModel):
    model_config = ConfigDict(extra="ignore")

    order_counter: int = 0
    orders: List[Order] = Field(default_factory=list)

order_state = OrderState()

"""Set up tools for your agents to use, these should be methods that combine the database functions above
 and apply criteria to them to ensure that the flow of the system is correct."""


# Tools for inventory agent
@tool
def get_catalog_items() -> Dict[str, Any]:
    """
    Gets stock position for an item

    This function checks if the item is availablee in the catalog and returns inveentory position if it is. 

    Args:
        item_name (str): The name of the item to look up.
        request_date (str): ISO-formatted date string (YYYY-MM-DD) for which the stock position is required.

    Returns:
        Dict[str, int]: A dictionary mapping item names to their current stock levels.
    """

    catalog_items = []
    for item in paper_supplies:
        catalog_items.append(item)

    return catalog_items




@tool
def get_stock_position(item_name: str, request_date: str) -> Dict[str, Any]:
    """
    Gets stock position for an item

    This function checks if the item is availablee in the catalog and returns inveentory position if it is. 

    Args:
        item_name (str): The name of the item to look up.
        request_date (str): ISO-formatted date string (YYYY-MM-DD) for which the stock position is required.

    Returns:
        Dict[str, int]: A dictionary mapping item names to their current stock levels.
    """
    catalog_item = next(
        (item for item in paper_supplies
         if item["item_name"].strip().lower() == item_name.strip().lower()),
        None
    )

    #in_catalog = catalog_item is not None
    in_catalog = 1 if catalog_item is not None else 0
    canonical_name = catalog_item["item_name"] if in_catalog else item_name

    if not in_catalog:
        stock_position = 0
    else:
        df = get_stock_level(canonical_name, request_date)  # <-- DataFrame
        stock_position = int(df.iloc[0]["current_stock"]) if not df.empty else 0


    return {
        "item_name": canonical_name,
        "requested_item_name": item_name,
        "request_date": request_date,
        "in_catalog": in_catalog,
        "stock_position": stock_position
    }


@tool
def check_item_inventory(item_name: str, request_date: str) -> Dict[str, int]:
    """
    Checks inventory position for an item

    This function checks if the item is availablee in the catalog and returns inveentory position if it is. 

    Args:
        item_name (str): The name of the item to look up.
        request_date (str): ISO-formatted date string (YYYY-MM-DD) representing the inventory cutoff.

    Returns:
        Dict[str, int]: A dictionary mapping item names to their current stock levels.
    """
    
    # 1) Find the canonical/catalog name (exact spelling) for this item
    catalog_item = next(
        (item for item in paper_supplies if item["item_name"].strip().lower() == item_name.strip().lower()),
        None
    )

    #in_catalog = catalog_item is not None
    in_catalog = 1 if catalog_item is not None else 0

    if not in_catalog:
        inventory_position = 0
        canonical_name = item_name
    else:
        canonical_name = catalog_item["item_name"]  # exact key format as stored in catalog
        all_inventory = get_all_inventory(request_date)

        # 2) Inventory lookup should be defensive
        inventory_position = all_inventory.get(canonical_name, 0)

        # Optional: if inventory keys aren’t canonical either, do a normalized fallback
        if canonical_name not in all_inventory:
            normalized_map = {k.strip().lower(): v for k, v in all_inventory.items()}
            inventory_position = normalized_map.get(canonical_name.strip().lower(), 0)

    return {
        "item_name": canonical_name,
        "requested_item_name": item_name,
        "in_catalog": in_catalog,
        "inventory_position": inventory_position
    }


@tool
def get_item_quote(item_name: str) -> Dict[str, int]:
    """
    Retrieve a list of historical quotes that match any of the provided item name.

    The function searches both the original customer request (from `quote_requests`) and
    the explanation for the quote (from `quotes`) for each keyword. Results are sorted by
    most recent order date and limited by the `limit` parameter.

    Args:
        item_name (str): The name of the item to look up.

    Returns:
        List[Dict]: A list of matching quotes, each represented as a dictionary with fields:
            - original_request
            - total_amount
            - quote_explanation
            - job_type
            - order_size
            - event_type
            - order_date
    """

    # 1) Find the canonical/catalog name (exact spelling) for this item
    catalog_item = next(
        (item for item in paper_supplies if item["item_name"].strip().lower() == item_name.strip().lower()),
        None
    )

    if catalog_item is None:
        return f"{item_name} is not in catalog"
    else:
        canonical_name = catalog_item["item_name"]  # exact key format as stored in catalog
        quote_history = search_quote_history([canonical_name, item_name])
        if quote_history is None:
            return f" There is no quote history for item {item_name}"
        else:
            return quote_history

    
@tool
def create_sales_transaction(item_name: str, quantity: int, price: float, date: Union[str, datetime]) -> Dict[str, int]:
    """
    This function records a transaction of type 'stock_orders' or 'sales' with a specified

    This function records a sales transaction for a specified item name, quantity, total price, and transaction date into the 'transactions' table of the database.

    Args:
        item_name (str): The name of the item involved in the transaction.
        quantity (int): Number of units involved in the transaction.
        price (float): Total price of the transaction.
        date (str or datetime): Date of the transaction in ISO 8601 format.

    Returns:
        int: The ID of the newly inserted transaction.

    """
    transaction_type = 'sales'

        # 1) Find the canonical/catalog name (exact spelling) for this item
    catalog_item = next(
        (item for item in paper_supplies if item["item_name"].strip().lower() == item_name.strip().lower()),
        None
    )

    if catalog_item is None:
        return f"{item_name} is not in catalog"
    else:
        canonical_name = catalog_item["item_name"]  # exact key format as stored in catalog
        sales_response = create_transaction(canonical_name, transaction_type, quantity, price, date) 

    return sales_response

@tool
def create_stock_order_transaction(item_name: str, quantity: int, date: Union[str, datetime]) -> Dict[str, int]:
    """
    This function records a stock order transaction for a specified item name, quantity and transaction date into the 'transactions' table of the database.
    The total price is calculated based on unit price available in paper supplies catalog

    Args:
        item_name (str): The name of the item involved in the transaction.
        quantity (int): Number of units involved in the transaction.
        date (str or datetime): Date of the transaction in ISO 8601 format.

    Returns:
        int: The ID of the newly inserted transaction.

    """
    transaction_type = 'stock_orders'

    # 1) Find the canonical/catalog name (exact spelling) for this item
    catalog_item = next(
        (item for item in paper_supplies if item["item_name"].strip().lower() == item_name.strip().lower()),
        None
    )

    if catalog_item is None:
        return f"{item_name} is not in catalog"
    else:
        canonical_name = catalog_item["item_name"]  # exact key format as stored in catalog
        unit_price = catalog_item["unit_price"]
        price = quantity * unit_price
        stock_order_response = create_transaction(canonical_name, transaction_type, quantity, price, date) 

    return stock_order_response

@tool
def get_item_supplier_delivery_date(item_name: str, request_date: str, quantity: int) -> str:
    """
    Estimate the supplier delivery date for a item based on the requested order quantity and a starting date.

    Delivery lead time increases with order size:
        - ≤10 units: same day
        - 11–100 units: 1 day
        - 101–1000 units: 4 days
        - >1000 units: 7 days

    Args:
        item_name (str): The name of the item involved in the transaction.
        request_date (str): The starting date in ISO format (YYYY-MM-DD).
        quantity (int): The number of units in the order.

    Returns:
        str: Estimated delivery date in ISO format (YYYY-MM-DD).
    """
    # 1) Find the canonical/catalog name (exact spelling) for this item
    catalog_item = next(
        (item for item in paper_supplies if item["item_name"].strip().lower() == item_name.strip().lower()),
        None
    )
    if catalog_item is None:
        return f"{item_name} is not in catalog"
    else:
        canonical_name = catalog_item["item_name"]  # exact key format as stored in catalog
        delivery_date = get_supplier_delivery_date(request_date, quantity) 

    return delivery_date

def get_all_transactions(as_of_date: str) -> Dict[str, int]:
    # SQL query to compute stock levels per item as of the given date
    query = """
        SELECT
            *
        FROM transactions
        WHERE transaction_date <= :as_of_date
    """

    # Execute the query with the date parameter
    result = pd.read_sql(query, db_engine, params={"as_of_date": as_of_date})

    # Convert the result into a dictionary {item_name: stock}
    return result






# Tools for quoting agent


# Tools for ordering agent


# Set up your agents and create an orchestration agent that will manage them.

#======= Agents =======

# Order Processing Agent

# Inveentory Manager Agent
class OrderProcessorAgent(ToolCallingAgent):
    """Agent responsible for processing customer order requests."""
    
    def __init__(self, model):
        super().__init__(
            tools=[get_catalog_items],
            model=model,
            name="order_processor",
            description="Agent responsible for processing customer orders. Parses requests, identifies order names and quantities."
        )

class InventoryManagerAgent(ToolCallingAgent):
    """Agent responsible for checking inventory and stock level."""
    
    def __init__(self, model):
        super().__init__(
            tools=[get_stock_position],
            model=model,
            name="inventory_manager",
            description="Agent responsible for checking inventory and stock level."
        )
        

class QuoteGenerationAgent(ToolCallingAgent):
    """Agent for generating quotes for incoming sales inquiries"""
    
    def __init__(self, model):
        super().__init__(
            tools=[check_item_inventory, get_item_quote],
            model=model,
            name="quote_generator",
            description="Agent for generating quotes for incoming sales inquiries.",
        )

class OrderFulfillmentAgent(ToolCallingAgent):
    """Agent for fulfillment of orders including supplier logistics and transactions"""
    
    def __init__(self, model):
        super().__init__(
            tools=[create_stock_order_transaction, create_sales_transaction, get_item_supplier_delivery_date],
            model=model,
            name="order_fulfiller",
            description="Agent for fulfillment of orders including supplier logistics and transactions."
        )

# ======= Paper Sales Orchestrator Agent =======

class PaperSalesOrchestratorAgent(ToolCallingAgent):
    """Orchestrates the workflow for paper inveentory and order fulfillment."""
        
    def __init__(self, model, order_state: OrderState):
        super().__init__(
            tools=[generate_financial_report],
            model=model,
            name="Orchestrator",
            description="Agent that orchestrates activities of other ageents and brings their results together for final output",
        )
        self.order_processor = OrderProcessorAgent(model)
        self.inventory_manager = InventoryManagerAgent(model)
        self.quote_generator = QuoteGenerationAgent(model)
        self.order_fulfiller = OrderFulfillmentAgent(model)
        self.order_state = order_state

    def parse_llm_json(self, output: str) -> dict:

        # 1) If it's already a dict, nothing to do
        if isinstance(output, dict):
            return output

        # 2) If it's something unexpected (e.g., list, None), fail loudly
        if not isinstance(output, str):
            raise TypeError(f"parse_llm_json expected str or dict, got {type(output)}: {output!r}")

        # 3) Normal string handling
        output = output.strip()

        start = output.find('{')
        end = output.rfind('}')
        if start == -1 or end == -1:
            raise ValueError(f"No JSON object found in LLM output: {output!r}")

        json_str = output[start:end+1]

        # First attempt: assume it's normal JSON
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass  # fall through to the double-escaped case

        # Heuristic: handle JSON that has been double-escaped like {\"order_id\"...}
        if '\\"' in json_str:
            try:
                # Treat json_str as the CONTENT of a JSON string literal
                # Wrap it in quotes, decode once to unescape \" → "
                inner = json.loads(f'"{json_str}"')
                # Now decode the real JSON object
                return json.loads(inner)
            except Exception as e2:
                raise ValueError(
                    f"Failed to parse double-escaped JSON from LLM output: {e2}\nRaw: {json_str!r}"
                )

        # If we get here, it's broken in some other way
        raise ValueError(f"Failed to parse JSON from LLM output: {json_str!r}")


    def _coerce_payload(self, payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            return payload

        if hasattr(payload, "content"):
            payload = payload.content

        if isinstance(payload, str):
            payload = payload.strip()

            # Try strict JSON parsing
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                # Fall back to structured error object
                return {
                    "order_id": "0000",
                    "requested_items": [],
                    "order_context": payload,
                    "order_status": "Failed",
                    "error": "LLM returned non-JSON or mixed response"
                }

        raise TypeError(f"payload must be dict or JSON string; got {type(payload)}")


    def dict_to_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert your input dict (with 'requested_items') into an Order Pydantic model
        (with 'order_items').

        Expected input shape:
        {
            "order_id": "...",
            "requested_items": [ {...}, {...} ],
            "request_date": "...",
            "delivery_required_date": "...",
            "order_context": "..."
        }
        """
        # Map requested_items -> order_items
        if DEBUG_LOG:
            print("***************** update_payload *******************")
            print(payload)
            print("***************** update_payload *******************")

        payload = self._coerce_payload(payload)

        requested_items = payload.get("requested_items", []) or []

        order_items = [OrderItem.model_validate(it) for it in requested_items]

        # Build Order (ignore any extra keys automatically due to extra="ignore")
        order_data = {
            "order_id": payload.get("order_id"),
            "order_items": order_items,
            "request_date": payload.get("request_date"),
            "delivery_required_date": payload.get("delivery_required_date"),
            "order_context": payload.get("order_context", ""),
            # You can set defaults or allow caller to override if present:
            "order_status": payload.get("order_status", "Started"),
        }

        order = Order.model_validate(order_data)

        # Append into shared state (no overwriting)
        self.order_state.orders.append(order)  # ✅ store Order model, not dict


        #return Order.model_validate(order_data)

        return order.model_dump()

    def normalize_discount(self, discount: str):
        """
        Convert discount strings to float when possible.
        Supports:
        - percentage strings: '10%' -> 0.10
        - decimal strings: '0.15' -> 0.15
        - mapped labels: 'Bulk' -> 0.10, 'VIP' -> 0.20
        Returns 0  for non-numeric labels.
        """

        BULK_MAP = {
            "bulk": 0.10,
            "vip": 0.20,
        }

        if not isinstance(discount, str):
            return discount  # or raise if you want strict typing

        value = discount.strip()
        low = value.lower()

        # Case 0: mapped symbolic labels ("Bulk", "VIP", etc.)
        if low in BULK_MAP:
            return BULK_MAP[low]

        # Case 1: percentage e.g. "10%" or "7.5%"
        if value.endswith('%'):
            try:
                num = float(value[:-1])
                return num / 100.0
            except ValueError:
                return discount  # failed to parse; fallback

        # Case 2: float-like string
        try:
            return float(value)
        except ValueError:
            # Case 3: text label -> leave as-is
            return 0

    def fulfill_order_dict(
        self,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Prepaare data to fulfill the order.

        Returns a dictionary for orders to be fulfilled.
        """

        if DEBUG_LOG:
            print("*****************fulfill_order_dict payload******************************")
            print("DEBUG fulfill_order_dict payload type:", type(payload))
            print("DEBUG fulfill_order_dict payload:", payload)
            print("*****************fulfill_order_dict payload******************************")

        fulfill_order = {
            "order_id": payload["order_id"],
            "order_items": []
        }
        request_date = payload["request_date"]
        delivery_required = payload["delivery_required_date"]
        for item in payload["order_items"]:
            if item["quote_price"] > 0:
                if item["order_quantity"] <= item["stock_position"]:
                    estimated_delivery = request_date
                else:
                    estimated_delivery = ""
                order_item = {
                    "item_name": item["item_name"],
                    "order_quantity": item["order_quantity"],
                    "stock_position": item["stock_position"],
                    "quote_price": item["quote_price"],
                    "request_date": request_date,
                    "estimated_delivery": estimated_delivery,
                    "delivery_required": delivery_required,


                }
                fulfill_order["order_items"].append(order_item)


        return fulfill_order

    def update_order_state(
        self,
        update_payload: Dict[str, Any],
        input_type: str = "default"
    ) -> Dict[str, Any]:
        """
        Update an existing OrderState with partial item-level updates.

        Returns a summary of what was actually updated.
        """
        order_state = self.order_state

        if DEBUG_LOG:
            print("DEBUG update_order_state input_type:", input_type)
            print("DEBUG raw update_payload:", update_payload)

        update_payload = self._coerce_payload(update_payload)
        if input_type == "quote_update":
            items = update_payload.get("order_items")
            if not items:
                print("WARNING: quote_update payload has no order_items:", update_payload)
                return self.order_state.model_dump()

            for item in items:
                item["discount_val"] = self.normalize_discount(item["discount"])

        target_order_id = update_payload.get("order_id")
        if not target_order_id:
            raise ValueError("update_payload must contain order_id")

        updates_by_item = {
            item["item_name"]: item
            for item in update_payload.get("order_items", [])
            if "item_name" in item
        }

        update_response = {
            "order_id": target_order_id,
            "updated_items": []
        }

        # Find the target order
        for order in order_state.orders:
            if order.order_id != target_order_id:
                continue

            # Optional: update order-level fields if present later
            # (not used in your current payload)

            for order_item in order.order_items:
                update = updates_by_item.get(order_item.item_name)
                if not update:
                    continue

                updated = False

                # Only allow specific fields to be patched
                for field in ("in_catalog", "stock_position", "quote_price", "item_status", "output_message", "sales_transaction_id", "estimated_delivery", "unit_price", "discount", "discount_val", "price_matching_confidence"):
                    if field in update:
                        old = getattr(order_item, field)
                        new = update[field]
                        # Coerce numeric types
                        if field in ("unit_price", "discount_val", "stock_position", "quote_price"):
                            if new is not None and isinstance(new, str):
                                try:
                                    new = float(new)
                                except ValueError:
                                    # if you want to be strict, raise; otherwise fallback
                                    new = 0.0

                        if old != new:
                            setattr(order_item, field, new)
                            updated = True

                if updated and input_type == "quote_update":
                    dv = float(order_item.discount_val or 0.0)
                    norm_discount_val = norm_discount_val = dv / (1 + 99 * (dv > 1)) # handling cases where discount_val is greater than 1

                    unit_price = float(order_item.unit_price or 0.0)
                    order_item.quote_price = (
                        order_item.order_quantity * unit_price * (1 - norm_discount_val)
                    )

                    update_response["updated_items"].append({
                        "item_name": order_item.item_name,
                        "in_catalog": order_item.in_catalog,
                        "stock_position": order_item.stock_position,
                        "discount": order_item.discount,
                        "discount_val": order_item.discount_val,
                        "price_matching_confidence": order_item.price_matching_confidence,
                        "quote_price": order_item.quote_price,
                        "item_status": order_item.item_status,
                        "estimated_delivery": order_item.estimated_delivery,
                    })

            break  # order_id is unique → stop after found

        order = next(
            (o for o in order_state.orders if o.order_id == target_order_id),
            None
        )

        if order:
            order_json = order.model_dump()
        else:
            order_json = {}

        return order_json

        #return update_response


    def process_order(self, customer_request: str) -> str:
        """
        Process a customer order from initial request through production queue.
        
        Args:
            customer_request: Natural language order request from customer
            
        Returns:
            Response to customer with order details and status
        """

        self.order_state.order_counter += 1
        order_id = f"ORD-{self.order_state.order_counter:04d}"
        
        # Step 1: Parse the order
        raw_order_response = self.order_processor.run(
            f"""The customer says: "{customer_request}"
            
            CRITICAL NORMALIZATION RULES
            1. item_name MUST be the exact canonical name from the catalog.
            2. Do NOT paraphrase or invent item_name.
            3. If customer wording differs (e.g., "Glossy Paper" vs "A4 glossy paper"), normalize to the closest catalog item name.
            4. If no catalog match is possible, keep the item_name provided by customer and set in_catalog to False.
            5. Derive a short and relevant context from {customer_request}
            6. Return ONLY valid JSON. No text outside JSON.
            7. Return only a single JSON object. Make sure all double quotes inside string values are escaped as \" so the JSON parses correctly.

            IMPORTANT:
                - You must return STRICT, valid JSON.
                - Do NOT use double quotes to denote inches or dimensions inside any string.
                Instead of writing `24" x 36"`, write `24in x 36in` or `24 inches x 36 inches`.
                - There must never be an unescaped `"` character inside a JSON string value.

            Respond as a json:
            - order_id : {order_id}
            - requested_items: list of objects
                - customer_text
                - item_name (canonical catalog name where available in catalog otherwise the item_name provided by customer)
                - in_catalog: 1 | 0 (1 if item_name is available in catalog else 0)
                - category
                - order_quantity
                - order_unit
                - match_type: "exact" | "normalized" | "unknown"
                - item_status: "In Catalog" (if in_catalog equals 1) | "Not in Catalog" (if in_catalog equals 0)
                - output_message: short message on the process output
            - request_date
            - delivery_required_date
            - order_context: Relevant context as derived from customer request. It must always be a string. If unknown, output "" (empty string). Never output null.
            """
        )

        if DEBUG_LOG:
            print("*************Printing RAW Order Response")
            print (raw_order_response)
            print("*************Printing RAW Order Response")

        parsed_order_response = self.parse_llm_json(raw_order_response)

        if DEBUG_LOG:
            print("*************Printing PARSED Order Response")
            print (parsed_order_response)
            print("*************Printing PARSED Order Response")
    
    
        order_details = self.dict_to_order(parsed_order_response)


        if DEBUG_LOG:
            print("*************Printing Order Details")
            print (order_details)
            print(type(order_details))
            print("*************Printing Order Details")

        # Step 3: Inventory Check

        inventory_response = self.inventory_manager.run(
            f"""
            1. First identify the items in {order_details["order_items"]} and check if the item is available in the catalog
            2. If the item is available in the catalog
                - Get the stock position for each of the item for the {order_details["request_date"]}
            Respond as a json:
            - order_id : {order_id}
            - order_items: list of objects
                - item_name should match item_name in {order_details["order_items"]}
                - stock_position for the request date
                - request_date
                - item_status: "Stock Position Updated" (if stock position is available) | "Stock Not Available" (if stock position is not available)
                - output_message: short message on the process output
             """
        )
        
        if DEBUG_LOG:
            print("*************Printing Inventory Response")
            print (inventory_response)
            print("*************Printing Inventory Response")

        
        updated_stock_resp = self.update_order_state(inventory_response)

        if DEBUG_LOG:
            print("*************Printing UPDATED STOCK Response")
            print (updated_stock_resp)
            print("*************Printing PDATED STOCK Response")
        
        # Step 4: Generate quote

        raw_price_map_response = self.quote_generator.run(
            f"""
            1. First identify items in {updated_stock_resp["order_items"]} and check if it is available in the catalog
            2. For each such item that is available in the catalog, analyze the following for the item
                - Inventory position for the item
                - Quote history for the item
                - {customer_request}
            3. Create a price map  as follows
                - For each of the item get the best match on
                    - Unit Price
                    - Unit
                    - Discount
            Return JSON::
            - order_id : {order_id} 
            - order_items: list of objects
                - item_name should match item_name in {updated_stock_resp["order_items"]}
                - unit_price
                - discount
                - price_matching_confidence: High | Medium | Low
                - item_status: "Quote Price Updated" (if quote_price has been updated) | "Quote Price Not Available" (if quote_price is 0)
                - output_message: short message on the process output
            """
        )
        
        if DEBUG_LOG:
            print("*************Printing RAW price_map_response")
            print (raw_price_map_response)
            print("*************Printing RAW price_map_response")

        parsed_price_map_response = self.parse_llm_json(raw_price_map_response)

        if DEBUG_LOG:
            print("*************Printing PARSED parsed_price_map_response")
            print (parsed_price_map_response)
            print("*************Printing PARSED parsed_price_map_response")
    
    
        updated_quote = self.update_order_state(parsed_price_map_response, "quote_update")

        if DEBUG_LOG:
            print("*************Printing UPDATED QUOTE Response")
            print (updated_quote)
            print("*************Printing UPDATED QUOTE Response")


        pending_order_response = self.fulfill_order_dict(updated_quote)

        if DEBUG_LOG:
            print("*************Printing PENDING ORDER Response")
            print (pending_order_response)
            print("*************Printing PENDING ORDER Response")

        if len(pending_order_response["order_items"]) == 0:
            final_response = updated_quote
            summary_response = "There are no items in this order that could be fulfilled "
            final_response["Order Summary"] = summary_response
            return json.dumps(final_response, indent=2)


        pending_order = self.update_order_state(pending_order_response)

        if DEBUG_LOG:
            print("*************Printing PENDING ORDER ****************")
            print (pending_order)
            print("*************Printing PENDING ORDER ****************")

        fulfillmnt_response = self.order_fulfiller.run(
            f"""
            You will fulfill orders that are pending in cordination with supplier.
            The steps that you will follow in fulfilling orders are the follwoing :
            
            Step1 :
            - Extract details of items in {pending_order["order_items"]}

            Step 2 :
            - For items where 'estimated_delivery' date is available
                - Create a 'sales' transaction with order_quantity, quote_price and request_date in {pending_order["order_items"]}
                - Create a 'stock order' transaction with order_quantity and request_date in {pending_order["order_items"]} to replenish the inventory
                - Update item_status to "Order Fulfilled" 

            Step 3 :
            - For items where 'estimated_delivery' date is NOT available
                - Get the estimated_delivery date from the supplier for order_quantity in {pending_order["order_items"]}
                    Step 3A : If estimated_delivery date is after delivery_required date
                        - Do Nothing
                        - Update item_status to "Order Fulfillment Failed" 
                    Step 3B : If estimated_delivery date N or BEFORE delivery_required date
                        - Create a 'sales' transaction with order_quantity, quote_price and request_date in {pending_order["order_items"]}
                        - Create a 'stock order' transaction with order_quantity and request_date in {pending_order["order_items"]} to replenish the inventory
                        - Update item_status to "Order Fulfilled" 

            Step 4: Respond as a json:
            - order_id : {pending_order["order_id"]}
            - order_items: list of objects
                - item_name should match item_name in {pending_order}
                - sales_transaction_id:  Transaction id from 'sales' transaction of the item
                - estimated_delivery 
                - item_status: 
                - output_message: short message on the process output

            
            """
        )
        if DEBUG_LOG:
            print("*************Printing fulfillmnt Response")
            print (fulfillmnt_response)
            print("*************Printing fulfillmnt Response")
        
        final_response = self.update_order_state(fulfillmnt_response, "Order Fulfilled")

        if DEBUG_LOG:
            print("*************Printing fulfillmnt Response")
            print (final_response)
            print("*************Printing fulfillmnt Response")

        summary_response = self.run(
            f"""
            You are an helpful assistant who can write great executive summary

            Use the following to generate an insightful and brief executive summary of the order
                - Financial Report that you generate for the request date
                - {final_response}

            The executive summary is an insightful narrative decription that is an amalgamation of financial report and order details. The length of the description is around 30 words.

            Respond as a text string.

            """
        )
        if DEBUG_LOG:
            print("*************Printing Executive Summary****************")
            print (summary_response)
            print("*************Printing Executive Summary****************")

        final_response["Order Summary"] = summary_response

        if DEBUG_LOG:
            print("*************Printing order_state.orders_by_id")
            print (order_state.orders)
            print("*************Printing order_state.orders_by_id")

        return json.dumps(final_response, indent=2)


        #final_response["Order Summary"] = summary_response



        #return json.dumps(final_response, indent=2)
        #return json.dumps(fulfill_order, indent=2)
        
    

# Run your test scenarios by writing them here. Make sure to keep track of them.

def run_test_scenarios():
    
    print("Initializing Database...")
    init_database(db_engine)
    try:
        quote_requests_sample = pd.read_csv("quote_requests_sample.csv")
        quote_requests_sample["request_date"] = pd.to_datetime(
            quote_requests_sample["request_date"], format="%m/%d/%y", errors="coerce"
        )
        quote_requests_sample.dropna(subset=["request_date"], inplace=True)
        quote_requests_sample = quote_requests_sample.sort_values("request_date")
    except Exception as e:
        print(f"FATAL: Error loading test data: {e}")
        return
    #print(quote_requests_sample['request'])

    # Get initial state
    initial_date = quote_requests_sample["request_date"].min().strftime("%Y-%m-%d")
    report = generate_financial_report(initial_date)
    current_cash = report["cash_balance"]
    current_inventory = report["inventory_value"]

    print(f"Current Cash: {current_cash}")
    print(f"Current Inventory: {current_inventory}")
   

    ############
    ############
    ############
    # INITIALIZE YOUR MULTI AGENT SYSTEM HERE
    ############
    ############
    ############

    orchestrator = PaperSalesOrchestratorAgent(model, order_state)

    results = []
    for idx, row in quote_requests_sample.iterrows():

        #if idx >1:
            #break
        request_date = row["request_date"].strftime("%Y-%m-%d")

        print(f"\n=== Request {idx+1} ===")
        print(f"Context: {row['job']} organizing {row['event']}")
        print(f"Request Date: {request_date}")
        print(f"Cash Balance: ${current_cash:.2f}")
        print(f"Inventory Value: ${current_inventory:.2f}")

        # Process request
        request_with_date = f"{row['request']} (Date of request: {request_date})"
        #print(request_with_date.replace('"', "in"))
        ############
        ############
        ############
        # USE YOUR MULTI AGENT SYSTEM TO HANDLE THE REQUEST
        ############
        ############
        ############

        #response = call_your_multi_agent_system(request_with_date)
        response = orchestrator.process_order(request_with_date.replace('"', "in"))

        # Update state
        report = generate_financial_report(request_date)
        current_cash = report["cash_balance"]
        current_inventory = report["inventory_value"]

        print(f"Response: {response}")
        print(f"Updated Cash: ${current_cash:.2f}")
        print(f"Updated Inventory: ${current_inventory:.2f}")

        results.append(
            {
                "request_id": idx + 1,
                "request_date": request_date,
                "cash_balance": current_cash,
                "inventory_value": current_inventory,
                "response": response,
            }
        )

        time.sleep(1)
        print(f"================== END OF RUN {idx} ================================")

    # Final report
    final_date = quote_requests_sample["request_date"].max().strftime("%Y-%m-%d")
    final_report = generate_financial_report(final_date)
    print("\n===== FINAL FINANCIAL REPORT =====")
    print(f"Final Cash: ${final_report['cash_balance']:.2f}")
    print(f"Final Inventory: ${final_report['inventory_value']:.2f}")

    print("************* printing order state")
    print(order_state.model_dump_json(indent=2))
    print("************* printing order state")

 
    # Save results
    pd.DataFrame(results).to_csv("test_results.csv", index=False)
    return results

def test_tools():
    
    print("Testing Tools...")
    

    test_date = "2025-04-03"
    test_item1 = "colored paper"
    test_item2 = "Party streamers"
    lst_item = [test_item2]

    #print(check_item_inventory(test_item2, test_date))
    pprint(get_all_inventory(test_date))
    #print(get_all_transactions(test_date))
    #print(get_all_transactions(test_date).to_string(index=True))

    #pprint(search_quote_history(lst_item))
    #pprint(get_item_quote(test_item1))

    #print(get_item_supplier_delivery_date(test_item1, test_date, 300))

    #print(create_sales_transaction(test_item1, 300, 30, test_date))

    #print(create_stock_order_transaction(test_item1, 300, test_date))

    #print(get_catalog_items())
    #pprint(generate_financial_report(test_date))






if __name__ == "__main__":
    results = run_test_scenarios()
    #test_tools()
