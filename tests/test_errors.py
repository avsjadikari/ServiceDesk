"""Error pages must render the app chrome, not Werkzeug's default page."""


def test_html_404_is_designed(client):
    response = client.get("/definitely-not-a-real-page")
    assert response.status_code == 404
    assert b"page you were looking for" in response.data
    assert b"<!DOCTYPE html>" in response.data


def test_api_404_returns_json(client):
    response = client.get("/api/definitely-not-a-real-endpoint")
    assert response.status_code == 404
    assert response.is_json
    assert "error" in response.get_json()
