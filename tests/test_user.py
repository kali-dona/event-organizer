""""Tests for the user module"""
import io
from flask import url_for
from app.models import User, FriendRequest, Notification
from app import db


def test_user_profile(client, auth):
    """Test user profile page"""
    auth.login()
    response = client.get(url_for('user.user_profile', user_id=1))
    assert response.status_code == 200
    assert b'Test User' in response.data
    assert b'<p><strong>Username:</strong> test1</p>' in response.data
    assert b'<p><strong>Email:</strong> test1@example.com</p>' in response.data
    assert b'profile_pictures/default_profile.jpg' in response.data


def test_delete_account(client, auth):
    """Test deleting an account"""
    auth.login()
    response = client.post(url_for('user.delete_account'))
    assert response.status_code == 302
    assert response.location == '/'


def test_edit_profile(client, auth):
    """Test editing a user's profile"""
    auth.login()
    data = {
        'first_name': 'NewName',
        'last_name': 'NewLastName',
        'email': 'newemail@example.com',
        'password': 'newpassword',
        'profile_picture': (io.BytesIO(b'fake image data'), 'profile.jpg')
    }
    response = client.post(
        url_for(
            'user.edit_profile',
            user_id=1),
        data=data,
        follow_redirects=True)
    assert response.status_code == 200
    assert b'Your profile was successfully updated!' in response.data


def test_send_friend_request(client, auth, init_database):
    """Test sending a friend request"""
    auth.login()
    user1 = User.query.filter_by(username='testuser1').first()
    user2 = User.query.filter_by(username='testuser2').first()

    existing_request = FriendRequest.query.filter_by(
        sender_id=user1.id, receiver_id=user2.id).first()
    if not existing_request:
        response = client.post(
            url_for(
                'user.send_friend_request',
                friend_id=user2.id))
        assert response.status_code == 302

        existing_request = FriendRequest.query.filter_by(
            sender_id=user1.id, receiver_id=user2.id).first()
        assert existing_request is not None

    notification = Notification.query.filter_by(user_id=user2.id).first()
    assert notification is not None


def test_respond_friend_request_accept(client, auth, init_database):
    """Test accepting a friend request"""
    auth.login()
    user1 = User.query.filter_by(username='testuser1').first()
    user2 = User.query.filter_by(username='testuser2').first()
    existing_request = FriendRequest.query.filter_by(
        sender_id=user1.id, receiver_id=user2.id).first()
    if not existing_request:
        existing_request = FriendRequest(
            sender_id=user1.id, receiver_id=user2.id)
        db.session.add(existing_request)
        db.session.commit()
    response = client.post(
        url_for(
            'user.respond_friend_request',
            request_id=existing_request.id,
            action='accept'))
    assert response.status_code == 302
