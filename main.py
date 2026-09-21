import asyncio
from contextlib import asynccontextmanager
import json
import os

import psycopg
from dotenv import load_dotenv
from fastmcp import FastMCP
from psycopg.rows import dict_row

load_dotenv()

CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")


def get_database_url():
    database_url = os.getenv("neon_api") or os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("Set DATABASE_URL in the FastMCP Cloud environment")
    return database_url


def run_async(coroutine):
    if os.name == "nt":
        return asyncio.run(coroutine, loop_factory=asyncio.SelectorEventLoop)
    return asyncio.run(coroutine)


def init_db():
    with psycopg.connect(get_database_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS expenses(
                    id BIGSERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    amount DOUBLE PRECISION NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT DEFAULT '',
                    note TEXT DEFAULT ''
                )
                """
            )
        connection.commit()
    print("Neon database initialized successfully")


@asynccontextmanager
async def app_lifespan(_server):
    init_db()
    yield


mcp = FastMCP("ExpenseTracker", lifespan=app_lifespan)


@mcp.tool()
async def add_expenses(
    date: str,
    amount: float,
    category: str,
    subcategory: str = "",
    note: str = "",
):
    """Add a new expense entry to the Neon database."""
    try:
        with psycopg.connect(
            get_database_url(), row_factory=dict_row
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO expenses(date, amount, category, subcategory, note)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (date, amount, category, subcategory, note),
                )
                expense_id = cursor.fetchone()["id"]
            connection.commit()
        return {"status": "success", "id": expense_id, "message": "Expense added successfully"}
    except Exception as error:
        return {"status": "error", "message": f"Database error: {error}"}


@mcp.tool()
async def list_expenses(start_date: str, end_date: str):
    """List expense entries within an inclusive date range."""
    try:
        with psycopg.connect(
            get_database_url(), row_factory=dict_row
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, date, amount, category, subcategory, note
                    FROM expenses
                    WHERE date BETWEEN %s AND %s
                    ORDER BY date DESC, id DESC
                    """,
                    (start_date, end_date),
                )
                return cursor.fetchall()
    except Exception as error:
        return {"status": "error", "message": f"Error listing expenses: {error}"}


@mcp.tool()
async def summarize(start_date: str, end_date: str, category: str | None = None):
    """Summarize expenses by category within an inclusive date range."""
    try:
        query = """
            SELECT category, SUM(amount) AS total_amount, COUNT(*) AS count
            FROM expenses
            WHERE date BETWEEN %s AND %s
        """
        params: list[str | None] = [start_date, end_date]
        if category:
            query += " AND category = %s"
            params.append(category)
        query += " GROUP BY category ORDER BY total_amount DESC"

        with psycopg.connect(
            get_database_url(), row_factory=dict_row
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()
    except Exception as error:
        return {"status": "error", "message": f"Error summarizing expenses: {error}"}


@mcp.tool()
async def delete_expenses(expense_id: int):
    """Delete an expense from the Neon database."""
    try:
        with psycopg.connect(get_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM expenses WHERE id = %s", (expense_id,))
                deleted = cursor.rowcount > 0
            connection.commit()
        return {"status": "success", "deleted": deleted}
    except Exception as error:
        return {"status": "error", "message": f"Database error: {error}"}


@mcp.tool()
async def update_expenses(
    expense_id: int,
    date: str | None = None,
    amount: float | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    note: str | None = None,
):
    """Update an existing expense in the Neon database."""
    values = {
        "date": date,
        "amount": amount,
        "category": category,
        "subcategory": subcategory,
        "note": note,
    }
    fields = [f"{field} = %s" for field, value in values.items() if value is not None]
    params = [value for value in values.values() if value is not None]
    if not fields:
        return {"status": "error", "message": "No fields to update"}

    try:
        with psycopg.connect(get_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE expenses SET {', '.join(fields)} WHERE id = %s",
                    [*params, expense_id],
                )
                updated = cursor.rowcount > 0
            connection.commit()
        return {"status": "success", "updated": updated}
    except Exception as error:
        return {"status": "error", "message": f"Database error: {error}"}


@mcp.tool()
async def credit_money(amount: float, note: str = ""):
    """Add a credit entry to the Neon database."""
    try:
        with psycopg.connect(
            get_database_url(), row_factory=dict_row
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO expenses(date, amount, category, note)
                    VALUES (CURRENT_DATE, %s, 'Credit', %s)
                    RETURNING id
                    """,
                    (amount, note),
                )
                expense_id = cursor.fetchone()["id"]
            connection.commit()
        return {"status": "success", "id": expense_id}
    except Exception as error:
        return {"status": "error", "message": f"Database error: {error}"}


@mcp.tool()
async def get_balance():
    """Calculate the current balance based on expenses and credits."""
    try:
        with psycopg.connect(
            get_database_url(), row_factory=dict_row
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(CASE WHEN category = 'Credit' THEN amount ELSE 0 END), 0)
                        - COALESCE(SUM(CASE WHEN category <> 'Credit' THEN amount ELSE 0 END), 0)
                        AS balance
                    FROM expenses
                    """
                )
                return {"balance": cursor.fetchone()["balance"]}
    except Exception as error:
        return {"status": "error", "message": f"Database error: {error}"}


@mcp.resource("expense:///categories", mime_type="application/json")
def categories():
    default_categories = {
        "categories": [
            "Food & Dining", "Transportation", "Shopping", "Entertainment",
            "Bills & Utilities", "Healthcare", "Travel", "Education",
            "Business", "Other",
        ]
    }
    try:
        with open(CATEGORIES_PATH, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return json.dumps(default_categories, indent=2)
    except Exception as error:
        return json.dumps({"error": f"Could not load categories: {error}"})


if __name__ == "__main__":
    run_async(mcp.run_async(transport="http", host="0.0.0.0", port=8000)) # for remote
    # mcp.run() # for local stdio