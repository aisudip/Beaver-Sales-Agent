# database/engine.py — SQLAlchemy engine creation
from sqlalchemy import create_engine, Engine
from config import DB_PATH

db_engine: Engine = create_engine(DB_PATH)
