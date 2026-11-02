"""Stock portfolio web application."""

import os
import sqlite3
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import lookup, usd

BASE_DIR = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "finance.db"))

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "dev-key-change-before-deploying"),
    DATABASE=str(DATABASE),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
app.jinja_env.filters["usd"] = usd


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the application tables if they do not exist."""
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            hash TEXT NOT NULL,
            cash REAL NOT NULL DEFAULT 10000.00
        );
        CREATE TABLE IF NOT EXISTS possessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            symbol TEXT NOT NULL,
            shares INTEGER NOT NULL CHECK (shares > 0),
            UNIQUE (user_id, symbol)
        );
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            symbol TEXT NOT NULL,
            shares INTEGER NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('Buy', 'Sell')),
            price REAL NOT NULL,
            datetime TEXT NOT NULL
        );
    """)
    db.commit()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def error(message, status=400):
    return render_template("apology.html", top=status, bottom=message), status


def positive_integer(field):
    try:
        amount = int(request.form.get(field, ""))
    except (TypeError, ValueError):
        return None
    return amount if amount > 0 else None


@app.after_request
def prevent_caching(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/")
@login_required
def index():
    db = get_db()
    holdings = db.execute(
        "SELECT symbol, shares FROM possessions WHERE user_id = ? ORDER BY symbol",
        (session["user_id"],),
    ).fetchall()
    portfolio = []
    for holding in holdings:
        quote = lookup(holding["symbol"])
        if quote:
            quote["shares"] = holding["shares"]
            portfolio.append(quote)
    cash = db.execute("SELECT cash FROM users WHERE id = ?", (session["user_id"],)).fetchone()["cash"]
    total = cash + sum(item["price"] * item["shares"] for item in portfolio)
    return render_template("index.html", table=portfolio, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")
    symbol = request.form.get("symbol", "").strip().upper()
    shares = positive_integer("shares")
    if not symbol:
        return error("Please provide a stock symbol.")
    if shares is None:
        return error("Shares must be a positive whole number.")
    quote = lookup(symbol)
    if quote is None:
        return error("That stock symbol was not found.")

    db = get_db()
    cost = quote["price"] * shares
    try:
        with db:
            account = db.execute("SELECT cash FROM users WHERE id = ?", (session["user_id"],)).fetchone()
            if account is None or cost > account["cash"]:
                return error("There is not enough cash for this purchase.")
            db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", (cost, session["user_id"]))
            db.execute("""INSERT INTO possessions (user_id, symbol, shares) VALUES (?, ?, ?)
                ON CONFLICT(user_id, symbol) DO UPDATE SET shares = shares + excluded.shares""",
                (session["user_id"], quote["symbol"], shares))
            record_trade(db, quote, shares, "Buy")
    except sqlite3.Error:
        app.logger.exception("Could not complete purchase")
        return error("The purchase could not be completed.", 500)
    flash("Purchase completed.")
    return redirect(url_for("index"))


def record_trade(db, quote, shares, trade_type):
    db.execute(
        "INSERT INTO history (user_id, symbol, shares, type, price, datetime) VALUES (?, ?, ?, ?, ?, ?)",
        (session["user_id"], quote["symbol"], shares, trade_type, quote["price"],
         datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    db = get_db()
    if request.method == "GET":
        stocks = db.execute("SELECT symbol FROM possessions WHERE user_id = ? ORDER BY symbol", (session["user_id"],)).fetchall()
        return render_template("sell.html", stocks=stocks)
    symbol = request.form.get("symbol", "").strip().upper()
    shares = positive_integer("shares")
    if not symbol:
        return error("Please choose a stock symbol.")
    if shares is None:
        return error("Shares must be a positive whole number.")
    quote = lookup(symbol)
    if quote is None:
        return error("That stock symbol was not found.")
    try:
        with db:
            holding = db.execute("SELECT shares FROM possessions WHERE user_id = ? AND symbol = ?",
                                 (session["user_id"], symbol)).fetchone()
            if holding is None or shares > holding["shares"]:
                return error("You do not own enough shares to complete this sale.")
            remaining = holding["shares"] - shares
            if remaining:
                db.execute("UPDATE possessions SET shares = ? WHERE user_id = ? AND symbol = ?",
                           (remaining, session["user_id"], symbol))
            else:
                db.execute("DELETE FROM possessions WHERE user_id = ? AND symbol = ?", (session["user_id"], symbol))
            db.execute("UPDATE users SET cash = cash + ? WHERE id = ?",
                       (quote["price"] * shares, session["user_id"]))
            record_trade(db, quote, shares, "Sell")
    except sqlite3.Error:
        app.logger.exception("Could not complete sale")
        return error("The sale could not be completed.", 500)
    flash("Sale completed.")
    return redirect(url_for("index"))


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("quote.html")
    symbol = request.form.get("symbol", "").strip()
    if not symbol:
        return error("Please provide a stock symbol.")
    info = lookup(symbol)
    if info is None:
        return error("That stock symbol was not found.")
    return render_template("quoted.html", info=info)


@app.route("/history")
@login_required
def history():
    trades = get_db().execute(
        "SELECT symbol, shares, type, price, datetime FROM history WHERE user_id = ? ORDER BY id DESC",
        (session["user_id"],),
    ).fetchall()
    return render_template("history.html", table=trades)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    confirmation = request.form.get("confirmation", "")
    if not username or not password or not confirmation:
        return error("Username, password, and confirmation are required.")
    if password != confirmation:
        return error("Passwords do not match.")
    try:
        with get_db() as db:
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)",
                       (username, generate_password_hash(password)))
    except sqlite3.IntegrityError:
        return error("That username is already registered.")
    flash("Account created. Please log in.")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    user = get_db().execute("SELECT id, hash FROM users WHERE username = ?", (username,)).fetchone()
    if user is None or not check_password_hash(user["hash"], password):
        return error("Invalid username or password.", 403)
    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
