from fastmcp import FastMCP
import os
import sqlite3
import tempfile
import aiosqlite

DB_PATH = os.environ.get(
    "EXPENSES_DB_PATH",
    os.path.join(tempfile.gettempdir(), "expenses.db"),
)
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

mcp = FastMCP("ExpenseTracker")
print(f"Database path: {DB_PATH}")

def init_db():
    try:
        with sqlite3.connect(DB_PATH) as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("""
            CREATE TABLE IF NOT EXISTS expenses(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                note TEXT DEFAULT ''
            )
            """)
            c.execute(
                "INSERT INTO expenses(date, amount, category) VALUES (?, ?, ?)",
                ("2000-01-01", 0, "__write_test__"),
            )
            c.execute("DELETE FROM expenses WHERE category = ?", ("__write_test__",))
        print("Database initialized successfully with write access")
    except Exception as error:
        print(f"Database initialization error: {error}")
        raise

init_db()

@mcp.tool()
async def add_expense(
    date: str,
    amount: float,
    category: str,
    subcategory: str = "",
    note: str = "",
):
    """Add a new expense entry to the database."""
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                "INSERT INTO expenses(date, amount, category, subcategory, note) VALUES (?, ?, ?, ?, ?)",
                (date, amount, category, subcategory, note),
            )
            expense_id = cur.lastrowid
            await c.commit()
            return {"status": "success", "id": expense_id, "message": "Expense added successfully"}
    except Exception as error:
        return {"status": "error", "message": f"Database error: {error}"}

@mcp.tool()
async def list_expenses(start_date: str, end_date: str):
    """List expense entries within an inclusive date range."""
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                """
                SELECT id, date, amount, category, subcategory, note
                FROM expenses
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC, id DESC
                """,
                (start_date, end_date),
            )
            cols = [description[0] for description in cur.description]
            return [dict(zip(cols, row)) for row in await cur.fetchall()]
    except Exception as error:
        return {"status": "error", "message": f"Error listing expenses: {error}"}

@mcp.tool()
async def summarize(start_date: str, end_date: str, category: str | None = None):
    """Summarize expenses by category within an inclusive date range."""
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            query = """
                SELECT category, SUM(amount) AS total_amount, COUNT(*) AS count
                FROM expenses
                WHERE date BETWEEN ? AND ?
            """
            params = [start_date, end_date]
            if category:
                query += " AND category = ?"
                params.append(category)
            query += " GROUP BY category ORDER BY total_amount DESC"
            cur = await c.execute(query, params)
            cols = [description[0] for description in cur.description]
            return [dict(zip(cols, row)) for row in await cur.fetchall()]
    except Exception as error:
        return {"status": "error", "message": f"Error summarizing expenses: {error}"}

@mcp.tool()
async def delete_expenses(expense_id: int):
    """Delete an expense from the database."""
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
            await c.commit()
            return {"status": "success", "deleted": cur.rowcount > 0}
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
    """Update an existing expense in the database."""
    fields = []
    params = []
    for field, value in (
        ("date", date),
        ("amount", amount),
        ("category", category),
        ("subcategory", subcategory),
        ("note", note),
    ):
        if value is not None:
            fields.append(f"{field} = ?")
            params.append(value)
    if not fields:
        return {"status": "error", "message": "No fields to update"}
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            params.append(expense_id)
            cur = await c.execute(
                f"UPDATE expenses SET {', '.join(fields)} WHERE id = ?", params
            )
            await c.commit()
            return {"status": "success", "updated": cur.rowcount > 0}
    except Exception as error:
        return {"status": "error", "message": f"Database error: {error}"}

@mcp.tool()
async def credit_money(amount: float, note: str = ""):
    """Add a credit entry to the database."""
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                "INSERT INTO expenses (date, amount, category, note) VALUES (date('now'), ?, 'Credit', ?)",
                (amount, note),
            )
            await c.commit()
            return {"status": "success", "id": cur.lastrowid}
    except Exception as error:
        return {"status": "error", "message": f"Database error: {error}"}

@mcp.tool()
async def get_balance():
    """Calculate the current balance based on expenses and credits."""
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE category != 'Credit'")
            expenses_total = (await cur.fetchone())[0]
            cur = await c.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE category = 'Credit'")
            credits_total = (await cur.fetchone())[0]
            return {"balance": credits_total - expenses_total}
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
        import json
        return json.dumps(default_categories, indent=2)
    except Exception as error:
        return f'{{"error": "Could not load categories: {error}"}}'



if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000) # for remote
    # mcp.run() # for local stdio