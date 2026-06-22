from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from models import db, User

auth_bp = Blueprint('auth', __name__)


def _send_verification_email(user):
    app = current_app._get_current_object()
    token = user.generate_verification_token()
    db.session.commit()
    base_url = app.config.get('APP_BASE_URL', request.host_url.rstrip('/'))
    verify_url = f"{base_url}{url_for('auth.verify_email', token=token)}"
    try:
        mail = Mail(app)
        msg = Message(
            subject='Verify your ArchiveHumanity account',
            sender=('ArchiveHumanity', app.config.get('MAIL_USERNAME', '')),
            recipients=[user.email],
        )
        msg.body = (
            f'Hi {user.name},\n\n'
            f'Thanks for signing up for ArchiveHumanity. Please verify your email address by clicking the link below:\n\n'
            f'{verify_url}\n\n'
            f'This link expires in 24 hours.\n\n'
            f'The ArchiveHumanity Team'
        )
        mail.send(msg)
        return True
    except Exception:
        return False


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not all([name, email, password]):
            flash('All fields are required.', 'error')
            return render_template('auth/register.html')

        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html')

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'error')
            return render_template('auth/register.html')

        user = User(name=name, email=email, is_verified=False)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        sent = _send_verification_email(user)

        invite_token = request.args.get('invite')
        if invite_token:
            return redirect(url_for('auth.verify_pending', email=email, invite=invite_token))

        return redirect(url_for('auth.verify_pending', email=email))

    return render_template('auth/register.html', invite=request.args.get('invite'))


@auth_bp.route('/verify-pending')
def verify_pending():
    email = request.args.get('email', '')
    return render_template('auth/verify_pending.html', email=email)


@auth_bp.route('/verify/<token>')
def verify_email(token):
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        flash('Invalid or expired verification link.', 'error')
        return redirect(url_for('auth.login'))

    if user.verification_token_expires < datetime.utcnow():
        flash('This verification link has expired. Please request a new one.', 'error')
        return redirect(url_for('auth.resend_verification_page', email=user.email))

    user.is_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    db.session.commit()

    invite_token = request.args.get('invite')
    login_user(user)
    flash('Email verified! Welcome to ArchiveHumanity.', 'success')

    if invite_token:
        return redirect(url_for('memorial.accept_invite', token=invite_token))
    return redirect(url_for('dashboard.index'))


@auth_bp.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification_page():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and not user.is_verified:
            _send_verification_email(user)
        flash('If that email is registered and unverified, a new link has been sent.', 'info')
        return redirect(url_for('auth.verify_pending', email=email))

    email = request.args.get('email', '')
    return render_template('auth/resend_verification.html', email=email)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if not user.is_verified:
                flash('Please verify your email before logging in.', 'warning')
                return redirect(url_for('auth.verify_pending', email=email))
            login_user(user, remember=request.form.get('remember') == 'on')
            next_url = request.args.get('next') or url_for('dashboard.index')
            return redirect(next_url)

        flash('Invalid email or password.', 'error')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.landing'))
