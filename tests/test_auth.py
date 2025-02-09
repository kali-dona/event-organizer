"""Test the auth module."""
from flask import url_for
from flask_wtf.csrf import generate_csrf
from app.models import User


def test_register(client):
    """Register a new user."""
    with client:
        client.get(url_for("auth.register"))
        csrf_token = generate_csrf()

    response = client.post(url_for("auth.register"), data={
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "newpassword",
        "confirm_password": "newpassword",
        "first_name": "Test",
        "last_name": "User",
        "csrf_token": csrf_token
    }, follow_redirects=True)
    assert response.status_code == 200
    assert User.query.filter_by(username="newuser").first() is not None
    assert b"You are already registered and logged in." not in response.data


def test_register_existing_username(client, new_user):
    """Register a user with an existing username."""
    with client:
        client.get(url_for("auth.register"))
        csrf_token = generate_csrf()

    response = client.post(url_for("auth.register"), data={
        "username": new_user.username,
        "email": "unique@example.com",
        "password": "password123",
        "confirm_password": "password123",
        "first_name": "Test",
        "last_name": "User",
        "csrf_token": csrf_token
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"This username is already taken." in response.data


def test_register_existing_email(client, new_user):
    """Register a user with an existing email."""
    with client:
        client.get(url_for("auth.register"))
        csrf_token = generate_csrf()

    response = client.post(url_for("auth.register"), data={
        "username": "unique_username",
        "email": new_user.email,
        "password": "password123",
        "confirm_password": "password123",
        "first_name": "Test",
        "last_name": "User",
        "csrf_token": csrf_token
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"This email is already registered." in response.data


def test_login(client, new_user):
    """Login a registered user."""
    response = client.post(url_for("auth.login"), data={
        "username": new_user.username,
        "password": "password123"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"You are already logged in." not in response.data
    assert new_user.is_authenticated


def test_login_invalid_credentials(client):
    """Login with invalid credentials."""
    response = client.post(url_for("auth.login"), data={
        "username": "wronguser",
        "password": "wrongpassword"
    }, follow_redirects=False)

    assert response.status_code == 302


def test_logout(client, new_user):
    """Logout a user."""
    response = client.post(url_for("auth.login"), data={
        "username": new_user.username,
        "password": "password123"
    }, follow_redirects=True)

    assert response.status_code == 200
    response = client.get(url_for("auth.logout"), follow_redirects=True)
    assert response.status_code == 200
