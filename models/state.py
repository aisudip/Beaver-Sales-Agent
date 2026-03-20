# models/state.py — Pydantic models for order state
from typing import List, Optional, Union
from pydantic import BaseModel, Field, ConfigDict


class OrderItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    item_name: str
    description: str = ""
    order_quantity: int = 0
    order_unit: str = ""
    in_catalog: int = 0
    stock_position: int = 0
    unit_price: float = 0.0
    discount: Union[float, int, str, None] = None
    discount_val: float = 0.0
    price_matching_confidence: str = ""
    quote_price: float = 0.0
    item_status: str = "Order Not Fulfilled"
    estimated_delivery: str = ""
    output_message: str = ""
    sales_transaction_id: Union[float, int, str, None] = None


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
