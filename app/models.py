"""This module defines the SQLAlchemy models for users, events, etc. and
handles relationships and constraints."""
from datetime import datetime
from typing import List
import pytz
from werkzeug.security import check_password_hash
from flask_login import UserMixin
from app import db

TIMEZONE_UTC_PLUS_2 = pytz.timezone('Europe/Sofia')

# Association table for friend relationships
friend_association = db.Table(
    'friend_association',
    db.Column(
        'user_id',
        db.Integer,
        db.ForeignKey('user.id'),
        primary_key=True),
    db.Column(
        'friend_id',
        db.Integer,
        db.ForeignKey('user.id'),
        primary_key=True))


class User(UserMixin, db.Model):
    """Represents a user in the system."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    date_added = db.Column(db.DateTime, default=lambda: datetime.now(TIMEZONE_UTC_PLUS_2))
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    profile_picture = db.Column(db.String(255), nullable=True,
                                default='default_profile.jpg')

    events = db.relationship('Event', back_populates='organizer', lazy=True)
    friends = db.relationship(
        'User',
        secondary=friend_association,
        primaryjoin=(id == friend_association.c.user_id),
        secondaryjoin=(id == friend_association.c.friend_id),
        backref=db.backref('friend_of', lazy='dynamic'),
        lazy='select'
    )

    def __repr__(self):
        return f'<User {self.username}>'

    def verify_password(self, password) -> bool:
        """Verifies a user's password."""
        return check_password_hash(self.password, password)


class FriendRequest(db.Model):
    """Represents a friend request between users."""
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False)
    status = db.Column(db.String(50), default='pending')

    sender = db.relationship(
        'User',
        foreign_keys=[sender_id],
        backref='sent_requests')
    receiver = db.relationship(
        'User',
        foreign_keys=[receiver_id],
        backref='received_requests')

    def __repr__(self):
        return f'<FriendRequest {self.sender.username} -> {self.receiver.username}, status={self.status}>'



class Attendance(db.Model):
    """Represents a user's attendance at an event."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey(
            'user.id',
            ondelete='CASCADE'),
        nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    status = db.Column(db.String(50), default='pending')

    user = db.relationship('User', backref='attendances')
    event = db.relationship('Event', back_populates='attendances')

    def __repr__(self):
        return f'<Attendance User {self.user_id} for Event {self.event_id}, status={self.status}>'


class Task(db.Model):
    """Represents tasks for events."""
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey(
            'user.id',
            ondelete='CASCADE'),
        nullable=False)
    title = db.Column(db.String(255), nullable=False)
    completed = db.Column(db.Boolean, default=False)

    event = db.relationship('Event', backref=db.backref('tasks', lazy=True))
    user = db.relationship(
        'User',
        backref=db.backref(
            'tasks',
            lazy=True),
        foreign_keys=[user_id])

    def __repr__(self):
        return f'<Task {self.title}, Event {self.event_id}, Completed {self.completed}>'


class Event(db.Model):
    """Represents an event."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    date = db.Column(db.DateTime, nullable=False)
    organizer_id = db.Column(
        db.Integer,
        db.ForeignKey(
            'user.id',
            ondelete='SET NULL'),
        nullable=True)
    attendances = db.relationship(
        'Attendance',
        back_populates='event',
        cascade='all, delete-orphan')
    notifications = db.relationship(
        'Notification',
        back_populates='event',
        cascade='all, delete-orphan')
    organizer = db.relationship('User', back_populates='events')
    invitations = db.relationship('Invitation', back_populates='event')
    comments = db.relationship(
        'Comment',
        backref='event',
        cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Event {self.title}, Date {self.date}, Organizer {self.organizer_id}>'

    def get_participants(self) -> List[User]:
        """Retrieves the list of participants attending the event."""
        accepted_invitations = Invitation.query.filter_by(
            event_id=self.id, status='accepted').all()
        return [invitation.recipient for invitation in accepted_invitations]


class Comment(db.Model):
    """Represents comments for event."""
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey(
            'user.id',
            ondelete='CASCADE'),
        nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    timestamp = db.Column(
        db.DateTime, default=lambda: datetime.now(TIMEZONE_UTC_PLUS_2)
    )
    parent_comment_id = db.Column(
        db.Integer,
        db.ForeignKey('comment.id'),
        nullable=True)

    parent_comment = db.relationship(
        'Comment',
        remote_side=[id],
        backref='replies',
        lazy=True)
    user = db.relationship('User', backref=db.backref('comments', lazy=True))

    def __repr__(self):
        return f'<Comment by User {self.user_id} on Event {self.event_id}, {len(self.content)} characters>'


class Notification(db.Model):
    """Represents a notification sent to a user."""
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(
        db.DateTime, default=lambda: datetime.now(TIMEZONE_UTC_PLUS_2)
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey(
            'user.id',
            ondelete='CASCADE'),
        nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=True)
    is_silenced = db.Column(db.Boolean, default=False)

    event = db.relationship('Event', back_populates='notifications')
    user = db.relationship('User', backref='notifications')

    def __repr__(self):
        return f'<Notification {self.message}, User {self.user_id}, Event {self.event_id}>'

class Invitation(db.Model):
    """Represents an invitation sent to user."""
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(50), default='pending', nullable=False)
    event_id = db.Column(
        db.Integer,
        db.ForeignKey(
            'event.id',
            ondelete='CASCADE'),
        nullable=False)
    recipient_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=True)
    recipient_email = db.Column(db.String(120), nullable=True)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(TIMEZONE_UTC_PLUS_2),
        nullable=False)

    event = db.relationship('Event', back_populates='invitations')
    recipient = db.relationship('User', foreign_keys=[recipient_id])

    def __repr__(self):
        return f"<Invitation Event {self.event_id}, Status {self.status}, Recipient {self.recipient_email or self.recipient_id}>"
