from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_mail import Mail, Message

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def landing():
    return render_template('landing.html')


@main_bp.route('/about')
def about():
    return render_template('about.html')


@main_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        message = request.form.get('message', '').strip()

        if not all([name, email, message]):
            flash('Please fill out all fields.', 'error')
            return render_template('contact.html')

        app = current_app._get_current_object()
        try:
            mail = Mail(app)
            msg = Message(
                subject=f'ArchiveHumanity contact: {name}',
                sender=('ArchiveHumanity', app.config.get('MAIL_USERNAME', '')),
                recipients=[app.config.get('MAIL_USERNAME', '')],
                reply_to=email,
            )
            msg.body = f"From: {name} <{email}>\n\n{message}"
            mail.send(msg)
            flash('Message sent. We\'ll get back to you soon.', 'success')
        except Exception:
            flash('Could not send your message right now. Please try emailing us directly.', 'error')

        return redirect(url_for('main.contact'))

    return render_template('contact.html')
