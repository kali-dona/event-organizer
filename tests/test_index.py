from flask import url_for, template_rendered
from app.models import User, Event, Notification
from datetime import datetime
from contextlib import contextmanager


@contextmanager
def captured_templates(app):
    recorded = []

    def record(sender, template, context, **extra):
        recorded.append((template, context))

    template_rendered.connect(record, app)
    try:
        yield recorded
    finally:
        template_rendered.disconnect(record, app)


def test_index_route_unauthenticated(client):
    response = client.get(url_for('index.index_route'))
    assert response.status_code == 200
    assert b"Organize It!" in response.data


def test_index_route_authenticated(client, auth):
    auth.login()
    response = client.get(url_for('index.index_route'))
    assert response.status_code == 302
    assert response.location == '/home'


def test_home_route_authenticated_no_events_no_notifications(
        client, auth, db_session):
    auth.login()
    response = client.get(url_for('index.home'))
    assert response.status_code == 200
    assert b"No upcoming events yet." in response.data
    assert b"No past events yet." in response.data
    assert b"You haven't created any events yet." in response.data
    assert b"No new notifications." in response.data


def test_home_route_authenticated_with_events_and_notifications(
        client, auth, db_session):
    auth.login()

    user = db_session.query(User).filter_by(email="test1@example.com").first()
    event = Event(
        title='Test Event',
        description='This is a test event',
        date=datetime(2025, 12, 1, 12, 0),
        organizer=user
    )
    db_session.add(event)
    db_session.commit()

    notification = Notification(
        message='Test Notification',
        user_id=user.id,
        is_silenced=False,
        timestamp=datetime.now()
    )
    db_session.add(notification)
    db_session.commit()

    response = client.get(url_for('index.home'))
    assert response.status_code == 200
    assert b"Test Event" in response.data
    assert b"Test Notification" in response.data
