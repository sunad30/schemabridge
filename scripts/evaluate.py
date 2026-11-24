"""Held-out alias smoke evaluation; not a real-customer benchmark."""

import json
from app.model import mapper
from pathlib import Path

CASES = {
    "customer_id": "client_ref",
    "full_name": "customer_full_name",
    "email": "email_address",
    "phone": "telephone_no",
    "postal_code": "postal_zip_code",
    "joined_date": "signup_timestamp",
    "balance": "unpaid_balance",
    "active": "account_enabled",
}


def evaluate():
    training = json.loads(Path("samples/training.json").read_text())
    assert not set(CASES.values()) & {x["header"] for x in training}
    vals = {x["field"]: x["values"] for x in training}
    rows = [{h: vals[f][i] for f, h in CASES.items()} for i in range(3)]
    output = mapper().propose(list(CASES.values()), rows)
    cases = [
        {
            "header": s["source"],
            "expected": next(f for f, h in CASES.items() if h == s["source"]),
            "predicted": s["target"],
        }
        for s in output
    ]
    result = {
        "dataset": "8 held-out header aliases; familiar synthetic value distributions",
        "correct": sum(c["expected"] == c["predicted"] for c in cases),
        "total": len(cases),
        "cases": cases,
        "limitations": "Small author-written smoke set; no real-world accuracy claim. Values share distributions with training.",
    }
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    evaluate()
