"""Fixed customer-import contract: the model proposes; the contract validates."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

FIELDS = {
    "customer_id": {
        "type": "identifier",
        "required": True,
        "description": "Stable customer account identifier",
    },
    "full_name": {"type": "text", "required": True, "description": "Full customer name"},
    "email": {"type": "email", "required": True, "description": "Contact email address"},
    "phone": {"type": "phone", "required": False, "description": "Telephone number"},
    "postal_code": {"type": "postal", "required": False, "description": "US ZIP code preserved as text"},
    "joined_date": {"type": "date", "required": False, "description": "Signup date in ISO YYYY-MM-DD"},
    "balance": {
        "type": "money",
        "required": False,
        "description": "Account balance, decimal with at most two fractional digits",
    },
    "active": {"type": "boolean", "required": False, "description": "Whether the account is active"},
}


def convert(value, field):
    value = value.strip()
    if not value:
        if FIELDS[field]["required"]:
            raise ValueError("Required value is blank")
        return None
    kind = FIELDS[field]["type"]
    if kind == "email":
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Expected an email address")
        return value
    if kind == "date":
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Use an unambiguous ISO date: YYYY-MM-DD")
        return date.fromisoformat(value).isoformat()
    if kind == "money":
        try:
            number = Decimal(value)
        except InvalidOperation:
            raise ValueError("Expected a decimal amount") from None
        if not number.is_finite() or abs(number) > Decimal("1000000000") or number.as_tuple().exponent < -2:
            raise ValueError("Amount must be finite, within 1 billion, and have at most 2 decimal places")
        return str(number.quantize(Decimal(".01")))
    if kind == "boolean":
        if value.lower() not in {"true", "false", "yes", "no", "1", "0"}:
            raise ValueError("Expected true/false, yes/no, or 1/0")
        return value.lower() in {"true", "yes", "1"}
    if kind == "postal" and not re.fullmatch(r"\d{5}(-\d{4})?", value):
        raise ValueError("Expected US ZIP or ZIP+4")
    if kind == "phone" and not re.fullmatch(r"[+()\d .-]{7,30}", value):
        raise ValueError("Expected a telephone number")
    return value
