import io
from typing import Any

import pandas as pd

SAMPLE_CSV = (
    b"id,name,amount,joined,active\n"
    b"1, Ann ,10.5,2024-01-02,yes\n"
    b"2,Bob,,2024-01-03,no\n"
    b"2,Bob,,2024-01-03,no\n"
    b"3,,7,2024-02-01,yes\n"
)

P = "/api/v1/projects"
D = "/api/v1/datasets"
J = "/api/v1/jobs"


def make_project(client, actor, name="Proj"):
    r = client.post(P, json={"organization_id": actor.org_id, "name": name}, headers=actor.headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def upload(client, actor, project_id, content=SAMPLE_CSV, filename="sales.csv", name=None):
    data = {"name": name} if name else {}
    return client.post(
        f"{P}/{project_id}/datasets",
        files={"file": (filename, content, "application/octet-stream")},
        data=data,
        headers=actor.headers,
    )


def ready_dataset(client, actor, project_id=None, **kw) -> tuple[str, str]:
    """Uploads and (because jobs run inline in tests) returns once ingestion has finished."""
    project_id = project_id or make_project(client, actor)
    r = upload(client, actor, project_id, **kw)
    assert r.status_code == 202, r.text
    dataset_id = r.json()["dataset"]["id"]
    job = client.get(f"{J}/{r.json()['job']['id']}", headers=actor.headers).json()
    assert job["status"] == "succeeded", job
    return project_id, dataset_id


def clean(client, actor, dataset_id, operations, **extra) -> dict[str, Any]:
    r = client.post(
        f"{D}/{dataset_id}/cleaning-jobs",
        json={"operations": operations, **extra},
        headers=actor.headers,
    )
    assert r.status_code == 202, r.text
    return client.get(f"{J}/{r.json()['id']}", headers=actor.headers).json()


def xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()
