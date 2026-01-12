import os
from fastapi import FastAPI
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

DATABASE_URL = os.getenv("DATABASE_URL")

app = FastAPI(title="Backend FastAPI Service")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/db-check")
def db_check():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            return {"database": "connected", "result": result.scalar()}
    except SQLAlchemyError as e:
        return {"database": "error", "detail": str(e), "url": DATABASE_URL}
