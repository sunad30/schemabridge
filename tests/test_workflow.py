import csv
import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.domain import parse_csv, analyze, validate_mapping, export_csv
from app.main import create_app
from app.schema import convert

SAMPLE = Path("samples/customers.csv").read_text()
MAPPING = dict(
    zip(
        [
            "client_ref",
            "customer_full_name",
            "email_address",
            "telephone_no",
            "zip_code",
            "signup_date",
            "amount_due",
            "enabled",
        ],
        ["customer_id", "full_name", "email", "phone", "postal_code", "joined_date", "balance", "active"],
    )
)


@pytest.mark.parametrize("text", ["", "a,a\n1,2", "a,b\n1", "a\n", "a\n" + ("x" * 2001)])
def test_rejects_bad_csv(text):
    with pytest.raises(ValueError):
        parse_csv(text)


def test_model_and_review_export():
    run = analyze(SAMPLE)
    assert {s["source"]: s["target"] for s in run["suggestions"]} == MAPPING
    with pytest.raises(ValueError):
        export_csv(run)
    result = validate_mapping(run, MAPPING)
    assert len(result["validation"]["valid_rows"]) == 1
    assert result["validation"]["invalid_row_count"] == 3
    rows = list(csv.DictReader(io.StringIO(export_csv(result))))
    assert rows[0]["postal_code"] == "02108"
    assert rows[0]["balance"] == "18.50"
    assert rows[0]["phone"].startswith("'+")


def test_duplicate_targets_and_missing_required():
    run = analyze(SAMPLE)
    with pytest.raises(ValueError):
        validate_mapping(run, {k: "email" for k in MAPPING})
    with pytest.raises(ValueError):
        validate_mapping(run, {k: None for k in MAPPING})


@pytest.mark.parametrize("value", ["NaN", "Infinity", "1.123", "1000000001"])
def test_money_validation(value):
    with pytest.raises(ValueError):
        convert(value, "balance")


def test_formula_export_and_unknown_column():
    run = analyze('id,name,email,noise\nC-1,=HYPERLINK("evil"),a@example.test,hello')
    reviewed = validate_mapping(
        run, {"id": "customer_id", "name": "full_name", "email": "email", "noise": None}
    )
    assert list(csv.DictReader(io.StringIO(export_csv(reviewed))))[0]["full_name"].startswith("'=")
    assert reviewed["validation"]["ignored_columns"] == ["noise"]


def test_http_workflow_and_boundaries(tmp_path):
    with TestClient(create_app(str(tmp_path / "db"))) as client:
        assert client.get("/").status_code == 200
        assert client.post("/api/runs", json={"csv": "a,a\n1,2"}).status_code == 422
        response = client.post("/api/runs", json={"csv": SAMPLE})
        assert response.status_code == 201
        run = response.json()
        url = "/api/runs/" + run["id"]
        assert client.get(url + "/export").status_code == 422
        assert client.post(url + "/review", json={"version": 1, "mapping": MAPPING}).status_code == 200
        assert client.post(url + "/review", json={"version": 1, "mapping": MAPPING}).status_code == 409
        assert client.get(url + "/export").headers["content-type"].startswith("text/csv")
        assert client.get("/api/runs/unknown").status_code == 404
        assert (
            client.post(
                "/api/runs", headers={"Origin": "https://evil.test"}, json={"csv": SAMPLE}
            ).status_code
            == 403
        )
        assert client.post("/api/runs", content=b"x" * 2000001).status_code == 413
