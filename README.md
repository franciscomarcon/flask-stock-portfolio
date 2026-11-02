# Stock Portfolio

A web application for managing a simulated stock portfolio. This project began as a CS50x assignment and has been adapted for this portfolio with SQLite persistence and without the `cs50` library or educational session extensions.

## Features

- User registration and authentication with hashed passwords.
- Stock quote lookup by ticker symbol.
- Buy and sell shares with automatic balance updates.
- Portfolio overview with cash balance and estimated total value.
- Transaction history.
- Automatic database and table creation on first run.

## Tech stack

Python, Flask, SQLite, Jinja, Bootstrap, and `requests`.

## Getting started

Requires Python 3.10 or newer.

```bash
git clone <repository-url>
cd flask-stock-portfolio
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Set a secret key before starting the application:

```bash
export SECRET_KEY="a-long-random-secret-key"  # Windows PowerShell: $env:SECRET_KEY="..."
flask --app app run
```

Open <http://127.0.0.1:5000> and create an account. Each new user starts with a simulated balance of $10,000. The `finance.db` file is created automatically and is not included in the repository.

Set `DATABASE_PATH` to use a different database location. For development with automatic reload, set `FLASK_DEBUG=1`.

## Stock quotes

Quotes are retrieved through the CS50 Finance quote endpoint (`finance.cs50.io`). An internet connection is required to look up, buy, or sell stocks. Values are for educational purposes and do not represent a brokerage service.

## Project structure

```text
app.py                 Routes, authentication, and portfolio logic
helpers.py             Quote lookup and currency formatting
templates/             Flask-rendered pages
static/                Application styles
```

## Credits

Based on the Finance assignment from CS50x. The application structure, business logic, and adaptations in this repository reflect the author's implementation. The quote endpoint is provided by CS50 Finance.
