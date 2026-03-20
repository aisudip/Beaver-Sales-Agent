# utils/agent_utils.py — Helper functions for order processing
from typing import Any, Dict

from config import BULK_DISCOUNT_MAP
from models.state import Order, OrderItem, OrderState
from utils.json_utils import coerce_payload
from utils.logging import get_logger

logger = get_logger(__name__)


def normalize_discount(discount: Any) -> float:
    """Convert discount strings/labels to a float fraction.
        Convert discount strings to float when possible.
        Supports:
        - percentage strings: '10%' -> 0.10
        - decimal strings: '0.15' -> 0.15
        - mapped labels: 'Bulk' -> 0.10, 'VIP' -> 0.20
        Returns 0  for non-numeric labels.
    """    
    if not isinstance(discount, str):
        return discount

    value = discount.strip()
    low = value.lower()

    # # Case 0: mapped symbolic labels ("Bulk", "VIP", etc.)
    if low in BULK_DISCOUNT_MAP:
        return BULK_DISCOUNT_MAP[low]
    
    # Case 1: percentage strings e.g. "10%" or "7.5%"
    if value.endswith('%'):
        try:
            return float(value[:-1]) / 100.0
        except ValueError:
            return 0
        
    # Case 2: float-like strings e.g. "0.15"
    try:
        return float(value)
    except ValueError:
        return 0


def dict_to_order(payload: Dict[str, Any], order_state: OrderState) -> Dict[str, Any]:
    """Convert a parsed LLM payload into an Order and append it to order_state.
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
    logger.debug("dict_to_order payload: %s", payload)
    payload = coerce_payload(payload)

    requested_items = payload.get("requested_items", []) or []
    order_items = [OrderItem.model_validate(it) for it in requested_items]

    # Create Order and append to state
    order_data = {
        "order_id": payload.get("order_id"),
        "order_items": order_items,
        "request_date": payload.get("request_date"),
        "delivery_required_date": payload.get("delivery_required_date"),
        "order_context": payload.get("order_context", ""),
    }

    order = Order.model_validate(order_data)
    order_state.orders.append(order)
    return order.model_dump()


def fulfill_order_dict(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare the subset of order items ready for fulfillment."""
    logger.debug("fulfill_order_dict payload: %s", payload)
    fulfill_order = {"order_id": payload["order_id"], "order_items": []}
    request_date = payload["request_date"]
    delivery_required = payload["delivery_required_date"]

    for item in payload["order_items"]:
        if item["quote_price"] > 0:
            estimated_delivery = request_date if item["order_quantity"] <= item["stock_position"] else ""
            fulfill_order["order_items"].append({
                "item_name": item["item_name"],
                "order_quantity": item["order_quantity"],
                "stock_position": item["stock_position"],
                "quote_price": item["quote_price"],
                "request_date": request_date,
                "estimated_delivery": estimated_delivery,
                "delivery_required": delivery_required,
            })

    return fulfill_order


def update_order_state(
    update_payload: Any, order_state: OrderState, input_type: str = "default"
) -> Dict[str, Any]:
    """Update an existing OrderState with partial item-level updates."""
    logger.debug("update_order_state input_type=%s payload=%s", input_type, update_payload)
    # Coerce the payload to a dict if it's not already
    update_payload = coerce_payload(update_payload)

    # For quote updates, we may need to normalize discount values and recalculate quote_price
    if input_type == "quote_update":
        items = update_payload.get("order_items")
        if not items:
            logger.warning("quote_update payload has no order_items: %s", update_payload)
            return order_state.model_dump()
        for item in items:
            item["discount_val"] = normalize_discount(item.get("discount"))

    target_order_id = update_payload.get("order_id")
    if not target_order_id:
        raise ValueError("update_payload must contain order_id")

    updates_by_item = {
        item["item_name"]: item
        for item in update_payload.get("order_items", [])
        if "item_name" in item
    }

    patchable = (
        "in_catalog", "stock_position", "quote_price", "item_status",
        "output_message", "sales_transaction_id", "estimated_delivery",
        "unit_price", "discount", "discount_val", "price_matching_confidence",
    )
    numeric_fields = ("unit_price", "discount_val", "stock_position", "quote_price")

    # Apply updates to the matching order and items in state
    for order in order_state.orders:
        if order.order_id != target_order_id:
            continue

        for order_item in order.order_items:
            update = updates_by_item.get(order_item.item_name)
            if not update:
                continue

            updated = False
            for field in patchable:
                if field not in update:
                    continue
                old = getattr(order_item, field)
                new = update[field]
                if field in numeric_fields and new is not None and isinstance(new, str):
                    try:
                        new = float(new)
                    except ValueError:
                        new = 0.0
                if old != new:
                    setattr(order_item, field, new)
                    updated = True

            if updated and input_type == "quote_update":
                dv = float(order_item.discount_val or 0.0)
                norm_discount_val = dv / (1 + 99 * (dv > 1))
                unit_price = float(order_item.unit_price or 0.0)
                order_item.quote_price = (
                    order_item.order_quantity * unit_price * (1 - norm_discount_val)
                )

        break

    order = next(
        (o for o in order_state.orders if o.order_id == target_order_id), None
    )
    return order.model_dump() if order else {}
