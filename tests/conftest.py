import uuid
import pytest
from app import create_app, db
from app.models import User, Event
from werkzeug.security import generate_password_hash
from datetime import datetime
from config import TestingConfig


@pytest.fixture(scope="module")
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def new_user(db_session):
    unique_username = f"testuser_{uuid.uuid4().hex[:8]}"
    unique_email = f"{unique_username}@example.com"

    user = User(
        username=unique_username,
        email=unique_email,
        password=generate_password_hash("password123"),
        first_name="Test",
        last_name="User"
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def db_session(app):
    with app.app_context():
        yield db.session
        db.session.rollback()


@pytest.fixture(scope="module")
def init_database(app):
    with app.app_context():
        db.create_all()

        user1 = User(
            username='testuser1',
            email='test1@example.com',
            password=generate_password_hash('password1'),
            first_name='Test',
            last_name='User1'
        )
        user2 = User(
            username='testuser2',
            email='test2@example.com',
            password=generate_password_hash('password2'),
            first_name='Test',
            last_name='User2'
        )

        event = Event(
            title='Test Event',
            description='This is a test event',
            date=datetime(2025, 12, 1, 12, 0),  # datetime обект
            organizer=user1
        )

        db.session.add_all([user1, user2, event])
        db.session.commit()

        yield db

        db.session.rollback()
        db.drop_all()


@pytest.fixture
def auth(client, db_session):
    class AuthActions:
        def login(self, email="test1@example.com", password="password1"):
            user = User.query.filter_by(email=email).first()
            if not user:
                user = User(
                    email=email,
                    username=email.split('@')[0],
                    first_name="Test",
                    last_name="User",
                    password=generate_password_hash(password),
                    profile_picture="default_profile.jpg",
                    date_added=datetime.utcnow()
                )
                db_session.add(user)
                db_session.commit()

            with client.session_transaction() as sess:
                sess['_user_id'] = user.id
                sess.permanent = True

        def logout(self):
            with client.session_transaction() as sess:
                sess.pop('_user_id', None)
                sess.permanent = False

    return AuthActions()


@pytest.fixture
def sample_event(db_session, client, auth):
    auth.login()
    user = User.query.filter_by(email="test1@example.com").first()
    event = Event(
        title="Sample Event",
        description="This is a test event.",
        date=datetime(2025, 5, 15, 14, 30),
        organizer_id=user.id
    )
    db_session.add(event)
    db_session.commit()
    return event


@pytest.fixture
def another_user(db_session):
    unique_username = f"another_user_{uuid.uuid4()}"
    unique_email = f"{unique_username}@example.com"

    user = User(
        username=unique_username,
        email=unique_email,
        password='password',
        first_name='First',
        last_name='Last',
        profile_picture='default_profile.jpg'
    )

    db_session.add(user)
    db_session.commit()
    return user
