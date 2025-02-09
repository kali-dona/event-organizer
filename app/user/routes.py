"""Module to defines user-related routes and to allows users
to manage (edit, delete) their profiles,
send and respond to friend requests, remove friends and searching for users."""
import os
import flask
from flask import current_app, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from app.models import (User, Attendance, Task, Event,
                        Comment, Notification, Invitation, FriendRequest, friend_association)
from app.logger import setup_logger
from app import db
from . import user


logger = setup_logger()


def allowed_file(filename):
    """Checks if a given file has an allowed extension based on
    the configured ALLOWED_EXTENSIONS."""
    return '.' in filename and filename.rsplit(
        '.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


@user.route('/user/<int:user_id>')
@login_required
def user_profile(user_id):
    """Displays a user's profile page. If the user is viewing their
    own profile, they have full access. If they are viewing someone else's
    profile, only partial information is shown."""
    cur_user = User.query.get_or_404(user_id)

    if cur_user == current_user:
        return render_template(
            'user_profile.html',
            user=cur_user,
            full_access=True)
    return render_template(
            'user_profile.html',
            user=cur_user,
            full_access=False)


@user.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    """Deletes the currently logged-in user's account and associated data,
    including comments, tasks, notifications, friend requests, and events.
    Redirects to the index route after the account deletion."""
    cur_user = User.query.get_or_404(current_user.id)
    if cur_user != current_user:
        flash('You can\'t delete someone else profile!', 'danger')
        return redirect(url_for('user.user_profile', user_id=current_user.id))

    try:
        Comment.query.filter_by(
            user_id=cur_user.id).delete(
            synchronize_session=False)
        Task.query.filter_by(user_id=cur_user.id).delete(synchronize_session=False)
        FriendRequest.query.filter(
            (FriendRequest.sender_id == cur_user.id) | (
                FriendRequest.receiver_id == cur_user.id)).delete(
            synchronize_session=False)
        Attendance.query.filter_by(
            user_id=cur_user.id).delete(
            synchronize_session=False)
        Invitation.query.filter_by(
            recipient_id=cur_user.id).delete(
            synchronize_session=False)
        Notification.query.filter_by(
            user_id=cur_user.id).delete(
            synchronize_session=False)
        events = Event.query.filter_by(organizer_id=cur_user.id).all()
        for event in events:
            Notification.query.filter_by(
                event_id=event.id).delete(
                synchronize_session=False)
        Event.query.filter_by(
            organizer_id=cur_user.id).delete(
            synchronize_session=False)
        db.session.delete(cur_user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception(e)
        flask.flash('Deleting account error', category='danger')
    return redirect(url_for('index.index_route'))


@user.route('/edit_profile/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_profile(user_id):
    """Allows the logged-in user to edit their profile,
    including their name, email, password, and profile picture."""
    cur_user = User.query.get_or_404(user_id)

    if cur_user != current_user:
        flash('You can\'t edit someone else profile!', 'danger')
        return redirect(url_for('user.user_profile', user_id=current_user.id))

    if request.method == 'POST':
        try:
            cur_user.first_name = request.form.get('first_name', cur_user.first_name)
            cur_user.last_name = request.form.get('last_name', cur_user.last_name)
            email = request.form.get('email')
            if email and email != cur_user.email:
                existing_user = User.query.filter_by(email=email).first()
                if existing_user:
                    flash('This email has profile already.', 'warning')
                    return redirect(
                        url_for(
                            'user.edit_profile',
                            user_id=cur_user.id))
                cur_user.email = email

            password = request.form.get('password')
            if password:
                cur_user.password = generate_password_hash(password)

            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and allowed_file(file.filename):
                    try:
                        filename = secure_filename(file.filename)
                        file_path = os.path.join(
                            current_app.root_path, 'static', 'profile_pictures', filename)
                        file.save(file_path)
                        cur_user.profile_picture = filename
                    except Exception as e:
                        logger.exception(e)
                        flash('Error uploading profile picture.', 'danger')

            db.session.commit()
            flash('Your profile was successfully updated!', 'success')
        except Exception as e:
            db.session.rollback()
            logger.exception(e)
            flash('An error occurred while updating your profile.', 'danger')

        return redirect(url_for('user.user_profile', user_id=cur_user.id))

    return render_template('edit_profile.html', user=cur_user)


@user.route('/send_friend_request/<int:friend_id>', methods=['POST'])
@login_required
def send_friend_request(friend_id):
    """Sends a friend request to another user. The request can only be sent
    if the current user is not already friends with the recipient and
    has not already sent a request."""
    friend = User.query.get_or_404(friend_id)

    if current_user.id == friend.id:
        flash('You can\'t add yourself as a friend!', 'danger')
        return redirect(url_for('user.user_profile', user_id=current_user.id))

    if friend in current_user.friends:
        flash('You are already friends!', 'info')
        return redirect(url_for('user.user_profile', user_id=current_user.id))

    existing_request = FriendRequest.query.filter_by(
        sender_id=current_user.id,
        receiver_id=friend.id,
        status='pending').first()
    if existing_request:
        flash('Friend request already sent!', 'info')
        return redirect(url_for('user.user_profile', user_id=current_user.id))

    try:
        friend_request = FriendRequest(
            sender_id=current_user.id,
            receiver_id=friend.id)
        db.session.add(friend_request)

        link = url_for('user.user_profile', user_id=friend.id, _external=True)

        notification = Notification(
            message=f'{
                current_user.username} sent you a friend request! '
                    f'<a href="{link}">Accept/Decline</a>',
            user_id=friend.id)
        db.session.add(notification)
        db.session.commit()
        flash('Friend request sent!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.exception(e)
        flash('An error occurred while sending your friend request.', 'danger')

    return redirect(url_for('user.user_profile', user_id=current_user.id))


@user.route('/respond_friend_request/<int:request_id>/<string:action>',methods=['GET', 'POST'])
@login_required
def respond_friend_request(request_id, action):
    """Responds to a friend's request by either accepting or declining it.
    If accepted, the user is added as a friend, and the request is removed.
    If declined, the request is simply removed."""
    friend_request = FriendRequest.query.get_or_404(request_id)

    if friend_request.receiver_id != current_user.id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('index.index_route'))
    try:
        if action == 'accept':
            if friend_request.status in current_user.friends:
                flash('You are already friends!', 'info')
            else:
                current_user.friends.append(friend_request.sender)
                friend_request.sender.friends.append(current_user)
                flash('Friend request accepted!', 'success')
            db.session.delete(friend_request)

            notification = Notification(
                message=f'{
                    current_user.username} accepted your friend request!',
                user_id=friend_request.sender.id)
            db.session.add(notification)

        elif action == 'decline':
            db.session.delete(friend_request)
            notification = Notification(
                message=f'{
                    current_user.username} declined your friend request.',
                user_id=friend_request.sender.id)
            db.session.add(notification)
            flash('Friend request declined.', 'info')

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception(e)
        flash('An error occurred while processing the friend request.', 'danger')
    return redirect(url_for('user.user_profile', user_id=current_user.id))


@user.route('/remove_friend/<int:friend_id>', methods=['POST'])
@login_required
def remove_friend(friend_id):
    """Removes a friend from the current user's friend list.
    Both sides of the friendship are deleted
    from the association table."""
    friend = User.query.get_or_404(friend_id)

    friendship1 = db.session.query(friend_association).filter_by(
        user_id=current_user.id, friend_id=friend.id).first()
    friendship2 = db.session.query(friend_association).filter_by(
        user_id=friend.id, friend_id=current_user.id).first()

    if not friendship1 or not friendship2:
        flash('This user is not your friend.', 'info')
        return redirect(url_for('user.user_profile', user_id=current_user.id))

    try:
        db.session.execute(
            friend_association.delete().where(
                friend_association.c.user_id == current_user.id,
                friend_association.c.friend_id == friend.id))
        db.session.execute(
            friend_association.delete().where(
                friend_association.c.user_id == friend.id,
                friend_association.c.friend_id == current_user.id))
        db.session.commit()
        flash('Friend removed successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.exception(e)
        flash('An error occurred while removing the friend.', 'danger')
    return redirect(url_for('user.user_profile', user_id=current_user.id))


@user.route('/search_friend', methods=['GET'])
@login_required
def search_friend():
    """Searches for users by their name, username, or email address.
    Displays the search results on the user's profile page.
    Redirects the user back to their profile if no search term is provided
    or if there is an error."""
    search_term = request.args.get('search_term')

    if not search_term:
        flash('Please enter a Name, Username or Email.', 'warning')
        return redirect(url_for('user.user_profile', user_id=current_user.id))
    try:
        search_results = User.query.filter(
            User.id != current_user.id,
            (User.first_name.ilike(f'%{search_term}%')) |
            (User.last_name.ilike(f'%{search_term}%')) |
            (User.username.ilike(f'%{search_term}%')) |
            (User.email.ilike(f'%{search_term}%'))
        ).all()
    except Exception as e:
        logger.exception(e)
        flash('An error occurred while searching for friends.', 'danger')
        return redirect(url_for('user.user_profile', user_id=current_user.id))

    if not search_results:
        flash('No users found.', 'info')
        return redirect(url_for('user.user_profile', user_id=current_user.id))

    return render_template(
        'user_profile.html',
        user=current_user,
        search_results=search_results,
        search_term=search_term,
        full_access=True
    )
