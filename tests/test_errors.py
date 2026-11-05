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


def test_api_429_returns_json(client, app):
    from werkzeug.exceptions import TooManyRequests

    @app.route("/api/test-429")
    def trigger_api_429():
        raise TooManyRequests()

    response = client.get("/api/test-429")
    assert response.status_code == 429
    assert response.is_json
    assert "Too many requests" in response.get_json()["error"]


def test_html_429_is_designed(client, app):
    from werkzeug.exceptions import TooManyRequests

    @app.route("/test-429")
    def trigger_web_429():
        raise TooManyRequests()

    response = client.get("/test-429")
    assert response.status_code == 429
    assert b"Too many requests" in response.data
    assert b"<!DOCTYPE html>" in response.data
