# prompts/templates.py — All LLM prompt strings as named constants

ORDER_PROCESSOR_PROMPT = """\
The catalog contains the following items:
{catalog_items}

The customer says: "{customer_request}"

CRITICAL NORMALIZATION RULES
1. item_name MUST be the exact canonical name from the catalog.
2. Do NOT paraphrase or invent item_name.
3. If customer wording differs (e.g., "Glossy Paper" vs "A4 glossy paper"), normalize to the closest catalog item name.
4. If no catalog match is possible, keep the item_name provided by customer and set in_catalog to False.
5. Derive a short and relevant context from the customer request.
6. Return ONLY valid JSON. No text outside JSON.
7. Return only a single JSON object. Make sure all double quotes inside string values are escaped as \\" so the JSON parses correctly.

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

INVENTORY_MANAGER_PROMPT = """\
1. First identify the items in {order_items} and check if the item is available in the catalog
2. If the item is available in the catalog
    - Get the stock position for each of the item for the {request_date}
Respond as a json:
- order_id : {order_id}
- order_items: list of objects
    - item_name should match item_name in {order_items}
    - stock_position for the request date
    - request_date
    - item_status: "Stock Position Updated" (if stock position is available) | "Stock Not Available" (if stock position is not available)
    - output_message: short message on the process output
"""

QUOTE_GENERATOR_PROMPT = """\
1. First identify items in {order_items} and check if it is available in the catalog
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
    - item_name should match item_name in {order_items}
    - unit_price
    - discount
    - price_matching_confidence: High | Medium | Low
    - item_status: "Quote Price Updated" (if quote_price has been updated) | "Quote Price Not Available" (if quote_price is 0)
    - output_message: short message on the process output
"""

ORDER_FULFILLER_PROMPT = """\
You will fulfill orders that are pending in coordination with supplier.
The steps that you will follow in fulfilling orders are the following:

Step1 :
- Extract details of items in {order_items}

Step 2 :
- For items where 'estimated_delivery' date is available
    - Create a 'sales' transaction with order_quantity, quote_price and request_date in {order_items}
    - Create a 'stock order' transaction with order_quantity and request_date in {order_items} to replenish the inventory
    - Update item_status to "Order Fulfilled"

Step 3 :
- For items where 'estimated_delivery' date is NOT available
    - Get the estimated_delivery date from the supplier for order_quantity in {order_items}
        Step 3A : If estimated_delivery date is after delivery_required date
            - Do Nothing
            - Update item_status to "Order Fulfillment Failed"
        Step 3B : If estimated_delivery date is on or BEFORE delivery_required date
            - Create a 'sales' transaction with order_quantity, quote_price and request_date in {order_items}
            - Create a 'stock order' transaction with order_quantity and request_date in {order_items} to replenish the inventory
            - Update item_status to "Order Fulfilled"

Step 4: Respond as a json:
- order_id : {order_id}
- order_items: list of objects
    - item_name should match item_name in {order_items}
    - sales_transaction_id: Transaction id from 'sales' transaction of the item
    - estimated_delivery
    - item_status:
    - output_message: short message on the process output
"""

EXECUTIVE_SUMMARY_PROMPT = """\
You are a helpful assistant who can write great executive summaries.

Use the following to generate an insightful and brief executive summary of the order:
    - Financial Report that you generate for the request date
    - {final_response}

The executive summary is an insightful narrative description that is an amalgamation of the financial report and order details. The length of the description is around 30 words.

Respond as a text string.
"""
