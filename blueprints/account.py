from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db

account_bp = Blueprint('account', __name__)


@account_bp.route('/account', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_profile':
            name = request.form.get('name', '').strip()
            if not name:
                flash('Name cannot be empty.', 'error')
            else:
                current_user.name = name
                db.session.commit()
                flash('Name updated.', 'success')

        elif action == 'change_password':
            current_pw = request.form.get('current_password', '')
            new_pw = request.form.get('new_password', '')
            confirm_pw = request.form.get('confirm_password', '')

            if not current_user.check_password(current_pw):
                flash('Current password is incorrect.', 'error')
            elif len(new_pw) < 8:
                flash('New password must be at least 8 characters.', 'error')
            elif new_pw != confirm_pw:
                flash('New passwords do not match.', 'error')
            else:
                current_user.set_password(new_pw)
                db.session.commit()
                flash('Password updated.', 'success')

        return redirect(url_for('account.index'))

    return render_template('account/index.html')
