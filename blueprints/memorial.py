import re
from datetime import datetime
from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, abort, current_app, send_file)
from flask_login import login_required, current_user
from models import (db, Memorial, MemorialPhoto, Memory, MemorialCollaborator,
                    CollaboratorInvite, FamilyLink, User, RELATION_TYPES)
from services.cloudinary_service import upload_photo, delete_photo
from services.qr_service import generate_qr_png
from flask_mail import Message
import io

memorial_bp = Blueprint('memorial', __name__)


def _slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text


def _unique_slug(base):
    slug = base
    n = 1
    while Memorial.query.filter_by(slug=slug).first():
        slug = f'{base}-{n}'
        n += 1
    return slug


# ── Public memorial page ──────────────────────────────────────────────────────

@memorial_bp.route('/m/<slug>')
def public(slug):
    memorial = Memorial.query.filter_by(slug=slug, is_published=True).first_or_404()
    approved_memories = [m for m in memorial.memories if m.is_approved]
    return render_template('memorial/public.html', memorial=memorial, memories=approved_memories)


@memorial_bp.route('/m/<slug>/tribute', methods=['POST'])
def submit_memory(slug):
    memorial = Memorial.query.filter_by(slug=slug, is_published=True).first_or_404()

    author_name = request.form.get('author_name', '').strip()
    relationship = request.form.get('relationship', '').strip()
    content = request.form.get('content', '').strip()

    if not author_name or not content:
        flash('Please provide your name and a message.', 'error')
        return redirect(url_for('memorial.public', slug=slug))

    memory = Memory(
        memorial_id=memorial.id,
        author_name=author_name,
        relationship_to_deceased=relationship or None,
        content=content,
        is_approved=False,
    )
    db.session.add(memory)
    db.session.commit()
    flash('Thank you for your tribute. It will appear once approved by the family.', 'success')
    return redirect(url_for('memorial.public', slug=slug) + '#tributes')


# ── Create ────────────────────────────────────────────────────────────────────

@memorial_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        first = request.form.get('first_name', '').strip()
        last = request.form.get('last_name', '').strip()

        if not first or not last:
            flash('First and last name are required.', 'error')
            return render_template('memorial/create.html')

        base_slug = _slugify(f'{first}-{last}')
        slug = _unique_slug(base_slug)

        memorial = Memorial(
            slug=slug,
            owner_id=current_user.id,
            first_name=first,
            last_name=last,
        )
        _apply_form_fields(memorial, request.form)
        db.session.add(memorial)
        db.session.commit()

        flash('Memorial created. Finish setting it up below.', 'success')
        return redirect(url_for('memorial.edit', slug=slug))

    return render_template('memorial/create.html')


# ── Edit ──────────────────────────────────────────────────────────────────────

@memorial_bp.route('/edit/<slug>', methods=['GET', 'POST'])
@login_required
def edit(slug):
    memorial = Memorial.query.filter_by(slug=slug).first_or_404()
    if not memorial.can_edit(current_user):
        abort(403)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'save_details':
            _apply_form_fields(memorial, request.form)
            memorial.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Details saved.', 'success')

        elif action == 'upload_profile_photo':
            file = request.files.get('profile_photo')
            if file and file.filename:
                if memorial.profile_photo_public_id:
                    delete_photo(memorial.profile_photo_public_id)
                url, pid = upload_photo(file.stream, folder='memorials/profiles',
                                        transformation=[{'width': 800, 'crop': 'limit'}])
                memorial.profile_photo_url = url
                memorial.profile_photo_public_id = pid
                db.session.commit()
                flash('Profile photo updated.', 'success')

        elif action == 'upload_photo':
            file = request.files.get('photo')
            if file and file.filename:
                url, pid = upload_photo(file.stream, folder='memorials/gallery',
                                        transformation=[{'width': 1600, 'crop': 'limit'}])
                caption = request.form.get('caption', '').strip() or None
                year_raw = request.form.get('year', '').strip()
                year = int(year_raw) if year_raw.isdigit() else None
                photo = MemorialPhoto(
                    memorial_id=memorial.id,
                    url=url,
                    public_id=pid,
                    caption=caption,
                    year=year,
                    order=len(memorial.photos),
                )
                db.session.add(photo)
                db.session.commit()
                flash('Photo added.', 'success')

        elif action == 'delete_photo':
            photo_id = request.form.get('photo_id')
            photo = MemorialPhoto.query.get(photo_id)
            if photo and photo.memorial_id == memorial.id:
                delete_photo(photo.public_id)
                db.session.delete(photo)
                db.session.commit()
                flash('Photo removed.', 'success')

        elif action == 'add_family_link':
            relation_types_in = request.form.getlist('relation_type[]')
            link_slugs_in = request.form.getlist('linked_slug[]')
            link_names_in = request.form.getlist('linked_name[]')

            added = 0
            for i, rt in enumerate(relation_types_in):
                if rt not in RELATION_TYPES:
                    continue
                ls = link_slugs_in[i].strip() if i < len(link_slugs_in) else ''
                ln = link_names_in[i].strip() if i < len(link_names_in) else ''
                if not ls and not ln:
                    continue
                linked_id = None
                if ls:
                    linked = Memorial.query.filter_by(slug=ls).first()
                    if linked:
                        linked_id = linked.id
                    else:
                        flash(f'No memorial found with slug "{ls}".', 'error')
                        continue
                db.session.add(FamilyLink(
                    memorial_id=memorial.id,
                    relation_type=rt,
                    linked_memorial_id=linked_id,
                    linked_name=ln if not linked_id else None,
                ))
                added += 1

            if added:
                db.session.commit()
                flash(f'{added} family member{"s" if added > 1 else ""} added.', 'success')
            return redirect(url_for('memorial.edit', slug=slug, _anchor='family'))

        elif action == 'delete_family_link':
            link_id = request.form.get('link_id')
            link = FamilyLink.query.get(link_id)
            if link and link.memorial_id == memorial.id:
                db.session.delete(link)
                db.session.commit()
                flash('Family link removed.', 'success')

        elif action == 'approve_memory':
            memory_id = request.form.get('memory_id')
            memory = Memory.query.get(memory_id)
            if memory and memory.memorial_id == memorial.id:
                memory.is_approved = True
                db.session.commit()
                flash('Tribute approved.', 'success')

        elif action == 'delete_memory':
            memory_id = request.form.get('memory_id')
            memory = Memory.query.get(memory_id)
            if memory and memory.memorial_id == memorial.id:
                db.session.delete(memory)
                db.session.commit()
                flash('Tribute deleted.', 'success')

        elif action == 'toggle_published':
            memorial.is_published = not memorial.is_published
            db.session.commit()
            state = 'published' if memorial.is_published else 'unpublished'
            flash(f'Memorial {state}.', 'success')

        elif action == 'invite_collaborator':
            _handle_invite(memorial, request, current_app)

        return redirect(url_for('memorial.edit', slug=slug))

    pending_memories = [m for m in memorial.memories if not m.is_approved]
    approved_memories = [m for m in memorial.memories if m.is_approved]
    return render_template('memorial/edit.html',
                           memorial=memorial,
                           pending_memories=pending_memories,
                           approved_memories=approved_memories,
                           relation_types=RELATION_TYPES)


def _apply_form_fields(memorial, form):
    memorial.first_name = form.get('first_name', memorial.first_name).strip()
    memorial.last_name = form.get('last_name', memorial.last_name).strip()
    memorial.epitaph = form.get('epitaph', '').strip() or None
    memorial.biography = form.get('biography', '').strip() or None
    memorial.birth_place = form.get('birth_place', '').strip() or None
    memorial.death_place = form.get('death_place', '').strip() or None
    memorial.cemetery_name = form.get('cemetery_name', '').strip() or None
    memorial.cemetery_location = form.get('cemetery_location', '').strip() or None
    memorial.plot_section = form.get('plot_section', '').strip() or None
    memorial.plot_number = form.get('plot_number', '').strip() or None

    birth_raw = form.get('birth_date', '').strip()
    death_raw = form.get('death_date', '').strip()
    if birth_raw:
        try:
            memorial.birth_date = datetime.strptime(birth_raw, '%Y-%m-%d').date()
        except ValueError:
            pass
    if death_raw:
        try:
            memorial.death_date = datetime.strptime(death_raw, '%Y-%m-%d').date()
        except ValueError:
            pass


def _handle_invite(memorial, request, app):
    from flask_mail import Mail
    email = request.form.get('invite_email', '').strip().lower()
    if not email:
        flash('Please enter an email address.', 'error')
        return

    if CollaboratorInvite.query.filter_by(memorial_id=memorial.id, email=email, accepted=False).first():
        flash('An invite has already been sent to that address.', 'error')
        return

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        if any(c.user_id == existing_user.id for c in memorial.collaborators):
            flash('That person already has access.', 'error')
            return

    invite = CollaboratorInvite(
        memorial_id=memorial.id,
        email=email,
        invited_by=current_user.id,
    )
    db.session.add(invite)
    db.session.commit()

    base_url = app.config.get('APP_BASE_URL', request.host_url.rstrip('/'))
    invite_url = f"{base_url}{url_for('memorial.accept_invite', token=invite.token)}"

    try:
        mail = Mail(app)
        msg = Message(
            subject=f'You\'ve been invited to co-manage a memorial for {memorial.full_name}',
            recipients=[email],
        )
        msg.body = (
            f'Hi,\n\n'
            f'{current_user.name} has invited you to help manage the memorial for '
            f'{memorial.full_name} on EternalQR.\n\n'
            f'Click the link below to accept:\n{invite_url}\n\n'
            f'This link expires in 7 days.\n\nThe EternalQR Team'
        )
        mail.send(msg)
        flash(f'Invite sent to {email}.', 'success')
    except Exception:
        flash(f'Invite saved but email could not be sent. Share this link manually: {invite_url}', 'warning')


@memorial_bp.route('/invite/<token>')
def accept_invite(token):
    invite = CollaboratorInvite.query.filter_by(token=token, accepted=False).first_or_404()
    if invite.is_expired:
        flash('This invite link has expired.', 'error')
        return redirect(url_for('main.landing'))

    if not current_user.is_authenticated:
        existing = User.query.filter_by(email=invite.email).first()
        if existing:
            flash('Please log in to accept this invite.', 'info')
            return redirect(url_for('auth.login', next=url_for('memorial.accept_invite', token=token)))
        flash('Create an account to accept this invite.', 'info')
        return redirect(url_for('auth.register', invite=token))

    if current_user.email != invite.email:
        flash('This invite was sent to a different email address.', 'error')
        return redirect(url_for('dashboard.index'))

    invite.accepted = True
    collab = MemorialCollaborator(memorial_id=invite.memorial_id, user_id=current_user.id)
    db.session.add(collab)
    db.session.commit()

    flash(f'You now have access to the memorial for {invite.memorial.full_name}.', 'success')
    return redirect(url_for('memorial.edit', slug=invite.memorial.slug))


# ── QR code ───────────────────────────────────────────────────────────────────

@memorial_bp.route('/edit/<slug>/qr')
@login_required
def qr_page(slug):
    memorial = Memorial.query.filter_by(slug=slug).first_or_404()
    if not memorial.can_edit(current_user):
        abort(403)
    base_url = current_app.config.get('APP_BASE_URL', request.host_url.rstrip('/'))
    qr_url = f"{base_url}{url_for('memorial.public', slug=slug)}"
    return render_template('memorial/qr.html', memorial=memorial, qr_url=qr_url)


@memorial_bp.route('/edit/<slug>/qr/image')
@login_required
def qr_image(slug):
    """Serve the QR PNG inline (for display in the browser)."""
    memorial = Memorial.query.filter_by(slug=slug).first_or_404()
    if not memorial.can_edit(current_user):
        abort(403)
    base_url = current_app.config.get('APP_BASE_URL', request.host_url.rstrip('/'))
    qr_url = f"{base_url}{url_for('memorial.public', slug=slug)}"
    png_bytes = generate_qr_png(qr_url)
    return send_file(io.BytesIO(png_bytes), mimetype='image/png')


@memorial_bp.route('/edit/<slug>/qr/download')
@login_required
def qr_download(slug):
    memorial = Memorial.query.filter_by(slug=slug).first_or_404()
    if not memorial.can_edit(current_user):
        abort(403)
    base_url = current_app.config.get('APP_BASE_URL', request.host_url.rstrip('/'))
    qr_url = f"{base_url}{url_for('memorial.public', slug=slug)}"
    png_bytes = generate_qr_png(qr_url)
    return send_file(
        io.BytesIO(png_bytes),
        mimetype='image/png',
        as_attachment=True,
        download_name=f'qr-{slug}.png',
    )
