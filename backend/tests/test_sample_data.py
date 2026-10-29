"""The walkthrough in sample_data/README.md must really work."""

from pathlib import Path

from tests.helpers import D, clean, ready_dataset

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "sales_sample.csv"


def test_sample_dataset_walkthrough(client, make_actor):
    ana = make_actor("Ana")
    _, did = ready_dataset(client, ana, content=SAMPLE.read_bytes(), filename="sales_sample.csv")

    profile = client.get(f"{D}/{did}/profile", headers=ana.headers).json()
    assert profile["row_count"] == 62 and profile["duplicate_rows"] == 2
    cols = {c["name"]: c for c in profile["columns"]}
    assert cols["amount"]["missing"] > 0
    assert cols["order_date"]["dtype"] == "datetime"
    assert cols["repeat_customer"]["dtype"] == "string"

    job = clean(
        client,
        ana,
        did,
        [
            {"op": "drop_duplicates"},
            {"op": "trim_whitespace", "columns": ["customer"]},
            {"op": "fill_missing", "column": "amount", "strategy": "mean"},
            {"op": "cast_type", "column": "repeat_customer", "to": "boolean"},
        ],
    )
    assert job["status"] == "succeeded", job
    assert job["result"]["rows_before"] == 62 and job["result"]["rows_after"] == 60

    after = client.get(f"{D}/{did}/profile", headers=ana.headers).json()
    assert after["duplicate_rows"] == 0 and after["version"] == 2
    cols = {c["name"]: c for c in after["columns"]}
    assert cols["amount"]["missing"] == 0
    assert cols["repeat_customer"]["dtype"] == "boolean"
    assert all(not str(t["value"]).endswith(" ") for t in cols["customer"]["top_values"])
