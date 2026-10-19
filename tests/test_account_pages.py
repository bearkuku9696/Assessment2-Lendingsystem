import pytest


@pytest.mark.parametrize("path,title", [("/login", "Sign in"), ("/register", "Create an account")])
def test_account_pages(auth, path, title):
    client, _ = auth
    response = client.get(path, params={"next": "/equipment/1/book"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert f"<h1>{title}</h1>" in response.text
    assert 'data-next="/equipment/1/book"' in response.text
    assert 'name="email"' in response.text
    assert 'name="password"' in response.text
    assert "width=device-width" in response.text
    if path == "/register":
        assert 'name="name"' in response.text
        assert 'minlength="8"' in response.text


@pytest.mark.parametrize("path", ["/login", "/register"])
@pytest.mark.parametrize("destination", ["https://example.org", "//example.org", "/\\example.org", "/admin", "/<script>"])
def test_account_pages_reject_unsafe_redirects(auth, path, destination):
    client, _ = auth
    assert client.get(path, params={"next": destination}).status_code == 422


def test_registration_confirmation_and_catalogue_links(auth):
    client, _ = auth
    assert "Account created. Sign in to continue." in client.get("/login?registered=true").text
    catalogue = client.get("/").text
    assert 'href="/login"' in catalogue
    assert 'href="/register"' in catalogue


@pytest.mark.parametrize("path,content_type", [
    ("/static/styles.css", "text/css"),
    ("/static/authentication.js", "javascript"),
    ("/static/session.js", "javascript"),
    ("/static/booking.js", "javascript"),
    ("/static/admin.js", "javascript"),
])
def test_page_assets_are_served(auth, path, content_type):
    client, _ = auth
    response = client.get(path)
    assert response.status_code == 200
    assert content_type in response.headers["content-type"]
    assert response.text.strip()
