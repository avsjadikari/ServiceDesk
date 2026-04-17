import pytest
from app.models import Article, User


class TestKnowledgeBase:
    """Test knowledge base functionality"""

    def test_kb_index_page_loads(self, client, app, db, admin_user):
        """Test KB index page loads (requires login because anonymous user check)"""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            response = client.get("/knowledge")
            assert response.status_code == 200

    def test_create_article_as_agent(self, client, app, db, admin_user):
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
            article_id = article.id

            response = client.post(
                f"/knowledge/{article_id}/edit",
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

            updated = db.session.get(Article, article_id)
            assert updated.title == "Updated Title"

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
            article_id = article.id

            client.get(f"/knowledge/{article_id}")

            db.session.expire_all()
            updated = db.session.get(Article, article_id)
            assert updated.view_count == 1
