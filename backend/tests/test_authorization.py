"""Access-control boundaries. These tests are the point of Phase 2A."""

from sqlalchemy import select

from app.models import AuditLog

P = "/api/v1/projects"
ORGS = "/api/v1/organizations"


def _add_member(client, owner, org_id, who, role):
    return client.post(
        f"{ORGS}/{org_id}/members", json={"email": who.email, "role": role}, headers=owner.headers
    )


def _project(client, actor, org_id, name="Alpha", **extra):
    return client.post(
        P, json={"organization_id": org_id, "name": name, **extra}, headers=actor.headers
    )


# ---------- cross-organization isolation (IDOR) ----------


def test_users_only_see_their_own_organizations(client, make_actor):
    ana, bob = make_actor("Ana"), make_actor("Bob")
    ids = lambda a: {o["id"] for o in client.get(ORGS, headers=a.headers).json()}  # noqa: E731
    assert ids(ana) == {ana.org_id} and ids(bob) == {bob.org_id}


def test_non_member_cannot_read_or_change_another_orgs_project(client, make_actor):
    ana, bob = make_actor("Ana"), make_actor("Bob")
    pid = _project(client, ana, ana.org_id).json()["id"]

    assert client.get(f"{P}/{pid}", headers=bob.headers).status_code == 404
    assert client.patch(f"{P}/{pid}", json={"name": "x"}, headers=bob.headers).status_code == 404
    assert client.delete(f"{P}/{pid}", headers=bob.headers).status_code == 404
    # Ana's project is untouched
    assert client.get(f"{P}/{pid}", headers=ana.headers).json()["name"] == "Alpha"


def test_missing_and_foreign_projects_are_indistinguishable(client, make_actor):
    ana, bob = make_actor("Ana"), make_actor("Bob")
    pid = _project(client, ana, ana.org_id).json()["id"]
    foreign = client.get(f"{P}/{pid}", headers=bob.headers)
    missing = client.get(f"{P}/00000000-0000-0000-0000-000000000000", headers=bob.headers)
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()


def test_cannot_create_project_in_someone_elses_org(client, make_actor):
    ana, bob = make_actor("Ana"), make_actor("Bob")
    assert _project(client, bob, ana.org_id).status_code == 404


def test_non_member_cannot_list_or_add_members(client, make_actor):
    ana, bob = make_actor("Ana"), make_actor("Bob")
    assert client.get(f"{ORGS}/{ana.org_id}/members", headers=bob.headers).status_code == 404
    assert _add_member(client, bob, ana.org_id, bob, "owner").status_code == 404


def test_project_list_never_leaks_other_orgs_and_filter_is_checked(client, make_actor):
    ana, bob = make_actor("Ana"), make_actor("Bob")
    _project(client, ana, ana.org_id, "Secret")
    _project(client, bob, bob.org_id, "Mine")
    names = [p["name"] for p in client.get(P, headers=bob.headers).json()["items"]]
    assert names == ["Mine"]
    assert (
        client.get(P, params={"organization_id": ana.org_id}, headers=bob.headers).status_code
        == 404
    )


def test_unauthenticated_requests_are_rejected_everywhere(client, make_actor):
    ana = make_actor("Ana")
    pid = _project(client, ana, ana.org_id).json()["id"]
    for method, url in [
        ("get", ORGS),
        ("post", ORGS),
        ("get", P),
        ("post", P),
        ("get", f"{P}/{pid}"),
        ("patch", f"{P}/{pid}"),
        ("delete", f"{P}/{pid}"),
        ("get", f"{ORGS}/{ana.org_id}/members"),
        ("post", f"{ORGS}/{ana.org_id}/members"),
    ]:
        assert getattr(client, method)(url).status_code == 401, (method, url)


# ---------- role matrix ----------


def test_viewer_can_read_but_not_write(client, make_actor):
    ana, vic = make_actor("Ana"), make_actor("Vic")
    assert _add_member(client, ana, ana.org_id, vic, "viewer").status_code == 201
    pid = _project(client, ana, ana.org_id).json()["id"]

    assert client.get(f"{P}/{pid}", headers=vic.headers).status_code == 200
    assert (
        client.get(P, params={"organization_id": ana.org_id}, headers=vic.headers).json()["total"]
        == 1
    )
    assert _project(client, vic, ana.org_id, "Nope").status_code == 403
    assert client.patch(f"{P}/{pid}", json={"name": "x"}, headers=vic.headers).status_code == 403
    assert client.delete(f"{P}/{pid}", headers=vic.headers).status_code == 403


def test_member_can_create_and_edit_but_not_delete_or_manage_members(client, make_actor):
    ana, mia, new = make_actor("Ana"), make_actor("Mia"), make_actor("New")
    _add_member(client, ana, ana.org_id, mia, "member")
    pid = _project(client, mia, ana.org_id, "ByMia").json()["id"]

    assert (
        client.patch(f"{P}/{pid}", json={"description": "d"}, headers=mia.headers).status_code
        == 200
    )
    assert client.delete(f"{P}/{pid}", headers=mia.headers).status_code == 403
    assert _add_member(client, mia, ana.org_id, new, "viewer").status_code == 403


def test_admin_can_delete_and_add_members_but_not_grant_admin_or_owner(client, make_actor):
    ana, adm, x, y, z = (make_actor(n) for n in ("Ana", "Adm", "X", "Y", "Z"))
    _add_member(client, ana, ana.org_id, adm, "admin")
    pid = _project(client, ana, ana.org_id).json()["id"]

    assert _add_member(client, adm, ana.org_id, x, "member").status_code == 201
    assert _add_member(client, adm, ana.org_id, y, "admin").status_code == 403
    assert _add_member(client, adm, ana.org_id, z, "owner").status_code == 403
    assert client.delete(f"{P}/{pid}", headers=adm.headers).status_code == 204


def test_owner_can_grant_any_role(client, make_actor):
    ana, adm, own = make_actor("Ana"), make_actor("Adm"), make_actor("Own")
    assert _add_member(client, ana, ana.org_id, adm, "admin").status_code == 201
    assert _add_member(client, ana, ana.org_id, own, "owner").status_code == 201


def test_adding_existing_member_or_unknown_user(client, make_actor):
    ana, bob = make_actor("Ana"), make_actor("Bob")
    assert _add_member(client, ana, ana.org_id, bob, "member").status_code == 201
    assert _add_member(client, ana, ana.org_id, bob, "viewer").status_code == 409
    ghost = type("G", (), {"email": "ghost@example.com"})
    assert _add_member(client, ana, ana.org_id, ghost, "member").status_code == 404


def test_invalid_role_is_rejected(client, make_actor):
    ana, bob = make_actor("Ana"), make_actor("Bob")
    assert _add_member(client, ana, ana.org_id, bob, "superuser").status_code == 422


def test_members_listing_shows_roles(client, make_actor):
    ana, bob = make_actor("Ana"), make_actor("Bob")
    _add_member(client, ana, ana.org_id, bob, "viewer")
    rows = client.get(f"{ORGS}/{ana.org_id}/members", headers=bob.headers).json()
    assert {(m["email"], m["role"]) for m in rows} == {
        ("ana@example.com", "owner"),
        ("bob@example.com", "viewer"),
    }


# ---------- project behaviour ----------


def test_create_org_makes_caller_owner(client, make_actor):
    ana = make_actor("Ana")
    r = client.post(ORGS, json={"name": "Acme Analytics"}, headers=ana.headers)
    assert r.status_code == 201 and r.json()["role"] == "owner"
    assert r.json()["slug"].startswith("acme-analytics-")


def test_project_name_unique_per_org_only(client, make_actor):
    ana = make_actor("Ana")
    other = client.post(ORGS, json={"name": "Other"}, headers=ana.headers).json()["id"]
    assert _project(client, ana, ana.org_id, "Dup").status_code == 201
    assert _project(client, ana, ana.org_id, "Dup").status_code == 409
    assert _project(client, ana, other, "Dup").status_code == 201


def test_project_validation(client, make_actor):
    ana = make_actor("Ana")
    assert _project(client, ana, ana.org_id, "   ").status_code == 422
    assert _project(client, ana, ana.org_id, "x" * 121).status_code == 422
    assert _project(client, ana, ana.org_id, "ok", description="d" * 2001).status_code == 422
    assert client.get(f"{P}/not-a-uuid", headers=ana.headers).status_code == 422


def test_patch_updates_only_given_fields_and_can_clear_description(client, make_actor):
    ana = make_actor("Ana")
    pid = _project(client, ana, ana.org_id, "Alpha", description="old").json()["id"]
    r = client.patch(f"{P}/{pid}", json={"name": "Beta"}, headers=ana.headers).json()
    assert r["name"] == "Beta" and r["description"] == "old"
    r = client.patch(f"{P}/{pid}", json={"description": None}, headers=ana.headers).json()
    assert r["name"] == "Beta" and r["description"] is None


def test_pagination(client, make_actor):
    ana = make_actor("Ana")
    for i in range(5):
        _project(client, ana, ana.org_id, f"P{i}")
    page = client.get(P, params={"limit": 2, "offset": 2}, headers=ana.headers).json()
    assert page["total"] == 5 and len(page["items"]) == 2 and page["offset"] == 2
    assert client.get(P, params={"limit": 101}, headers=ana.headers).status_code == 422
    assert client.get(P, params={"offset": -1}, headers=ana.headers).status_code == 422


def test_sensitive_actions_are_audited(client, make_actor, db):
    ana, bob = make_actor("Ana"), make_actor("Bob")
    _add_member(client, ana, ana.org_id, bob, "member")
    pid = _project(client, ana, ana.org_id).json()["id"]
    client.patch(f"{P}/{pid}", json={"name": "Renamed"}, headers=ana.headers)
    client.delete(f"{P}/{pid}", headers=ana.headers)
    actions = {a for (a,) in db.execute(select(AuditLog.action)).all()}
    assert {
        "organization.member_add",
        "project.create",
        "project.update",
        "project.delete",
    } <= actions
