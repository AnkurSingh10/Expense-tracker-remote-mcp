import random 
from fastmcp import FastMCP
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "expenses.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

mcp = FastMCP(name = "Expense Tracker")

def init_db():
    with sqlite3.connect(DB_PATH) as c:
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
init_db()

@mcp.tool()
def add_expenses(
    date: str,
    amount: float,
    category: str,
    subcategory: str = '',
    note: str = '',
):
    """Add an new expense to the database."""
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute("INSERT INTO expenses (date, amount, category, subcategory, note) VALUES (?, ?, ?, ?, ?)",
                  (date, amount, category, subcategory, note))
    
    return {"status": "ok", "id": cur.lastrowid}

@mcp.tool()
def list_expenses(start_date: str, end_date: str):
    """List expense entries within an inclusive date range."""
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            """
            SELECT *
            FROM expenses
            WHERE date BETWEEN ? AND ?
            ORDER BY id ASC
        """,
        (start_date, end_date) 
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

@mcp.tool()
def summarize(start_date: str, end_date: str, category: str | None = None):
     '''Summarize expenses by category within an inclusive date range.'''
     with sqlite3.connect(DB_PATH) as c:
         query = (
             """
            SELECT id, category, SUM(amount) AS total_amount
            FROM expenses
            WHERE date BETWEEN ? AND ?
            """
         )
         params = [start_date, end_date]

         if category:
             query+= "AND category = ?"
             params.append(category)
         query+= " GROUP BY category ORDER BY category ASC"

         cur = c.execute(query, params)
         cols = [d[0] for d in cur.description]
         return [dict(zip(cols, r)) for r in cur.fetchall()]

@mcp.tool()
def delete_expenses(expense_id: int):
    """Delete an expense from the database."""
    with sqlite3.connect(DB_PATH) as c:
        c.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))

@mcp.tool()
def update_expenses(
    expense_id: int,
    date: str | None = None,
    amount: float | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    note: str | None = None,
):
    """Update an existing expense in the database."""
    with sqlite3.connect(DB_PATH) as c:
        # Build the update query dynamically based on provided parameters
        fields = []
        params = []
        if date is not None:
            fields.append("date = ?")
            params.append(date)
        if amount is not None:
            fields.append("amount = ?")
            params.append(amount)
        if category is not None:
            fields.append("category = ?")
            params.append(category)
        if subcategory is not None:
            fields.append("subcategory = ?")
            params.append(subcategory)
        if note is not None:
            fields.append("note = ?")
            params.append(note)

        if not fields:
            return {"status": "error", "message": "No fields to update"}

        query = f"UPDATE expenses SET {', '.join(fields)} WHERE id = ?"
        params.append(expense_id)

        c.execute(query, params)

@mcp.tool()
def credit_money(amount: float, note: str = ''):
    """Add a credit entry to the database."""
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute("INSERT INTO expenses (date, amount, category, note) VALUES (date('now'), ?, 'Credit', ?)",
                  (amount, note))
    
    return {"status": "ok", "id": cur.lastrowid}

@mcp.tool()
def get_balance():
    """Calculate the current balance based on expenses and credits."""
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute("SELECT SUM(amount) FROM expenses Where category != 'Credit'")
        cur2 = c.execute("SELECT SUM(amount) FROM expenses Where category = 'Credit'")
        total = cur2.fetchone()[0]-cur.fetchone()[0]
        return {"balance": total if total is not None else 0.0}

@mcp.resource("expense://categories", mime_type="application/json")
def categories():
    #Read fresh each time so you can edit the file without restarting
    with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
        return f.read()



if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000) # for remote
    # mcp.run() # for local stdio