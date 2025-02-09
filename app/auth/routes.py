""" Module for user registration, login, and logout functionality."""
import os
from flask import current_app, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, current_user, login_required, logout_user
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from app import db
from app.forms import RegistrationForm, LoginForm
from app.models import User, Invitation
from app.auth import auth


@auth.route('/register', methods=['GET', 'POST'])
def register():
    """User registration with username, email, password, first name,
    last name, and profile picture."""
    if current_user.is_authenticated:
        flash('You are already registered and logged in.', 'info')
        return redirect(url_for('index.home'))

    form = RegistrationForm()
    if form.validate_on_submit():
        existing_username = User.query.filter_by(
            username=form.username.data).first()
        if User.query.filter_by(username=form.username.data).first():
            flash('This username is already taken.', 'danger')
            return redirect(url_for('auth.register'))

        existing_email = User.query.filter_by(email=form.email.data).first()
        if existing_email:
            flash('This email is already registered.', 'danger')
        if existing_username or existing_email:
            return render_template('register.html', form=form)

        profile_picture = form.profile_picture.data
        picture_filename = 'default_profile.jpg'

        if profile_picture:
            picture_filename = secure_filename(profile_picture.filename)
            picture_path = os.path.join(
                current_app.root_path,
                'static',
                'profile_pictures',
                picture_filename)
            if not os.path.exists(os.path.dirname(picture_path)):
                os.makedirs(os.path.dirname(picture_path))
            profile_picture.save(picture_path)

        hashed_password = generate_password_hash(form.password.data)
        new_user = User(
            username=form.username.data,
            email=form.email.data,
            password=hashed_password,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            profile_picture=picture_filename
        )
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)

        invitations = Invitation.query.filter_by(
            recipient_email=new_user.email).all()
        for invitation in invitations:
            invitation.recipient_id = new_user.id
        db.session.commit()

        next_page = request.args.get('next')
        return redirect(next_page) if next_page else redirect(
            url_for('index.home'))

    return render_template('register.html', form=form)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    """User login with username and password."""
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        next_page = request.args.get('next')
        return redirect(next_page or url_for('index.index_route'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.verify_password(form.password.data):
            login_user(user)

            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(
                url_for('index.home'))

        flash('Invalid username or password', 'danger')
        return render_template('login.html', form=form)

    return render_template('login.html', form=form)


@auth.route('/logout')
@login_required
def logout():
    """Logs the user out, clears the session, and redirects to the homepage.
    Clears browser cache headers to ensure proper redirection."""
    logout_user()
    session.clear()
    flash('You have been logged out', 'success')
    response = redirect(url_for('index.index_route'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response
