"""This module contains routes for the index and home pages of the application."""
from datetime import datetime
import pytz
from flask_login import current_user, login_required
from flask import redirect, url_for, render_template
from app.models import Attendance, Event, Notification
from . import index


timezone_utc_plus_2 = pytz.timezone('Europe/Sofia')


def get_current_time_in_timezone(timezone):
    """Get the current time in the specified timezone."""
    current_time_utc = datetime.now(pytz.utc)
    return current_time_utc.astimezone(timezone)


@index.route('/')
def index_route():
    """Route for the main landing page.
    If the user is authenticated, redirects to the home page.
    If the user is not authenticated, renders the index.html template."""
    if current_user.is_authenticated:
        return redirect(url_for('index.home'))
    return render_template('index.html')


@index.route('/home')
@login_required
def home():
    """Route for the home page, showing a list of events.
    Retrieves the user's organized events and events they are attending,
    and categorizes them into upcoming and past events based on the current time.
    Also retrieves and displays notifications for the user."""
    user_events = Event.query.filter_by(organizer_id=current_user.id).all()
    attending_events = Event.query.join(Attendance).filter(
        Attendance.user_id == current_user.id,
        Attendance.status == 'accepted'
    ).all()
    current_time = get_current_time_in_timezone(timezone_utc_plus_2)
    upcoming_events = [event for event in user_events + attending_events if
                       event.date.replace(tzinfo=pytz.utc) >= current_time]
    past_events = [event for event in user_events + attending_events if
                   event.date.replace(tzinfo=pytz.utc) < current_time]
    notifications = Notification.query.filter_by(
        user_id=current_user.id, is_silenced=False).order_by(
        Notification.timestamp.desc()).all()
    print(notifications)

    return render_template('home.html',
                           upcoming_events=upcoming_events,
                           past_events=past_events,
                           user_events=user_events,
                           notifications=notifications)
