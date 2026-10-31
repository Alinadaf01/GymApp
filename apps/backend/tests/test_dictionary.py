def test_dictionary_requires_auth(client):
    assert client.get("/api/exercises/dictionary").status_code == 401


def test_dictionary_crud_and_conflicts(auth_client):
    r = auth_client.post("/api/exercises/dictionary",
                         json={"canonical_name": "لت سيم‌کش", "aliases": ["لت", "لت", " زیربغل سیم کش "]})
    assert r.status_code == 201
    e = r.json()
    assert e["canonical_name"] == "لت سیم‌کش" and e["aliases"] == ["لت", "زیربغل سیم کش"]
    # same spoken form (spaces/ZWNJ ignored) for another exercise -> conflict
    r = auth_client.post("/api/exercises/dictionary", json={"canonical_name": "زیربغل سیم‌کش"})
    assert r.status_code == 409
    r = auth_client.put(f"/api/exercises/dictionary/{e['id']}",
                        json={"canonical_name": "لت سیم‌کش", "aliases": ["لت پول"]})
    assert r.json()["aliases"] == ["لت پول"]
    assert [x["canonical_name"] for x in auth_client.get("/api/exercises/dictionary?q=پول").json()] == ["لت سیم‌کش"]
    assert auth_client.delete(f"/api/exercises/dictionary/{e['id']}").status_code == 204
    assert auth_client.get("/api/exercises/dictionary").json() == []


def test_dictionary_route_not_shadowed_by_exercise_routes(auth_client):
    # PUT /api/exercises/{id} exists too; dictionary paths must still resolve
    assert auth_client.get("/api/exercises/dictionary").status_code == 200


def test_dictionary_is_used_by_parser(auth_client):
    from app.database import SessionLocal
    from app.parsers.service import load_dictionary, parse_text

    auth_client.post("/api/exercises/dictionary", json={"canonical_name": "لت سیم‌کش", "aliases": ["لت پول"]})
    with SessionLocal() as db:
        payload = parse_text("لت پول سه ست دوازده تایی", "workout", load_dictionary(db))
    (ex,) = payload["exercises"]
    assert ex["name"] == "لت سیم‌کش" and ex["matched"] is True
