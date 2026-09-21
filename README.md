# Expense Tracker MCP Server

A remote [Model Context Protocol](https://modelcontextprotocol.io/) server for managing expenses. The server runs on FastMCP and stores data in a Neon PostgreSQL database.

## Features

- Add, list, update, and delete expenses
- Summarize expenses by date range and category
- Record credits and calculate the current balance
- Expose an expense category resource at `expense:///categories`
- Automatically create the `expenses` table when the server starts
- Explicit input schemas for MCP client compatibility

## Requirements

- Python 3.13 or newer
- A Neon PostgreSQL database
- `uv` for dependency management

## Configuration

Create a local `.env` file in the project root:

```env
DATABASE_URL=postgresql://username:password@host/database?sslmode=require
```

The server also accepts the existing `neon_api` variable for backwards compatibility. `DATABASE_URL` is recommended for deployments.

Never commit `.env` or the database connection string. The repository already excludes `.env` through `.gitignore`.

## Local Development

Install dependencies:

```powershell
uv sync
```

Start the server over HTTP:

```powershell
uv run fastmcp run main.py --transport http --host 0.0.0.0 --port 8000
```

The MCP endpoint is:

```text
http://localhost:8000/mcp
```

To run the module directly instead:

```powershell
uv run python main.py
```

## FastMCP Cloud Deployment

Push the source code to GitHub without committing `.env`. In FastMCP Cloud, add the following runtime secret/environment variable:

```text
Name: DATABASE_URL
Value: your Neon PostgreSQL connection string
```

Redeploy after adding or changing the variable. FastMCP Cloud injects the value at runtime; GitHub repository secrets are only needed if a GitHub Actions workflow uses the secret.

The module can be inspected during the cloud build without a database secret. The Neon connection is validated when the server starts.

## MCP Tools

| Tool | Purpose |
| --- | --- |
| `add_expenses` | Add an expense with date, amount, category, subcategory, and note |
| `list_expenses` | List expenses within an inclusive date range |
| `summarize` | Group totals and counts by category |
| `update_expenses` | Update selected fields on an existing expense |
| `delete_expenses` | Delete an expense by ID |
| `credit_money` | Add a credit entry |
| `get_balance` | Return credits minus expenses |

Dates should use ISO format, for example `2026-09-21`. Amounts are numeric values. Database writes use parameterized SQL queries.

## Database Schema

The server creates this table automatically:

```sql
CREATE TABLE expenses (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT DEFAULT '',
    note TEXT DEFAULT ''
);
```

## Security

- Store Neon credentials only in local environment files or deployment secrets.
- Rotate the Neon password immediately if the connection string is exposed.
- Do not print or commit database credentials.
- Use a restricted database role for production deployments where possible.
