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

# RDS requires (or strongly recommends) TLS; local Docker Postgres doesn't have
# a cert to offer, so this defaults to "prefer" and gets tightened via env var
# once pointed at a real RDS endpoint (e.g. POSTGRES_SSLMODE=require).
sslmode = os.getenv("POSTGRES_SSLMODE", "prefer")

engine = create_engine(
    f"postgresql+psycopg2://{user}:{password}@{db_host}:{db_port}/{db_name}",
    connect_args={"sslmode": sslmode},
)

class Base(DeclarativeBase):
    pass

def get_db():
    db = Session(engine)
    try:
        yield db
    finally:
        db.close()