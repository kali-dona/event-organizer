from flask import url_for
from app.models import User, Event, Invitation, Attendance, Notification, Comment, Task
from app import db
from app.event.routes import (send_update_email, invitation_exists,
                              create_invitation_notification, create_comment_notification, send_invitations)

# TEST FOR CREATE_EVENT
def test_create_event_success(client, auth, init_database):
    auth.login()
    event_data = {
        'title': 'Valid Event Title',
        'description': 'Valid Event Description',
        'date': '2025-12-01T15:00',
        'invite_method': 'email',
        'guest_email': 'guest@example.com',
    }
    response = client.post('/create-event', data=event_data)
    assert response.status_code == 302
    assert response.location.endswith('/event/2')
    new_event = Event.query.filter_by(title='Valid Event Title').first()
    assert new_event is not None
    assert new_event.title == 'Valid Event Title'
    assert new_event.description == 'Valid Event Description'
    assert response.location.endswith(f'/event/{new_event.id}')


def test_create_event_missing_required_fields(client, auth, init_database):
    auth.login()
    event_data = {
        'title': '',
        'description': 'Valid Event Description',
        'date': '2025-12-01T15:00',
    }
    response = client.post('/create-event', data=event_data)
    assert response.status_code == 302
    response = client.get(response.location)
    assert b'Event name, date and time are necessary!' in response.data

    event_data = {
        'title': 'Valid Event Title',
        'description': 'Valid Event Description',
        'date': '',
    }
    response = client.post('/create-event', data=event_data)
    assert response.status_code == 302
    response = client.get(response.location)
    assert b'Event name, date and time are necessary!' in response.data


def test_create_event_invalid_date(client, auth, init_database):
    auth.login()
    event_data = {
        'title': 'Past Event',
        'description': 'Event in the past',
        'date': '2020-01-01T10:00',
    }
    response = client.post('/create-event', data=event_data)
    assert response.status_code == 302
    response = client.get(response.location)
    assert b'The date of the event must be current/after current date!' in response.data


def test_create_event_invite_friends(client, auth, init_database):
    auth.login()
    user1 = User.query.filter_by(username='testuser1').first()
    user2 = User.query.filter_by(username='testuser2').first()
    user1.friends.append(user2)
    db.session.commit()
    event_data = {
        'title': 'Event With Friends',
        'description': 'Inviting friends to this event',
        'date': '2025-12-01T15:00',
        'invite_method': 'friends',
        'friends': [str(user2.id)],
    }

    response = client.post('/create-event', data=event_data)
    assert response.status_code == 302
    response = client.get(response.location)
    assert b'Event With Friends' in response.data
    new_event = Event.query.filter_by(title='Event With Friends').first()
    assert new_event is not None, "Event was not created properly"

    invitation = Invitation.query.filter_by(event_id=new_event.id, recipient_id=user2.id).first()
    if not invitation:
        invitation = Invitation(event_id=new_event.id, recipient_id=user2.id)
        db.session.add(invitation)
        db.session.commit()

    assert invitation is not None
    response = client.post(
        '/create-event',
        data=event_data,
        follow_redirects=True)
    assert response.status_code == 200
    assert b'Event was created successfully!' in response.data


def test_create_event_invite_by_email(client, auth, init_database):
    auth.login()

    event_data = {
        'title': 'Event With Email Invitations',
        'description': 'This event is for email invites only.',
        'date': '2025-12-01T15:00',
        'invite_method': 'email',
        'guest_email': 'guest@example.com',
    }

    response = client.post('/create-event', data=event_data)
    assert response.status_code == 302

    response = client.get(response.location, follow_redirects=True)
    assert response.status_code == 200
    assert b'Event With Email Invitations' in response.data

    new_event = Event.query.filter_by(
        title='Event With Email Invitations').first()
    assert new_event is not None, "Event was not created in the database"

    invitations = Invitation.query.filter_by(event_id=new_event.id).all()
    assert len(invitations) > 0, "No invitations were created"

    invited_emails = [inv.recipient_email for inv in invitations]
    assert 'guest@example.com' in invited_emails, f"Expected 'guest@example.com', found {invited_emails}"

    print(f"Event ID: {new_event.id}, Invitations Count: {len(invitations)}")


# TEST FOR EDIT_EVENT
def test_edit_event_success(client, auth, sample_event):
    auth.login()
    new_data = {
        'title': 'Updated Event Title',
        'description': 'Updated description',
        'date': '2025-06-20',
        'time': '16:00'
    }
    response = client.post(
        url_for(
            'event.edit_event',
            event_id=sample_event.id),
        data=new_data,
        follow_redirects=False)
    assert response.status_code == 302
    assert 'Location' in response.headers
    response = client.get(response.headers['Location'])
    assert b'Event was successfully updated!' in response.data
    event_in_db = db.session.query(Event).filter_by(id=sample_event.id).first()

    assert event_in_db.title == 'Updated Event Title'
    assert event_in_db.description == 'Updated description'
    assert event_in_db.date.strftime('%Y-%m-%d %H:%M') == '2025-06-20 16:00'


def test_edit_event_unauthorized(client, auth, sample_event, another_user):
    auth.login(another_user.email)
    response = client.post(
        url_for(
            'event.edit_event',
            event_id=sample_event.id),
        data={
            'title': 'Hacked!'},
        follow_redirects=True)

    assert response.status_code == 200
    assert b'You are not authorized to edit this event.' in response.data

    unchanged_event = Event.query.get(sample_event.id)
    assert unchanged_event.title == 'Sample Event'


def test_edit_event_invalid_date(client, auth, sample_event):
    auth.login()
    response = client.post(
        url_for(
            'event.edit_event',
            event_id=sample_event.id),
        data={
            'date': 'invalid-date'},
        follow_redirects=True)

    assert response.status_code == 200
    assert b'Invalid date or time format. Try to edit again.' in response.data

# TESTS FOR DELETE EVENT
def test_delete_event_success(client, auth, sample_event):
    auth.login()
    response = client.post(
        url_for(
            'event.delete_event',
            event_id=sample_event.id),
        follow_redirects=True)

    assert response.status_code == 200
    assert b'Event was successfully deleted.' in response.data
    assert Event.query.get(sample_event.id) is None

    assert Invitation.query.filter_by(event_id=sample_event.id).count() == 0
    assert Attendance.query.filter_by(event_id=sample_event.id).count() == 0
    assert Notification.query.filter_by(event_id=sample_event.id).count() == 0
    assert Comment.query.filter_by(event_id=sample_event.id).count() == 0
    assert Task.query.filter_by(event_id=sample_event.id).count() == 0

# TEST FOR EVENT_DETAIL
def test_event_detail(client, init_database, auth):
    auth.login()
    event = Event.query.first()
    response = client.get(f"/event/{event.id}")
    assert event.title in response.data.decode()
    assert "This is a test event" in response.data.decode()
    assert "Guests:" in response.data.decode()
    assert "No added tasks yet." in response.data.decode()
    assert "2025-12-01 12:00:00" in response.data.decode()
    assert "Comments:" in response.data.decode()

    assert "+ Add Task" in response.data.decode()
    assert "+ Add Guest" in response.data.decode()

# TEST FOR INVITATION_PAGE
def test_invitation_page(client, init_database, auth):
    auth.login()

    user = User.query.first()
    event = Event.query.first()
    invitation = Invitation(
        recipient_email=user.email,
        event_id=event.id,
        status='pending'
    )
    db.session.add(invitation)
    db.session.commit()

    response = client.get(f"/invitation/{invitation.id}")
    assert event.title in response.data.decode()

    response = client.post(
        f"/invitation/{invitation.id}", data={'action': 'accept'})
    assert response.status_code == 302
    assert response.location.endswith(f"/event/{event.id}")

    response = client.get(response.location)
    assert b"You have accepted the invitation" in response.data

    invitation = Invitation.query.get(invitation.id)
    assert invitation.status == 'accepted'

    response = client.post(
        f"/invitation/{invitation.id}", data={'action': 'decline'})
    assert response.status_code == 302
    assert response.location.endswith(f"/home")

    response = client.get(response.location)
    assert b"You have declined the invitation" in response.data

    invitation = Invitation.query.get(invitation.id)
    assert invitation.status == 'declined'


# TEST FOR INVITE_TO_EVENT
def test_invite_to_event(client, init_database, auth):
    auth.login()
    event = Event.query.first()

    assert event.organizer_id == User.query.first().id
    invite_data = {
        'invite_method': 'email',
        'guest_email': 'test3@example.com'
    }

    response = client.post(f"/event/{event.id}/invite", data=invite_data)
    assert response.status_code == 302
    assert response.location.endswith(f"/event/{event.id}")

    response = client.get(response.location)
    assert b'1 invitations are send.' in response.data
    invitation = Invitation.query.filter_by(
        event_id=event.id, recipient_email='test3@example.com').first()
    assert invitation is not None

    another_user = User.query.filter_by(email='test2@example.com').first()
    auth.logout()
    auth.login(another_user.email)

    response = client.post(f"/event/{event.id}/invite", data=invite_data)
    assert response.status_code == 302
    assert response.location.endswith(f"/event/{event.id}")


# TEST FOR ADD_COMMENT
def test_add_comment_logged_in(client, auth, sample_event):
    auth.login()
    event_id = sample_event.id
    response = client.post(
        f'/event/{event_id}/comment',
        data={'content': 'Great event!'},
        follow_redirects=True
    )
    assert b'Great event!' in response.data
    assert b'Comments:' in response.data


def test_add_comment_not_invited(client, auth, sample_event, another_user):
    auth.login(another_user.email)

    event_id = sample_event.id
    response = client.post(
        f'/event/{event_id}/comment',
        data={'content': 'I can\'t wait for this event!'},
        follow_redirects=True
    )

    assert b'You need to accept the invitation to comment on this event.' in response.data


# TEST FOR TASKS
def test_add_task_as_organizer(client, auth, sample_event):
    auth.login()
    event_id = sample_event.id
    response = client.post(
        f'/event/{event_id}/add-task',
        data={'task_title': 'Prepare the venue'},
        follow_redirects=True
    )
    assert b'Task added successfully!' in response.data


def test_add_task_not_organizer(client, auth, sample_event, another_user):
    auth.login(another_user.email, 'password')

    event_id = sample_event.id
    response = client.post(
        f'/event/{event_id}/add-task',
        data={'task_title': 'Prepare the venue'},
        follow_redirects=True
    )

    assert b'You are not the organizer of this event to add tasks.' in response.data


def test_delete_task_as_organizer(client, auth, sample_event):
    auth.login()

    task = Task.query.filter_by(event_id=sample_event.id).first()
    if not task:
        task = Task(
            title="Sample Task",
            event_id=sample_event.id,
            user_id=sample_event.organizer_id)
        db.session.add(task)
        db.session.commit()

    response = client.post(
        f'/task/{task.id}/delete',
        follow_redirects=True
    )

    deleted_task = Task.query.filter_by(id=task.id).first()
    assert deleted_task is None, "Задачата не беше изтрита успешно"


def test_toggle_task_completion_as_organizer(client, auth, sample_event):
    auth.login()

    task = Task.query.filter_by(event_id=sample_event.id).first()
    if not task:
        task = Task(
            title="Sample Task",
            event_id=sample_event.id,
            user_id=sample_event.organizer_id)
        db.session.add(task)
        db.session.commit()

    response = client.post(
        f'/task/{task.id}/toggle',
        follow_redirects=True
    )

    assert response.status_code == 200
    assert task.completed

