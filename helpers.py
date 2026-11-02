"""Small helpers for price lookup and currency formatting."""

import requests


def lookup(symbol):
    """Return the latest quote for a ticker, or None when unavailable."""
    try:
        response = requests.get(
            "https://finance.cs50.io/quote",
            params={"symbol": symbol.upper()},
            timeout=8,
        )
        response.raise_for_status()
        data = response.json()
        return {
            "name": data["companyName"],
            "price": float(data["latestPrice"]),
            "symbol": symbol.upper(),
        }
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return None


def usd(value):
    """Format a numeric amount as US dollars."""
    return f"${value:,.2f}"
