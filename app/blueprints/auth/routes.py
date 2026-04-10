from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.blueprints.auth import auth_bp
from app.blueprints.auth.forms import RegisterForm, LoginForm
from app.extensions import db, oauth
from app.models.user import User


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data.lower(),
            display_name=form.display_name.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Welcome to EventPlanner.AI!', 'success')
        return redirect(url_for('dashboard.index'))

    return render_template('auth/register.html', form=form)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            flash('Welcome back!', 'success')
            return redirect(next_page or url_for('dashboard.index'))
        flash('Invalid email or password.', 'danger')

    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/google')
def google_login():
    if not oauth.google.client_id:
        flash('Google sign-in is not configured.', 'warning')
        return redirect(url_for('auth.login'))
    redirect_uri = url_for('auth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route('/google/callback')
def google_callback():
    try:
        token = oauth.google.authorize_access_token()
    except Exception as e:
        flash(f'Google sign-in failed: {str(e)}', 'danger')
        return redirect(url_for('auth.login'))

    user_info = token.get('userinfo')
    if not user_info:
        flash('Could not retrieve Google account information.', 'danger')
        return redirect(url_for('auth.login'))

    google_id = user_info.get('sub')
    email = user_info.get('email', '').lower()
    name = user_info.get('name', email.split('@')[0])
    picture = user_info.get('picture')

    if not google_id or not email:
        flash('Google account is missing required information.', 'danger')
        return redirect(url_for('auth.login'))

    # Look up by google_id, then by email (link existing accounts)
    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        user = User.query.filter_by(email=email).first()
        if user:
            # Link Google account to existing email-based user
            user.google_id = google_id
            if picture and not user.avatar_url:
                user.avatar_url = picture
        else:
            # Create new user
            user = User(
                email=email,
                display_name=name,
                google_id=google_id,
                avatar_url=picture,
            )
            db.session.add(user)
        db.session.commit()

    login_user(user)
    flash(f'Welcome, {user.display_name}!', 'success')
    return redirect(url_for('dashboard.index'))
