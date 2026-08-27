"""The treasure bag is the ledger, not the browser.

The Rewards screen read stars out of `sessionStorage` and listed whatever
strings `child["rewards"]` happened to hold, so the badge shelf that
`data/rewards.json` had always described was never shown and a star count went
stale the moment a lesson finished on another device. These tests pin the two
things that fixed it: the shelf is served whole, and every badge on it is
derived from the child's own ledger rather than stored beside it.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def make_child(client: TestClient, email: str) -> str:
    auth = client.post("/auth/register", json={"name": "P", "email": email, "password": "demo1234"})
    token = auth.json()["session_token"]
    child = client.post(
        "/children",
        json={
            "session_token": token,
            "name": "Mira",
            "birth_year": date.today().year - 2,
            "birth_month": date.today().month,
            "preferred_language": "English",
        },
    )
    return child.json()["child_id"]


def shelf(client: TestClient, child_id: str) -> dict:
    body = client.get(f"/progress/{child_id}/rewards").json()
    return {badge["badge_id"]: badge for badge in body["badges"]}


def test_a_new_child_is_served_the_whole_shelf_with_nothing_earned(client: TestClient):
    child_id = make_child(client, "shelf-new@example.com")
    badges = shelf(client, child_id)
    assert badges, "the unearned badges must be served too, or the screen has nothing to show"
    assert not any(badge["earned"] for badge in badges.values())
    # An unearned badge says what is left, so the screen can be kind about it.
    assert badges["first_star"]["progress_hint"]


def test_stars_earn_their_milestones_and_no_others(client: TestClient):
    child_id = make_child(client, "shelf-stars@example.com")
    client.post(f"/dev/seed/{child_id}")
    body = client.get(f"/progress/{child_id}/rewards").json()
    badges = {badge["badge_id"]: badge for badge in body["badges"]}

    assert body["stars"] > 0
    assert badges["first_star"]["earned"] is True
    assert badges["first_star"]["progress_hint"] is None
    # Derived, not stored: every star milestone agrees with the star count, so a
    # badge can never be handed over by anything but the ledger.
    for badge_id, threshold in (("ten_stars", 10), ("twenty_five_stars", 25), ("fifty_stars", 50)):
        assert badges[badge_id]["earned"] is (body["stars"] >= threshold)


def test_finishing_every_world_earns_the_traveller_badge(client: TestClient):
    child_id = make_child(client, "shelf-done@example.com")
    before = shelf(client, child_id)["all_paths_complete"]
    assert before["earned"] is False
    client.post(f"/dev/seed/{child_id}")
    assert shelf(client, child_id)["all_paths_complete"]["earned"] is True
