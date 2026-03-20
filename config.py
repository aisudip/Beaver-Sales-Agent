# config.py — All constants and configuration values

DB_PATH = "sqlite:///munder_difflin.db"
QUOTE_REQUESTS_CSV = "two_quote_requests.csv"
QUOTES_CSV = "quotes.csv"
TEST_SAMPLE_CSV = "two_quote_requests_sample.csv"
INITIAL_DATE = "2025-01-01"

OPENAI_MODEL_ID = "gpt-4o-mini"
OPENAI_BASE_URL = "https://openai.vocareum.com/v1"
MODEL_TEMPERATURE = 0.0
MODEL_SEED = 42

DELIVERY_LEAD_SMALL = 3        # days, for quantity < 500
DELIVERY_LEAD_LARGE = 7        # days, for quantity >= 500
DELIVERY_THRESHOLD = 500

QUOTE_SEARCH_LIMIT = 5

BULK_DISCOUNT_MAP = {"bulk": 0.10, "vip": 0.20}
ORDER_ID_FORMAT = "ORD-{:04d}"
