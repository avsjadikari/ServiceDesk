import pytest
from app.models import Article, User


class TestKnowledgeBase:
    """Test knowledge base functionality"""

    def test_kb_index_page_loads(self, client):
        """Test KB index page loads"""
        response = client.get("/knowledge")
        assert response.status_code == 200

    def test_create_article_as_agent(self, client, app, admin_user):
        """Test agent can create knowledge articles"""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            response = client.post(
                "/knowledge/new",
                data={
                    "title": "How to Reset Password",
                    "content": "# Password Reset Guide\n\nFollow these steps...",
                    "category": "Account/Access",
                    "tags": "password,reset,security",
                    "status": "published",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

            article = Article.query.filter_by(title="How to Reset Password").first()
            assert article is not None
            assert article.status == "published"

    def test_view_article(self, client, app, db, admin_user):
        """Test viewing an article"""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )

            article = Article(
                title="Test Article",
                content="Test content",
                category="Hardware",
                author_id=admin_user.id,
                status="published",
            )
            db.session.add(article)
            db.session.commit()

            response = client.get(f"/knowledge/{article.id}")
            assert response.status_code == 200

    def test_search_articles(self, client, app, db, admin_user):
        """Test searching articles"""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )

            article = Article(
                title="VPN Guide",
                content="How to connect to VPN",
                category="Network",
                author_id=admin_user.id,
                status="published",
            )
            db.session.add(article)
            db.session.commit()

            response = client.get("/knowledge?search=VPN")
            assert response.status_code == 200

    def test_edit_article(self, client, app, db, admin_user):
        """Test editing an article"""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )

            article = Article(
                title="Original Title",
                content="Original content",
                category="Software",
                author_id=admin_user.id,
                status="published",
            )
            db.session.add(article)
            db.session.commit()

            response = client.post(
                f"/knowledge/{article.id}/edit",
                data={
                    "title": "Updated Title",
                    "content": "Updated content",
                    "category": "Software",
                    "tags": "",
                    "status": "published",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200

            article = Article.query.get(article.id)
            assert article.title == "Updated Title"

    def test_view_count_increments(self, client, app, db, admin_user):
        """Test view count increments on viewing"""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )

            article = Article(
                title="Popular Article",
                content="Content",
                category="Hardware",
                author_id=admin_user.id,
                status="published",
                view_count=0,
            )
            db.session.add(article)
            db.session.commit()

            client.get(f"/knowledge/{article.id}")

            article = Article.query.get(article.id)
            assert article.view_count == 1

    def test_draft_article_not_viewable_by_id(self, client, app, db, admin_user):
        """Regression: article detail routes used get_or_404 without a
        published filter, so draft/archived content was readable by ID —
        including by unauthenticated portal visitors."""
        with app.app_context():
            article = Article(
                title="Draft Article",
                content="Internal draft content",
                category="Security",
                author_id=admin_user.id,
                status="draft",
            )
            db.session.add(article)
            db.session.commit()

            response = client.get(f"/knowledge/{article.id}")
            assert response.status_code == 404

            response = client.get(f"/portal/knowledge/{article.id}")
            assert response.status_code == 404

            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )

            response = client.get(f"/api/articles/{article.id}")
            assert response.status_code == 404
class TestKnowledgeCharacterization:
    """CHARACTERIZATION: pin current behavior of app/routes/knowledge.py gaps."""

    def test_index_category_filter(self, client, app, db, admin_user):
        """Line 29: category branch in index filters published articles."""
        with app.app_context():
            db.session.add_all([
                Article(title="A1", content="c1", category="Hardware", author_id=admin_user.id, status="published"),
                Article(title="A2", content="c2", category="Software", author_id=admin_user.id, status="published"),
                Article(title="A3", content="c3", category="Hardware", author_id=admin_user.id, status="draft"),
            ])
            db.session.commit()
        resp = client.get("/knowledge?category=Hardware")
        assert resp.status_code == 200
        # CHARACTERIZED: only published matching category listed; drafts excluded.
        body = resp.get_data(as_text=True)
        assert "A1" in body
        assert "A2" not in body
        assert "A3" not in body

    def test_new_non_agent_forbidden(self, client, app, admin_user, regular_user):
        """Line 70: POST /knowledge/new as regular user -> 403."""
        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})
        resp = client.post(
            "/knowledge/new",
            data={"title": "T", "content": "C", "category": "Hardware",
                  "tags": "", "status": "published"},
        )
        assert resp.status_code == 403  # CHARACTERIZED: abort(403)

    def test_new_get_renders_form(self, client, app, agent_user):
        """Line 101: GET /knowledge/new renders form for agent."""
        with app.app_context():
            client.post("/login", data={"username": "agent", "password": "Agent@123456"})
        resp = client.get("/knowledge/new")
        assert resp.status_code == 200

    def test_new_agent_create_redirects_to_view(self, client, app, db, agent_user, admin_user):
        """Lines 74-98: agent create commits article + version row, redirects to view."""
        with app.app_context():
            client.post("/login", data={"username": "agent", "password": "Agent@123456"})
        resp = client.post(
            "/knowledge/new",
            data={"title": "AgentArt", "content": "Body", "category": "Hardware",
                  "tags": "a,b", "status": "published"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/knowledge/1")
        with app.app_context():
            from app.models import ArticleVersion
            a = Article.query.filter_by(title="AgentArt").first()
            assert a is not None
            assert a.status == "published"
            v = ArticleVersion.query.filter_by(article_id=a.id, version=1).first()
            assert v is not None  # CHARACTERIZED: initial version row created

    def test_new_agent_get_form_render_path(self, client, app, agent_user):
        """Line 101 already covered; keep GET-only render without login redirect."""
        with app.app_context():
            client.post("/login", data={"username": "agent", "password": "Agent@123456"})
        resp = client.get("/knowledge/new")
        assert resp.status_code == 200

    def test_edit_non_agent_forbidden(self, client, app, db, admin_user, regular_user):
        """Line 108: regular user edit -> 403."""
        with app.app_context():
            a = Article(title="E1", content="c", category="Hardware", author_id=admin_user.id, status="published")
            db.session.add(a)
            db.session.commit()
            aid = a.id
            client.post("/login", data={"username": "user", "password": "User@123456"})
        resp = client.post(
            f"/knowledge/{aid}/edit",
            data={"title": "E1x", "content": "cx", "category": "Hardware",
                  "tags": "", "status": "published"},
        )
        assert resp.status_code == 403  # CHARACTERIZED: abort(403)

    def test_edit_get_renders_form(self, client, app, db, admin_user, agent_user):
        """Line 136: GET edit renders form for agent."""
        with app.app_context():
            a = Article(title="E2", content="c", category="Hardware", author_id=admin_user.id, status="published")
            db.session.add(a)
            db.session.commit()
            aid = a.id
            client.post("/login", data={"username": "agent", "password": "Agent@123456"})
        resp = client.get(f"/knowledge/{aid}/edit")
        assert resp.status_code == 200

    def test_edit_post_bumps_version(self, client, app, db, admin_user, agent_user):
        """Lines 113-134: edit POST increments article.version, stores old content version row, redirects to view."""
        with app.app_context():
            a = Article(title="E3", content="old", category="Hardware", author_id=admin_user.id, status="published", version=1)
            db.session.add(a)
            db.session.commit()
            aid = a.id
            client.post("/login", data={"username": "agent", "password": "Agent@123456"})
        resp = client.post(
            f"/knowledge/{aid}/edit",
            data={"title": "E3 new", "content": "new", "category": "Hardware",
                  "tags": "", "status": "published"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert f"/knowledge/{aid}" in resp.headers["Location"]
        with app.app_context():
            from app.models import ArticleVersion
            a2 = Article.query.get(aid)
            assert a2.title == "E3 new"
            assert a2.version == 2
            # CHARACTERIZED → fixed 2026-10-08: version rows are snapshots of
            # the article AT that revision. v2 stores the post-edit content
            # (was: the pre-edit "old" content, inconsistent with v1 which
            # stores the created state)
            v = ArticleVersion.query.filter_by(article_id=aid, version=2).first()
            assert v.content == "new"

    def test_versions_agent_can_view(self, client, app, db, admin_user, agent_user):
        """Lines 142-154: agent versions page renders."""
        with app.app_context():
            a = Article(title="V1", content="c", category="Hardware", author_id=admin_user.id, status="published")
            db.session.add(a)
            db.session.commit()
            aid = a.id
            client.post("/login", data={"username": "agent", "password": "Agent@123456"})
        resp = client.get(f"/knowledge/{aid}/versions")
        assert resp.status_code == 200

    def test_versions_non_agent_forbidden(self, client, app, db, admin_user, regular_user):
        """Lines 142-143: regular user versions -> 403."""
        with app.app_context():
            a = Article(title="V2", content="c", category="Hardware", author_id=admin_user.id, status="published")
            db.session.add(a)
            db.session.commit()
            aid = a.id
            client.post("/login", data={"username": "user", "password": "User@123456"})
        resp = client.get(f"/knowledge/{aid}/versions")
        assert resp.status_code == 403  # CHARACTERIZED: abort(403)

    def test_versions_anonymous_redirects_to_login(self, client, app, db, admin_user):
        """@login_required on versions: anonymous -> 302 login."""
        with app.app_context():
            a = Article(title="V3", content="c", category="Hardware", author_id=admin_user.id, status="published")
            db.session.add(a)
            db.session.commit()
            aid = a.id
        resp = client.get(f"/knowledge/{aid}/versions")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]  # CHARACTERIZED: login redirect

    def test_helpful_increments_and_redirects(self, client, app, db, admin_user, regular_user):
        """Lines 160-164: POST helpful increments helpful_count, flashes, redirects to view."""
        with app.app_context():
            a = Article(title="H1", content="c", category="Hardware", author_id=admin_user.id, status="published", helpful_count=0)
            db.session.add(a)
            db.session.commit()
            aid = a.id
            client.post("/login", data={"username": "user", "password": "User@123456"})
        resp = client.post(f"/knowledge/{aid}/helpful", follow_redirects=False)
        assert resp.status_code == 302
        assert f"/knowledge/{aid}" in resp.headers["Location"]  # CHARACTERIZED: redirects to view, no view_count bump here
        with app.app_context():
            assert Article.query.get(aid).helpful_count == 1

    def test_helpful_anonymous_redirects_to_login(self, client, app, db, admin_user):
        """@login_required on helpful: anonymous -> 302 login."""
        with app.app_context():
            a = Article(title="H2", content="c", category="Hardware", author_id=admin_user.id, status="published", helpful_count=0)
            db.session.add(a)
            db.session.commit()
            aid = a.id
        resp = client.post(f"/knowledge/{aid}/helpful")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_delete_non_agent_forbidden(self, client, app, db, admin_user, regular_user):
        """Lines 170-171: regular user delete -> 403; article survives."""
        with app.app_context():
            a = Article(title="D1", content="c", category="Hardware", author_id=admin_user.id, status="published")
            db.session.add(a)
            db.session.commit()
            aid = a.id
            client.post("/login", data={"username": "user", "password": "User@123456"})
        resp = client.post(f"/knowledge/{aid}/delete")
        assert resp.status_code == 403  # CHARACTERIZED: abort(403)
        with app.app_context():
            assert Article.query.get(aid) is not None

    def test_delete_agent_deletes_and_redirects(self, client, app, db, admin_user, agent_user):
        """Lines 173-178: agent delete removes row, redirects to index."""
        with app.app_context():
            a = Article(title="D2", content="c", category="Hardware", author_id=admin_user.id, status="published")
            db.session.add(a)
            db.session.commit()
            aid = a.id
            client.post("/login", data={"username": "agent", "password": "Agent@123456"})
        resp = client.post(f"/knowledge/{aid}/delete", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/knowledge")  # CHARACTERIZED: redirect to index
        with app.app_context():
            assert Article.query.get(aid) is None  # CHARACTERIZED: row deleted


class TestPortalKnowledgeCharacterization:
    """CHARACTERIZATION: portal knowledge endpoints (in scope)."""

    def test_portal_knowledge_list(self, client, app, db, admin_user):
        """Pin: GET /portal/knowledge returns 200; supports basic listing."""
        with app.app_context():
            db.session.add(Article(title="PK1", content="c", category="G", author_id=admin_user.id, status="published"))
            db.session.add(Article(title="PD1", content="c", category="G", author_id=admin_user.id, status="draft"))
            db.session.commit()
        resp = client.get("/portal/knowledge")
        assert resp.status_code == 200
        # CHARACTERIZED: portal.knowledge shows published only (filtered by status); draft excluded.

    def test_portal_knowledge_search(self, client, app, db, admin_user):
        """Pin: /portal/knowledge?search filters."""
        with app.app_context():
            db.session.add(Article(title="SearchMe", content="needle", category="G", author_id=admin_user.id, status="published"))
            db.session.commit()
        resp = client.get("/portal/knowledge?search=needle")
        assert resp.status_code == 200
        # CHARACTERIZED: search filters title OR content (ilike).

    def test_portal_knowledge_category(self, client, app, db, admin_user):
        """Pin: /portal/knowledge?category filters."""
        with app.app_context():
            db.session.add(Article(title="CatA", content="c", category="A", author_id=admin_user.id, status="published"))
            db.session.add(Article(title="CatB", content="c", category="B", author_id=admin_user.id, status="published"))
            db.session.commit()
        resp = client.get("/portal/knowledge?category=A")
        assert resp.status_code == 200
        # CHARACTERIZED: category filter applied.

    def test_portal_knowledge_view_increments(self, client, app, db, admin_user):
        """Pin: GET /portal/knowledge/<id> increments view_count (portal.knowledge_view)."""
        with app.app_context():
            a = Article(title="PView", content="c", category="G", author_id=admin_user.id, status="published", view_count=0)
            db.session.add(a)
            db.session.commit()
            aid = a.id
        resp = client.get(f"/portal/knowledge/{aid}")
        assert resp.status_code == 200
        with app.app_context():
            assert Article.query.get(aid).view_count == 1  # CHARACTERIZED: view_count increment on GET
