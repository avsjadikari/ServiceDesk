from app.i18n import SUPPORTED_LANGUAGES, load_translations, get_translation, _TRANSLATIONS
from flask import g


def test_supported_languages_configured():
    assert "en" in SUPPORTED_LANGUAGES
    assert "es" in SUPPORTED_LANGUAGES
    assert "fr" in SUPPORTED_LANGUAGES
    assert "de" in SUPPORTED_LANGUAGES
    assert "ja" in SUPPORTED_LANGUAGES
    assert "ar" in SUPPORTED_LANGUAGES
    assert "si" in SUPPORTED_LANGUAGES

    # Verify Arabic RTL
    assert SUPPORTED_LANGUAGES["ar"]["dir"] == "rtl"
    # Verify others LTR
    for lang in ["en", "es", "fr", "de", "ja", "si"]:
        assert SUPPORTED_LANGUAGES[lang]["dir"] == "ltr"


def test_translation_catalogs_loaded(app):
    with app.app_context():
        catalogs = load_translations()
        for lang in ["en", "es", "fr", "de", "ja", "ar", "si"]:
            assert lang in catalogs
            assert len(catalogs[lang]) > 0
            assert "Dashboard" in catalogs[lang]
            assert "Tickets" in catalogs[lang]


def test_translation_lookup_and_fallback(app):
    with app.app_context():
        with app.test_request_context():
            # Test English default
            g.lang = "en"
            assert get_translation("Dashboard") == "Dashboard"
            assert get_translation("Tickets") == "Tickets"

            # Test Spanish
            g.lang = "es"
            assert get_translation("Dashboard") == "Panel de Control"
            assert get_translation("Tickets") == "Tickets"

            # Test French
            g.lang = "fr"
            assert get_translation("Dashboard") == "Tableau de Bord"

            # Test German
            g.lang = "de"
            assert get_translation("Analytics") == "Analysen"
            assert get_translation("Knowledge Base") == "Wissensdatenbank"

            # Test Japanese
            g.lang = "ja"
            assert get_translation("Dashboard") == "ダッシュボード"

            # Test Arabic
            g.lang = "ar"
            assert get_translation("Dashboard") == "لوحة التحكم"

            # Test Sinhala
            g.lang = "si"
            assert get_translation("Dashboard") == "පාලක පුවරුව"

            # Test fallback to English when key missing in specific language
            assert get_translation("NonExistentKey123") == "NonExistentKey123"


def test_set_language_route(client):
    res = client.get("/set-lang/es", follow_redirects=False)
    assert res.status_code == 302
    with client.session_transaction() as sess:
        assert sess.get("lang") == "es"

    # Set Arabic
    res = client.get("/set-lang/ar", follow_redirects=False)
    assert res.status_code == 302
    with client.session_transaction() as sess:
        assert sess.get("lang") == "ar"

    # Invalid language ignored
    client.get("/set-lang/invalid_lang", follow_redirects=False)
    with client.session_transaction() as sess:
        assert sess.get("lang") == "ar"


def test_rtl_rendered_in_html_for_arabic(client, app, admin_user):
    with app.app_context():
        client.post("/login", data={"username": "admin", "password": "Admin@123456"})
        client.get("/set-lang/ar")

        res = client.get("/dashboard")
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert 'lang="ar"' in html
        assert 'dir="rtl"' in html
        assert "لوحة التحكم" in html  # Arabic for Dashboard


def test_sinhala_rendered_in_html(client, app, admin_user):
    with app.app_context():
        client.post("/login", data={"username": "admin", "password": "Admin@123456"})
        client.get("/set-lang/si")

        res = client.get("/dashboard")
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert 'lang="si"' in html
        assert 'dir="ltr"' in html
        assert "පාලක පුවරුව" in html  # Sinhala for Dashboard


def test_japanese_rendered_in_html(client, app, admin_user):
    with app.app_context():
        client.post("/login", data={"username": "admin", "password": "Admin@123456"})
        client.get("/set-lang/ja")

        res = client.get("/dashboard")
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert 'lang="ja"' in html
        assert "ダッシュボード" in html


def test_query_param_language_switch(client):
    res = client.get("/portal?lang=de")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'lang="de"' in html


def test_spanish_content_translated_in_dashboard_and_tickets(client, app, admin_user):
    with app.app_context():
        client.post("/login", data={"username": "admin", "password": "Admin@123456"})
        client.get("/set-lang/es")

        # Check Dashboard page content
        res = client.get("/dashboard")
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert "Total de Tickets" in html
        assert "Tickets Abiertos" in html
        assert "Cumplimiento de SLA" in html

        # Check Tickets page content
        res = client.get("/tickets")
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert "Vista de Lista" in html
        assert "Vista de Tablero" in html
        assert "Nuevo Ticket" in html
        assert "Filtrar" in html


def test_kanban_board_content_translated(client, app, admin_user):
    with app.app_context():
        client.post("/login", data={"username": "admin", "password": "Admin@123456"})
        client.get("/set-lang/ja")

        res = client.get("/tickets/board")
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert "チケットワークフローボード" in html
        assert "新規・トリアージ" in html
        assert "保留・待機中" in html
        assert "解決済み" in html

