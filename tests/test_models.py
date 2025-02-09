from werkzeug.security import generate_password_hash
from app.models import FriendRequest, Attendance, Task, Comment, Notification, Invitation
from datetime import datetime
from app import db
from app.models import User, Event


def test_user_creation(app, init_database):
    user = User(
        username='john_doe',
        email='john1@example.com',  # Уникален имейл
        password=generate_password_hash('password123'),
        first_name='John',
        last_name='Doe'
    )
    db.session.add(user)
    db.session.commit()

    assert user.username == 'john_doe'
    assert user.email == 'john1@example.com'
    assert user.verify_password('password123')


def test_friend_request_creation(app, init_database):
    user1 = User.query.filter_by(email='test1@example.com').first()
    user2 = User.query.filter_by(email='test2@example.com').first()

    friend_request = FriendRequest(sender_id=user1.id, receiver_id=user2.id)
    db.session.add(friend_request)
    db.session.commit()

    assert friend_request.sender.username == 'testuser1'
    assert friend_request.receiver.username == 'testuser2'
    assert friend_request.status == 'pending'


def test_event_creation(app, init_database):
    user = User.query.filter_by(email='test1@example.com').first()

    event = Event(
        title='Sample Event',
        description='This is a sample event description',
        date=datetime(2025, 12, 1, 10, 30),
        organizer_id=user.id
    )
    db.session.add(event)
    db.session.commit()

    assert event.title == 'Sample Event'
    assert event.organizer.username == 'testuser1'
    assert event.date == datetime(2025, 12, 1, 10, 30)


def test_task_creation(app, init_database):
    user = User.query.filter_by(email='test1@example.com').first()
    event = Event.query.filter_by(title='Test Event').first()

    task = Task(
        title='Task 1',
        completed=False,
        event_id=event.id,
        user_id=user.id
    )
    db.session.add(task)
    db.session.commit()

    assert task.title == 'Task 1'
    assert task.event.title == 'Test Event'
    assert task.user.username == 'testuser1'
    assert task.completed is False


def test_attendance_creation(app, init_database):
    user = User.query.filter_by(email='test1@example.com').first()
    event = Event.query.filter_by(title='Test Event').first()

    attendance = Attendance(
        user_id=user.id,
        event_id=event.id,
        status='confirmed'
    )
    db.session.add(attendance)
    db.session.commit()

    assert attendance.status == 'confirmed'
    assert attendance.user.username == 'testuser1'
    assert attendance.event.title == 'Test Event'


def test_comment_creation(app, init_database):
    user = User.query.filter_by(email='test1@example.com').first()
    event = Event.query.filter_by(title='Test Event').first()

    comment = Comment(
        content='This is a comment',
        user_id=user.id,
        event_id=event.id
    )
    db.session.add(comment)
    db.session.commit()

    assert comment.content == 'This is a comment'
    assert comment.user.username == 'testuser1'
    assert comment.event.title == 'Test Event'


def test_notification_creation(app, init_database):
    user = User.query.filter_by(email='test1@example.com').first()
    event = Event.query.filter_by(title='Test Event').first()

    notification = Notification(
        message='This is a notification',
        user_id=user.id,
        event_id=event.id
    )
    db.session.add(notification)
    db.session.commit()

    assert notification.message == 'This is a notification'
    assert notification.user.username == 'testuser1'


def test_invitation_creation(app, init_database):
    user = User.query.filter_by(email='test1@example.com').first()
    event = Event.query.filter_by(title='Test Event').first()

    invitation = Invitation(
        status='pending',
        event_id=event.id,
        recipient_email='recipient@example.com'
    )
    db.session.add(invitation)
    db.session.commit()

    assert invitation.status == 'pending'
    assert invitation.event.title == 'Test Event'
    assert invitation.recipient_email == 'recipient@example.com'
