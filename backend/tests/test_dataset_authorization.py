"""Access-control boundaries for datasets, versions, exports and jobs."""

import uuid

import pytest

from tests.helpers import SAMPLE_CSV, D, J, P, clean, make_project, ready_dataset, upload

ORGS = "/api/v1/organizations"
CLEAN_BODY = {"operations": [{"op": "drop_duplicates"}]}


def _join(client, owner, who, role):
    r = client.post(
        f"{ORGS}/{owner.org_id}/members",
        json={"email": who.email, "role": role},
        headers=owner.headers,
    )
    assert r.status_code == 201, r.text


@pytest.fixture
def world(client, make_actor):
    """Ana owns an org with a ready dataset; Bob is an outsider with their own org."""
    ana, bob = make_actor("Ana"), make_actor("Bob")
    pid, did = ready_dataset(client, ana)
    job_id = client.get(f"{D}/{did}/jobs", headers=ana.headers).json()[0]["id"]
    return {"ana": ana, "bob": bob, "pid": pid, "did": did, "job": job_id}


def _all_calls(client, w):
    """Every dataset/job route, as (name, callable(headers) -> response)."""
    pid, did, job = w["pid"], w["did"], w["job"]
    f = ("x.csv", SAMPLE_CSV, "text/csv")
    return {
        "list": lambda h: client.get(f"{P}/{pid}/datasets", headers=h),
        "upload": lambda h: client.post(
            f"{P}/{pid}/datasets", files={"file": f}, data={"name": "n"}, headers=h
        ),
        "get": lambda h: client.get(f"{D}/{did}", headers=h),
        "preview": lambda h: client.get(f"{D}/{did}/preview", headers=h),
        "profile_get": lambda h: client.get(f"{D}/{did}/profile", headers=h),
        "profile_post": lambda h: client.post(f"{D}/{did}/profile", json={}, headers=h),
        "clean": lambda h: client.post(f"{D}/{did}/cleaning-jobs", json=CLEAN_BODY, headers=h),
        "export": lambda h: client.get(f"{D}/{did}/export", headers=h),
        "jobs": lambda h: client.get(f"{D}/{did}/jobs", headers=h),
        "job_get": lambda h: client.get(f"{J}/{job}", headers=h),
        "job_cancel": lambda h: client.post(f"{J}/{job}/cancel", headers=h),
        "delete": lambda h: client.delete(f"{D}/{did}", headers=h),
    }


def test_anonymous_requests_are_rejected_everywhere(client, world):
    for name, call in _all_calls(client, world).items():
        assert call({}).status_code == 401, name


def test_outsider_gets_404_on_every_route_and_changes_nothing(client, world):
    bob = world["bob"]
    for name, call in _all_calls(client, world).items():
        r = call(bob.headers)
        assert r.status_code == 404, (name, r.status_code, r.text)
    ds = client.get(f"{D}/{world['did']}", headers=world["ana"].headers).json()
    assert ds["status"] == "ready" and len(ds["versions"]) == 1  # nothing was altered or deleted


def test_foreign_and_missing_ids_look_identical(client, world):
    bob = world["bob"]
    ghost = str(uuid.uuid4())
    foreign = client.get(f"{D}/{world['did']}", headers=bob.headers)
    missing = client.get(f"{D}/{ghost}", headers=bob.headers)
    assert foreign.status_code == missing.status_code == 404 and foreign.json() == missing.json()
    foreign_job = client.get(f"{J}/{world['job']}", headers=bob.headers)
    missing_job = client.get(f"{J}/{ghost}", headers=bob.headers)
    assert foreign_job.status_code == missing_job.status_code == 404
    assert foreign_job.json() == missing_job.json()


def test_viewer_can_read_everything_but_change_nothing(client, make_actor, world):
    vic = make_actor("Vic")
    _join(client, world["ana"], vic, "viewer")
    calls = _all_calls(client, world)
    for name in ("list", "get", "preview", "profile_get", "export", "jobs", "job_get"):
        assert calls[name](vic.headers).status_code == 200, name
    for name in ("upload", "profile_post", "clean", "job_cancel", "delete"):
        assert calls[name](vic.headers).status_code == 403, name
    assert (
        len(client.get(f"{D}/{world['did']}", headers=world["ana"].headers).json()["versions"]) == 1
    )


def test_member_can_upload_and_clean_but_not_delete(client, make_actor, world):
    mia = make_actor("Mia")
    _join(client, world["ana"], mia, "member")
    calls = _all_calls(client, world)
    assert calls["upload"](mia.headers).status_code == 202
    assert calls["clean"](mia.headers).status_code == 202
    assert calls["profile_post"](mia.headers).status_code == 202
    assert calls["delete"](mia.headers).status_code == 403


def test_admin_can_delete(client, make_actor, world):
    adm = make_actor("Adm")
    _join(client, world["ana"], adm, "admin")
    assert _all_calls(client, world)["delete"](adm.headers).status_code == 204


def test_same_dataset_name_in_two_orgs_stays_isolated(client, make_actor):
    """Two orgs, same dataset names: each user only ever sees their own."""
    ana, bob = make_actor("Ana"), make_actor("Bob")
    _, a_ds = ready_dataset(client, ana, name="shared-name")
    _, b_ds = ready_dataset(client, bob, name="shared-name")
    assert a_ds != b_ds
    assert client.get(f"{D}/{b_ds}", headers=ana.headers).status_code == 404
    assert client.get(f"{D}/{a_ds}", headers=bob.headers).status_code == 404


def test_job_lookup_cannot_cross_organizations_even_with_valid_dataset_id(client, make_actor):
    ana, bob = make_actor("Ana"), make_actor("Bob")
    pid, did = ready_dataset(client, ana)
    job = clean(client, ana, did, CLEAN_BODY["operations"])
    assert client.get(f"{J}/{job['id']}", headers=bob.headers).status_code == 404
    assert client.get(f"{D}/{did}/jobs", headers=bob.headers).status_code == 404


def test_project_listing_shows_only_own_datasets(client, make_actor):
    ana, bob = make_actor("Ana"), make_actor("Bob")
    ready_dataset(client, ana)
    bob_pid = make_project(client, bob)
    upload(client, bob, bob_pid, name="bobs")
    names = [
        d["name"]
        for d in client.get(f"{P}/{bob_pid}/datasets", headers=bob.headers).json()["items"]
    ]
    assert names == ["bobs"]


def test_expensive_requests_are_rate_limited_per_user(client, make_actor, limits, world):
    limits(job_rate_limit_attempts=3, job_rate_limit_window_seconds=60)
    ana, did = world["ana"], world["did"]
    codes = [
        client.post(f"{D}/{did}/cleaning-jobs", json=CLEAN_BODY, headers=ana.headers).status_code
        for _ in range(5)
    ]
    # the fixture's own upload already used one of the 3 allowed requests
    assert codes == [202, 202, 429, 429, 429]
    # another user's allowance is separate
    assert (
        client.post(f"{D}/{did}/profile", json={}, headers=world["bob"].headers).status_code == 404
    )
