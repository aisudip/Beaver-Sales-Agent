# main.py — Entry point: run_test_scenarios()
import os
import sys

# If not running inside the project venv, re-exec with the correct Python
_venv_python = os.path.join(os.path.dirname(__file__), ".venv312", "Scripts", "python.exe")
if os.path.exists(_venv_python) and os.path.abspath(sys.executable) != os.path.abspath(_venv_python):
    import subprocess
    sys.exit(subprocess.call([_venv_python] + sys.argv))

import time

try:
    import dotenv
    dotenv.load_dotenv()
except ImportError:
    pass  # dotenv not installed; rely on environment variables already set

import pandas as pd
from smolagents import OpenAIServerModel

from config import MODEL_TEMPERATURE, MODEL_SEED, OPENAI_BASE_URL, OPENAI_MODEL_ID, TEST_SAMPLE_CSV
from database.engine import db_engine
from database.init_db import init_database
from models.state import OrderState
from orchestrator.orchestrator import PaperSalesOrchestratorAgent
from tools.agent_tools import generate_financial_report
from utils.logging import get_logger

logger = get_logger(__name__)

openai_api_key = os.getenv("UDACITY_OPENAI_API_KEY")

model = OpenAIServerModel(
    model_id=OPENAI_MODEL_ID,
    temperature=MODEL_TEMPERATURE,
    top_p=1.0,
    seed=MODEL_SEED,
    api_base=OPENAI_BASE_URL,
    api_key=openai_api_key,
)


def run_test_scenarios():
    logger.info("Initializing Database...")
    init_database(db_engine)

    try:
        quote_requests_sample = pd.read_csv(TEST_SAMPLE_CSV)
        quote_requests_sample["request_date"] = pd.to_datetime(
            quote_requests_sample["request_date"], format="%m/%d/%y", errors="coerce"
        )
        quote_requests_sample.dropna(subset=["request_date"], inplace=True)
        quote_requests_sample = quote_requests_sample.sort_values("request_date")
    except Exception as e:
        logger.error("FATAL: Error loading test data: %s", e)
        return

    initial_date = quote_requests_sample["request_date"].min().strftime("%Y-%m-%d")
    report = generate_financial_report(initial_date)
    current_cash = report["cash_balance"]
    current_inventory = report["inventory_value"]

    logger.info("Current Cash: %.2f", current_cash)
    logger.info("Current Inventory: %.2f", current_inventory)

    order_state = OrderState()
    orchestrator = PaperSalesOrchestratorAgent(model, order_state)

    results = []
    for idx, row in quote_requests_sample.iterrows():
        request_date = row["request_date"].strftime("%Y-%m-%d")

        logger.info("=== Request %d ===", idx + 1)
        logger.info("Context: %s organizing %s", row["job"], row["event"])
        logger.info("Request Date: %s", request_date)
        logger.info("Cash Balance: $%.2f", current_cash)
        logger.info("Inventory Value: $%.2f", current_inventory)

        request_with_date = f"{row['request']} (Date of request: {request_date})"
        response = orchestrator.process_order(request_with_date.replace('"', "in"))

        report = generate_financial_report(request_date)
        current_cash = report["cash_balance"]
        current_inventory = report["inventory_value"]

        logger.info("Response: %s", response)
        logger.info("Updated Cash: $%.2f", current_cash)
        logger.info("Updated Inventory: $%.2f", current_inventory)

        results.append({
            "request_id": idx + 1,
            "request_date": request_date,
            "cash_balance": current_cash,
            "inventory_value": current_inventory,
            "response": response,
        })

        time.sleep(1)
        logger.info("================== END OF RUN %d ================================", idx)

    final_date = quote_requests_sample["request_date"].max().strftime("%Y-%m-%d")
    final_report = generate_financial_report(final_date)
    logger.info("===== FINAL FINANCIAL REPORT =====")
    logger.info("Final Cash: $%.2f", final_report["cash_balance"])
    logger.info("Final Inventory: $%.2f", final_report["inventory_value"])
    logger.info("order_state: %s", order_state.model_dump_json(indent=2))

    pd.DataFrame(results).to_csv("test_results.csv", index=False)
    return results


if __name__ == "__main__":
    run_test_scenarios()
