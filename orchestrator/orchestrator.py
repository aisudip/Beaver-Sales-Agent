# orchestrator/orchestrator.py — PaperSalesOrchestratorAgent with error handling
import json
from typing import Any

from smolagents import ToolCallingAgent

from agents.base import create_agent
from catalog.catalog import paper_supplies
from config import ORDER_ID_FORMAT
from database.helper_fns import DatabaseError
from models.state import OrderState
from prompts.templates import (
    EXECUTIVE_SUMMARY_PROMPT,
    INVENTORY_MANAGER_PROMPT,
    ORDER_FULFILLER_PROMPT,
    ORDER_PROCESSOR_PROMPT,
    QUOTE_GENERATOR_PROMPT,
)
from tools.agent_tools import (
    check_item_inventory,
    create_sales_transaction,
    create_stock_order_transaction,
    prepare_financial_report,
    get_item_quote,
    get_item_supplier_delivery_date,
    get_stock_position,
)
from utils.agent_utils import dict_to_order, fulfill_order_dict, update_order_state
from utils.json_utils import parse_llm_json
from utils.logging import get_logger

logger = get_logger(__name__)


class AgentStageError(Exception):
    """Raised when a sub-agent stage fails."""


class PaperSalesOrchestratorAgent(ToolCallingAgent):
    """Orchestrates the workflow for paper inventory and order fulfillment."""

    def __init__(self, model, order_state: OrderState):
        super().__init__(
            tools=[prepare_financial_report],
            model=model,
            name="Orchestrator",
            description="Agent that orchestrates activities of other agents and brings their results together for final output",
        )
        self.order_processing_agent = create_agent(
            model, [], "order_processor",
            "Agent responsible for processing customer orders. Parses requests, identifies order names and quantities."
        )
        self.inventory_management_agent = create_agent(
            model, [get_stock_position], "inventory_manager",
            "Agent responsible for checking inventory and stock level."
        )
        self.quote_generation_agent = create_agent(
            model, [check_item_inventory, get_item_quote], "quote_generator",
            "Agent for generating quotes for incoming sales inquiries."
        )
        self.order_fulfillment_agent = create_agent(
            model,
            [create_stock_order_transaction, create_sales_transaction, get_item_supplier_delivery_date],
            "order_fulfiller",
            "Agent for fulfillment of orders including supplier logistics and transactions."
        )
        self.order_state = order_state

    # ------------------- agent helper -------------------

    def _run_agent_stage(self, agent: Any, prompt: str, stage_name: str) -> str:
        """Run an agent stage with consistent error handling and logging."""
        logger.info("Starting stage: %s", stage_name)
        try:
            result = agent.run(prompt)
            logger.debug("%s result: %s", stage_name, result)
            return result
        except Exception as e:
            logger.error("Stage %s failed: %s", stage_name, e)
            raise AgentStageError(f"{stage_name} failed: {e}") from e

    # --------------- agent processing ---------------

    def process_order(self, customer_request: str) -> str:
        """
        Process a customer order from initial request through fulfillment.

        Returns:
            JSON string with order details, summary, and status.
        """
        self.order_state.order_counter += 1
        order_id = ORDER_ID_FORMAT.format(self.order_state.order_counter)

        # Stage 1: Parse order
        try:
            raw = self._run_agent_stage(
                self.order_processing_agent,
                ORDER_PROCESSOR_PROMPT.format(
                    customer_request=customer_request,
                    order_id=order_id,
                    catalog_items=paper_supplies,
                ),
                "order_processing_agent",
            )
            parsed = parse_llm_json(raw)
            order_details = dict_to_order(parsed, self.order_state)
        except (AgentStageError, ValueError) as e:
            logger.error("Order parsing failed: %s", e)
            return json.dumps({"error": "order_parsing_failed", "detail": str(e)}, indent=2)

        # Stage 2: Inventory check (non-fatal)
        try:
            raw = self._run_agent_stage(
                self.inventory_management_agent,
                INVENTORY_MANAGER_PROMPT.format(
                    order_items=order_details["order_items"],
                    request_date=order_details["request_date"],
                    order_id=order_id,
                ),
                "inventory_management_agent",
            )
            updated_stock_resp = update_order_state(raw, self.order_state)
        except (AgentStageError, ValueError) as e:
            logger.warning("Inventory check failed, continuing with stock_position=0: %s", e)
            updated_stock_resp = order_details

        # Stage 3: Quote generation
        try:
            raw = self._run_agent_stage(
                self.quote_generation_agent,
                QUOTE_GENERATOR_PROMPT.format(
                    order_items=updated_stock_resp["order_items"],
                    customer_request=customer_request,
                    order_id=order_id,
                    catalog_items=paper_supplies,
                ),
                "quote_generation_agent",
            )
            parsed_price_map = parse_llm_json(raw)
            updated_quote = update_order_state(parsed_price_map, self.order_state, "quote_update")
        except (AgentStageError, ValueError) as e:
            logger.error("Quote generation failed: %s", e)
            return json.dumps({"error": "quote_generation_failed", "detail": str(e)}, indent=2)

        pending_order_response = fulfill_order_dict(updated_quote)

        if len(pending_order_response["order_items"]) == 0:
            final_response = updated_quote
            final_response["Order Summary"] = "There are no items in this order that could be fulfilled"
            return json.dumps(final_response, indent=2)

        pending_order = update_order_state(pending_order_response, self.order_state)

        # Stage 4: Fulfillment
        try:
            raw = self._run_agent_stage(
                self.order_fulfillment_agent,
                ORDER_FULFILLER_PROMPT.format(
                    order_items=pending_order["order_items"],
                    order_id=pending_order["order_id"],
                ),
                "order_fulfillment_agent",
            )
            final_response = update_order_state(raw, self.order_state, "Order Fulfilled")
        except (AgentStageError, DatabaseError, ValueError) as e:
            logger.error("Order fulfillment failed: %s", e)
            return json.dumps({"error": "fulfillment_failed", "detail": str(e)}, indent=2)

        # Stage 5: Executive summary (non-fatal)
        try:
            summary_response = self._run_agent_stage(
                self,
                EXECUTIVE_SUMMARY_PROMPT.format(final_response=final_response),
                "summary",
            )
        except AgentStageError:
            summary_response = "Summary unavailable"

        final_response["Order Summary"] = summary_response
        logger.debug("order_state.orders: %s", self.order_state.orders)
        return json.dumps(final_response, indent=2)
