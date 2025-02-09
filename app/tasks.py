"""This module handles automated notifications for upcoming events
 and cleans up old notifications."""
from datetime import timedelta, datetime
import pytz
from flask_mail import Message
from app import db
from app.models import Event, Attendance, Notification
from app.logger import setup_logger
from app import mail

logger = setup_logger()
TIMEZONE_UTC_PLUS_2 = pytz.timezone('Europe/Sofia')


def get_current_time_in_timezone(timezone) -> datetime:
    """Returns the current time in the given timezone."""
    current_time_utc = datetime.now(pytz.utc)
    return current_time_utc.astimezone(timezone)


def notify_upcoming_events():
    """Sends notifications for upcoming events every 12 hours."""
    current_time = get_current_time_in_timezone(TIMEZONE_UTC_PLUS_2)
    next_day = current_time + timedelta(days=1)

    upcoming_events = Event.query.filter(
        Event.date.between(current_time, next_day)
    ).all()

    for event in upcoming_events:
        attendees = Attendance.query.filter_by(
            event_id=event.id, status='accepted').all()

        for attendee in attendees:
            message = f'Reminder: Event "{event.title}" is happening tomorrow!'

            existing_notification = Notification.query.filter_by(
                user_id=attendee.user_id,
                event_id=event.id,
                message=message
            ).first()

            if existing_notification:
                continue

            new_notification = Notification(
                message=message,
                user_id=attendee.user_id,
                event_id=event.id
            )
            db.session.add(new_notification)

            user = attendee.user
            send_email(user.email, event.title, message)

    db.session.commit()


def send_email(to, event_title, message) -> None:
    """Sends an email notification to a user."""
    msg = Message(
        subject=f'Reminder: {event_title} is happening tomorrow!',
        recipients=[to],
        body=message
    )
    try:
        mail.send(msg)
    except Exception as e:
        logger.exception(e)


def clean_up_old_notifications():
    """Cleans up outdated notifications every 24 hours."""
    users_with_notifications = db.session.query(
        Notification.user_id).distinct().all()
    try:
        for user_tuple in users_with_notifications:
            user_id = user_tuple[0]
            notifications = Notification.query.filter_by(
                user_id=user_id).order_by(
                Notification.timestamp.desc()).all()

            if len(notifications) > 50:
                for notification in notifications[50:]:
                    db.session.delete(notification)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception(e)
