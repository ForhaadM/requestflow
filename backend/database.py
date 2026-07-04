from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session
from dotenv import load_dotenv
import os

load_dotenv()

user = os.getenv("POSTGRES_USER")
password = os.getenv("POSTGRES_PASSWORD")
db_name = os.getenv("POSTGRES_DB")
db_host = os.getenv("POSTGRES_HOST")
db_port = os.getenv("POSTGRES_PORT")

engine = create_engine(f"postgresql+psycopg2://{user}:{password}@{db_host}:{db_port}/{db_name}")

class Base(DeclarativeBase):
    pass