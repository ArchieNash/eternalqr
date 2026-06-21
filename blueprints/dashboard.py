from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import Memorial, MemorialCollaborator

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
@login_required
def index():
    owned = Memorial.query.filter_by(owner_id=current_user.id).order_by(Memorial.created_at.desc()).all()

    collab_ids = [c.memorial_id for c in MemorialCollaborator.query.filter_by(user_id=current_user.id).all()]
    collaborating = Memorial.query.filter(
        Memorial.id.in_(collab_ids),
        Memorial.owner_id != current_user.id,
    ).order_by(Memorial.created_at.desc()).all()

    return render_template('dashboard/index.html', owned=owned, collaborating=collaborating)
