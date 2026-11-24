import csv
import hashlib
import io
from .schema import FIELDS, convert
from .model import mapper


def parse_csv(text):
    if len(text.encode()) > 256_000:
        raise ValueError("CSV exceeds 256 KB")
    reader = csv.reader(io.StringIO(text.lstrip("\ufeff")), strict=True)
    try:
        headers = next(reader)
        if not 1 <= len(headers) <= 32 or any(not h.strip() or len(h) > 100 for h in headers):
            raise ValueError("Use 1–32 nonempty column names, each at most 100 characters")
        if len(set(headers)) != len(headers):
            raise ValueError("Duplicate column names are not supported")
        rows = []
        for row in reader:
            if not row:
                continue
            if len(row) != len(headers):
                raise ValueError("Every row must have the same number of cells as the header")
            if any(len(v) > 2000 for v in row):
                raise ValueError("Cells must be at most 2,000 characters")
            rows.append(dict(zip(headers, row)))
            if len(rows) > 1000:
                raise ValueError("At most 1,000 rows per import")
        if not rows:
            raise ValueError("CSV must contain at least one data row")
    except (StopIteration, csv.Error):
        raise ValueError("Invalid or empty CSV") from None
    return headers, rows


def analyze(text):
    headers, rows = parse_csv(text)
    return {
        "status": "awaiting_review",
        "source_hash": hashlib.sha256(text.encode()).hexdigest(),
        "headers": headers,
        "rows": rows,
        "suggestions": mapper().propose(headers, rows),
        "mapping": None,
        "validation": None,
        "model_version": "column-logreg-v1",
    }


def validate_mapping(payload, mapping):
    if set(mapping) != set(payload["headers"]):
        raise ValueError("Mapping must specify every source column; use null to ignore")
    targets = [t for t in mapping.values() if t is not None]
    if any(t not in FIELDS for t in targets) or len(set(targets)) != len(targets):
        raise ValueError("Targets must be known and assigned at most once")
    missing = [f for f, s in FIELDS.items() if s["required"] and f not in targets]
    if missing:
        raise ValueError("Map required fields: " + ", ".join(missing))
    transformed = []
    issues = []
    ids = {}
    for index, row in enumerate(payload["rows"], start=2):
        out = {}
        for source, target in mapping.items():
            if target is None:
                continue
            try:
                out[target] = convert(row[source], target)
            except ValueError as exc:
                issues.append({"row": index, "source": source, "field": target, "message": str(exc)})
        cid = out.get("customer_id")
        if cid:
            ids.setdefault(cid, []).append(index)
        transformed.append(out)
    for cid, indices in ids.items():
        if len(indices) > 1:
            for index in indices:
                issues.append(
                    {
                        "row": index,
                        "source": next(s for s, t in mapping.items() if t == "customer_id"),
                        "field": "customer_id",
                        "message": "Duplicate customer ID within this import",
                    }
                )
    invalid = {i["row"] for i in issues}
    return {
        **payload,
        "status": "reviewed",
        "mapping": mapping,
        "validation": {
            "valid_rows": [r for i, r in enumerate(transformed, 2) if i not in invalid],
            "invalid_row_count": len(invalid),
            "issues": issues,
            "total_rows": len(transformed),
            "ignored_columns": [s for s, t in mapping.items() if t is None],
        },
    }


def export_csv(payload):
    if payload["status"] != "reviewed":
        raise ValueError("Review and validate the mapping before exporting")
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(FIELDS))
    writer.writeheader()
    for row in payload["validation"]["valid_rows"]:
        safe = {}
        for k, v in row.items():
            value = "" if v is None else str(v).lower() if isinstance(v, bool) else str(v)
            # Spreadsheet-safe text export. Numeric balance retains its canonical sign.
            if k != "balance" and value.lstrip().startswith(("=", "+", "-", "@")):
                value = "'" + value
            safe[k] = value
        writer.writerow(safe)
    return out.getvalue()
