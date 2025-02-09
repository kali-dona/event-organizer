"""This module contains routes and views for event management, including
functions for creating, editing, deleting events, managing event tasks,
comments, and invitations."""
from datetime import datetime
import pytz
from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from flask_mail import Message
from app.logger import setup_logger
from app import db
from app.models import User, Attendance, Task, Event, Comment, Notification, Invitation
from app import mail
from . import event

logger = setup_logger()

timezone_utc_plus_2 = pytz.timezone('Europe/Sofia')


def get_current_time_in_timezone(timezone):
    """Get the current time in the specified timezone."""
    current_time_utc = datetime.now(pytz.utc)
    return current_time_utc.astimezone(timezone)


@event.route('/create-event', methods=['GET', 'POST'])
@login_required
def create_event():
    """Handles the creation of a new event. It processes the form data to
    create an event, validate the data, and send invitations to the guests
    via email or friend IDs."""
    friends = current_user.friends

    if request.method == 'POST':
        event_name = request.form.get('title')
        event_description = request.form.get('description')
        event_date = request.form.get('date')
        invite_method = request.form.get('invite_method')
        guest_emails = request.form.get('guest_email', '').split(',')
        friend_ids = request.form.getlist('friends')

        if not event_name or not event_date:
            flash('Event name, date and time are necessary!', 'danger')
            return redirect(url_for('event.create_event'))
        try:
            event_date = datetime.strptime(event_date, '%Y-%m-%dT%H:%M')
            if event_date <= datetime.now():
                flash(
                    'The date of the event must be current/after current date!',
                    'danger')
                return redirect(url_for('event.create_event'))

            new_event = Event(
                title=event_name,
                description=event_description,
                date=event_date,
                organizer_id=current_user.id
            )
            db.session.add(new_event)
            db.session.commit()

            email_list = [email.strip()
                          for email in guest_emails if email.strip()]
            if invite_method and (email_list or friend_ids):
                send_invitations(
                    new_event,
                    invite_method,
                    email_list,
                    friend_ids)
            flash('Event was created successfully!', 'success')
            return redirect(
                url_for(
                    'event.event_detail',
                    event_id=new_event.id))

        except Exception as e:
            db.session.rollback()
            logger.exception(e)
            flash('Event was not created successfully!', 'danger')

    return render_template('create_event.html', friends=friends)


@event.route('/edit-event/<int:event_id>', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    """Handles editing of an existing event. It updates the event with the provided
    data. The function also sends update notifications to participants."""
    cur_event = Event.query.get_or_404(event_id)

    if cur_event.organizer_id != current_user.id:
        flash('You are not authorized to edit this event.', 'danger')
        return redirect(url_for('event.event_detail', event_id=cur_event.id))

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        date_str = request.form.get('date')
        time_str = request.form.get('time')

        try:
            cur_event.title = title
            cur_event.description = description
            if date_str and time_str:
                cur_event.date = datetime.strptime(
                    f'{date_str} {time_str}', '%Y-%m-%d %H:%M')
            elif date_str:
                cur_event.date = datetime.strptime(date_str, '%Y-%m-%d')
            elif time_str:
                cur_event.date = cur_event.date.replace(
                    hour=int(
                        time_str.split(':')[0]), minute=int(
                        time_str.split(':')[1]))

            db.session.commit()
            flash('Event was successfully updated!', 'success')
            send_update_email(cur_event, f'Hello!\n\n"{
            cur_event.title}" has been recently updated. You can see the changes here: {
            url_for(
                'event.event_detail',
                event_id=cur_event.id,
                _external=True)}')
            create_event_update_notification(
                cur_event, f'Event "{
                cur_event.title}" was recently updated.')

            return redirect(url_for('event.event_detail', event_id=cur_event.id))

        except ValueError:
            flash('Invalid date or time format. Try to edit again.', 'danger')
        except Exception as e:
            db.session.rollback()
            logger.exception(e)
            flash(
                'Unexpected error! Event was not updated successfully!',
                'danger')

    return render_template('edit_event.html', event=cur_event)


@event.route('/delete-event/<int:event_id>', methods=['POST'])
@login_required
def delete_event(event_id):
    """Deletes an existing event and its associated data (invitations, comments, etc.)
     from the database."""
    cur_event = Event.query.get_or_404(event_id)

    if cur_event.organizer_id != current_user.id:
        flash('You are not organizer of this event and can\'t delete it!', 'danger')
        return redirect(url_for('user.user_profile', user_id=current_user.id))

    try:
        send_update_email(cur_event, f'Event "{cur_event.title}" has '
                                     f'been deleted. You can see your other events here: {
                                                url_for(
                                                'index.home',
                                                event_id=cur_event.id,
                                                _external=True)}')
        Invitation.query.filter_by(event_id=event_id).delete()
        Attendance.query.filter_by(event_id=event_id).delete()
        Notification.query.filter_by(event_id=event_id).delete()
        Comment.query.filter_by(event_id=event_id).delete()
        Task.query.filter_by(event_id=event_id).delete()
        db.session.delete(cur_event)
        db.session.commit()

        flash('Event was successfully deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.exception(e)
        flash('Unexpected error! Event was not deleted successfully!', 'danger')

    return redirect(url_for('user.user_profile', user_id=current_user.id))


@event.route('/event/<int:event_id>')
@login_required
def event_detail(event_id):
    """Displays the details of a specific event, including participants, comments,
     tasks, and invitations."""
    try:
        cur_event = Event.query.get_or_404(event_id)
        is_owner = cur_event.organizer_id == current_user.id
        is_attending = Attendance.query.filter_by(
            event_id=cur_event.id,
            user_id=current_user.id,
            status='accepted').first()
        comments = Comment.query.filter_by(
            event_id=event_id, parent_comment_id=None).all()
        for comment in comments:
            comment.replies = Comment.query.filter_by(
                parent_comment_id=comment.id).all()

        db.session.commit()
        participants = []
        if is_owner or cur_event.get_participants():
            participants = db.session.query(User).join(Attendance).filter(
                Attendance.event_id == cur_event.id,
                Attendance.status == 'accepted'
            ).all()

        tasks = []
        if is_owner:
            tasks = Task.query.filter_by(event_id=cur_event.id).all()

        friends = current_user.friends

        current_time = get_current_time_in_timezone(timezone_utc_plus_2)
        event_has_passed = cur_event.date.replace(
            tzinfo=pytz.utc) < current_time
    except Exception as e:
        logger.exception(e)
        flash('There was an error loading your event!', 'danger')
        return redirect(url_for('index.home', user_id=current_user.id))
    return render_template(
        'event_detail.html',
        event=cur_event,
        is_owner=is_owner,
        is_attending=is_attending,
        participants=participants,
        tasks=tasks,
        comments=comments,
        friends=friends,
        event_has_passed=event_has_passed
    )


@event.route('/invitation/<int:invitation_id>', methods=['GET', 'POST'])
def invitation_page(invitation_id):
    """Displays an invitation to a user, allowing them to accept or decline it"""
    try:
        invitation = Invitation.query.get_or_404(invitation_id)
        cur_event = Event.query.get_or_404(invitation.event_id)
        if not current_user.is_authenticated:
            flash('Please register to respond to the invitation.', 'info')
            return redirect(url_for('auth.register',
                                    next=request.url))
        if not invitation.recipient_id and invitation.recipient_email == current_user.email:
            invitation.recipient_id = current_user.id
            db.session.commit()
        if (invitation.recipient_id != current_user.id and
                invitation.recipient_email != current_user.email):
            flash('You are not authorized to view this invitation.', 'danger')
            return redirect(url_for('index.home'))

        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'accept':
                invitation.status = 'accepted'
                db.session.commit()

                attendance = Attendance.query.filter_by(
                    user_id=current_user.id, event_id=cur_event.id).first()
                if attendance:
                    attendance.status = 'accepted'
                else:
                    new_attendance = Attendance(
                        user_id=current_user.id,
                        event_id=invitation.event_id,
                        status='accepted')
                    db.session.add(new_attendance)
                create_invitation_status_notification(
                    cur_event.id, cur_event.organizer_id, 'accepted', current_user.username)
                db.session.commit()

                flash(
                    f'You have accepted the invitation to "{
                    cur_event.title}".', 'success')
                return redirect(
                    url_for(
                        'event.event_detail',
                        event_id=cur_event.id))
            if action == 'decline':
                invitation.status = 'declined'
                db.session.commit()
                create_invitation_status_notification(
                    cur_event.id, cur_event.organizer_id, 'declined', current_user.username)
                flash(
                    f'You have declined the invitation to "{
                    cur_event.title}".', 'danger')
                return redirect(url_for('index.home'))
    except Exception as e:
        db.session.rollback()
        logger.exception(e)
        flash('There was an error loading your invitation!', 'danger')
        return redirect(url_for('index.home'))

    return render_template(
        'invitation_page.html',
        invitation=invitation,
        event=cur_event)


@event.route('/event/<int:event_id>/invite', methods=['POST'])
@login_required
def invite_to_event(event_id):
    """Allows the event organizer to send invitations to guests by email or friends."""
    cur_event = Event.query.get_or_404(event_id)
    try:
        if cur_event.organizer_id != current_user.id:
            flash('You can\'t send invites for this event!', 'danger')
            return redirect(url_for('event.event_detail', event_id=cur_event.id))

        invite_method = request.form.get('invite_method')
        guest_emails = request.form.get('guest_email', '').strip()
        friend_ids = request.form.getlist('friends')
        email_list = [email.strip()
                      for email in guest_emails.split(',') if email.strip()]

        send_invitations(cur_event, invite_method, email_list, friend_ids)
    except Exception as e:
        logger.exception(e)
        flash('There was an error sending invitations!', 'danger')

    return redirect(url_for('event.event_detail', event_id=cur_event.id))


@event.route('/event/<int:event_id>/comment', methods=['POST'])
@login_required
def add_comment(event_id):
    """Allows users to add comments to an event they are part in.
    It also sends notifications to event organizers and participants."""
    cur_event = Event.query.get_or_404(event_id)
    try:
        attendance = Attendance.query.filter_by(
            event_id=event_id,
            user_id=current_user.id,
            status='accepted').first()
        if not attendance and cur_event.organizer_id != current_user.id:
            flash(
                'You need to accept the invitation to comment on this event.',
                'danger')
            return redirect(url_for('event.event_detail', event_id=event_id))

        content = request.form.get('content')
        parent_comment_id = request.form.get('parent_comment_id', None)

        if content:
            comment = Comment(
                content=content,
                user_id=current_user.id,
                event_id=event_id,
                parent_comment_id=parent_comment_id)
            db.session.add(comment)

            if cur_event.organizer_id != current_user.id:
                create_comment_notification(event_id, cur_event.organizer_id)

            attendees = Attendance.query.filter_by(
                event_id=event_id, status='accepted').all()
            for attendee in attendees:
                if attendee.user_id != current_user.id:
                    create_comment_notification(event_id, attendee.user_id)
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception(e)
        flash('There was an error adding your comment!', 'danger')

    return redirect(url_for('event.event_detail', event_id=event_id))


@event.route('/event/<int:event_id>/add-task', methods=['POST'])
@login_required
def add_task(event_id):
    """Allows the event organizer to add tasks to the event."""
    cur_event = Event.query.get_or_404(event_id)

    try:
        if cur_event.organizer_id != current_user.id:
            flash(
                'You are not the organizer of this event to add tasks.',
                'danger')
            return redirect(url_for('event.event_detail', event_id=event_id))

        if request.method == 'POST':
            task_title = request.form.get('task_title')
            if not task_title.strip():
                flash('Task title cannot be empty.', 'warning')
            else:
                new_task = Task(
                    title=task_title,
                    event_id=event_id,
                    user_id=current_user.id)
                db.session.add(new_task)
                db.session.commit()
                flash('Task added successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.exception(e)
        flash('There was an error adding your task!', 'danger')

    return redirect(url_for('event.event_detail', event_id=cur_event.id))


@event.route('/task/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_task(task_id):
    """Toggles the completion status of a task. It checks if the user is
    the event organizer before modifying the task status."""
    task = Task.query.get_or_404(task_id)

    if task.event.organizer_id != current_user.id:
        flash('You are not authorized to modify this task.', 'danger')
        return redirect(url_for('event.event_detail', event_id=task.event_id))

    task.completed = not task.completed
    db.session.commit()
    flash('Task status updated.', 'success')
    return redirect(url_for('event.event_detail', event_id=task.event_id))


@event.route('/task/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    """Deletes a task from an event."""
    task = Task.query.get_or_404(task_id)

    try:
        if current_user.id not in (task.event.organizer_id, task.user_id):
            flash('You are not authorized to delete this task.', 'danger')
            return redirect(
                url_for(
                    'event.event_detail',
                    event_id=task.event_id))

        db.session.delete(task)
        db.session.commit()
        flash('Task deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.exception(e)
        flash('There was an error deleting your task!', 'danger')
    return redirect(url_for('event.event_detail', event_id=task.event_id))


def invitation_exists(event_id, email=None, user_id=None) -> bool:
    """Checks if an invitation already exists for a given event."""
    if email:
        return Invitation.query.filter_by(
            event_id=event_id,
            recipient_email=email).first() is not None
    if user_id:
        return Invitation.query.filter_by(
            event_id=event_id,
            recipient_id=user_id).first() is not None
    return False


def send_invitations(
        cur_event,
        invite_method,
        emails=None,
        friend_ids=None) -> None:
    """Sends invitations for an event through the invite method (email or friends).
    It also sends notification emails to the invited guests."""
    try:
        invitations_sent = 0
        skipped_invitations = 0

        if invite_method == 'email' and emails:
            for email in emails:
                email = email.strip()
                user = User.query.filter_by(email=email).first()

                if invitation_exists(
                        cur_event.id, email=email) or (
                        user and invitation_exists(
                    cur_event.id, user_id=user.id)):
                    skipped_invitations += 1
                    continue

                if not user:
                    invitation = Invitation(
                        event_id=cur_event.id, recipient_email=email)
                else:
                    invitation = Invitation(
                        event_id=cur_event.id, recipient_id=user.id, recipient_email=user.email)
                    create_invitation_notification(invitation)

                db.session.add(invitation)
                db.session.commit()

                msg = Message(
                    subject=f'Invitation for {
                    cur_event.title}',
                    recipients=[
                        email if not user else user.email],
                    body=f'Hello,\n\nYou were invited to "{
                    cur_event.title}".\n\n' f'You can accept or decline here: {
                    url_for(
                        'event.invitation_page',
                        invitation_id=invitation.id,
                        _external=True)}')
                mail.send(msg)
                invitations_sent += 1

        elif invite_method == 'friends' and friend_ids:
            for friend_id in friend_ids:
                friend = User.query.get(friend_id)
                if not friend or invitation_exists(
                        cur_event.id, user_id=friend.id):
                    skipped_invitations += 1
                    continue

                invitation = Invitation(
                    event_id=cur_event.id, recipient_id=friend.id, recipient_email=user.email)
                db.session.add(invitation)
                db.session.commit()

                create_invitation_notification(invitation)
                msg = Message(
                    subject=f'Invitation for {
                    cur_event.title}',
                    recipients=[
                        friend.email],
                    body=f'Hello {
                    friend.username},\n\nYou were invited to "{
                    cur_event.title}".\n\n' f'You can accept or decline here: {
                    url_for(
                        'event.invitation_page',
                        invitation_id=invitation.id,
                        _external=True)}')
                mail.send(msg)
                invitations_sent += 1

        if invitations_sent > 0:
            flash(f'{invitations_sent} invitations are send.', 'success')
        if skipped_invitations > 0:
            flash(f'{skipped_invitations} invitation were not '
                  f'send because they are already been send.',
                  'warning')

    except Exception as e:
        db.session.rollback()
        logger.exception(e)
        flash('There was an error sending your invitations!', 'danger')


def send_update_email(cur_event, message) -> None:
    """Sends an email to all participants when an event is updated."""
    participants = cur_event.get_participants()
    if not participants:
        return
    for participant in participants:
        if participant.email:
            msg = Message(
                subject=f'{
                cur_event.title} has been updated.',
                recipients=[
                    participant.email],
                body=message)
            try:
                mail.send(msg)
            except Exception as e:
                logger.exception(e)
                flash('There was an error sending your updates!', 'danger')


def create_event_update_notification(cur_event, message) -> None:
    """Creates and sends a notification to participants when an event is updated."""
    attendees = Attendance.query.filter_by(
        event_id=cur_event.id, status='accepted').all()
    if not attendees:
        return
    link = url_for('event.event_detail', event_id=cur_event.id, _external=True)

    try:
        for attendee in attendees:
            notification = Notification(
                message=f'<a href="{link}">{message}</a>',
                user_id=attendee.user_id,
                event_id=cur_event.id
            )
            db.session.add(notification)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception(e)
        flash('There was an error sending your update notification!', 'danger')


def create_invitation_notification(invitation) -> None:
    """Creates a notification when a user receives an invitation to an event."""
    try:
        if not invitation.id:
            db.session.add(invitation)
            db.session.commit()
            db.session.refresh(invitation)
        cur_event = Event.query.get(invitation.event_id)
        if not cur_event or not invitation.recipient_email:
            return

        link = url_for(
            'event.invitation_page',
            invitation_id=invitation.id,
            _external=True)
        new_notification = Notification(
            message=f'<a href="{link}">You have been invited to {
            cur_event.title}</a>',
            user_id=invitation.recipient_id,
            event_id=cur_event.id)

        db.session.add(new_notification)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception(e)
        flash(
            'There was an error sending notification for your invitations!',
            'danger')


def create_invitation_status_notification(
        event_id, organizer_id, status, guest_id) -> None:
    """Creates a notification when the status of an invitation is changed (accepted or declined)."""
    try:
        cur_event = Event.query.get(event_id)
        if not cur_event:
            return
        message = f'{guest_id} has {status} your invitation for event "{
        Event.query.get(event_id).title}"'
        new_notification = Notification(
            message=message,
            user_id=organizer_id,
            event_id=event_id
        )
        db.session.add(new_notification)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception(e)


def create_comment_notification(event_id, user_id) -> None:
    """Creates a notification when a new comment is added to an event."""
    try:
        cur_event = Event.query.get(event_id)
        if not cur_event:
            return
        message = f'New comment on event "{cur_event.title}"'
        link = url_for('event.event_detail', event_id=event_id, _external=True)
        new_notification = Notification(
            message=f'<a href="{link}">{message}</a>',
            user_id=user_id,
            event_id=event_id
        )
        db.session.add(new_notification)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception(e)
