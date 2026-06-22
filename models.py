from datetime import datetime, timedelta
import secrets
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy.orm import DeclarativeBase
from werkzeug.security import generate_password_hash, check_password_hash


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    owned_memorials = db.relationship('Memorial', backref='owner', lazy=True, foreign_keys='Memorial.owner_id')
    collaborations = db.relationship('MemorialCollaborator', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Memorial(db.Model):
    __tablename__ = 'memorials'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    birth_date = db.Column(db.Date)
    death_date = db.Column(db.Date)
    birth_place = db.Column(db.String(255))
    death_place = db.Column(db.String(255))

    biography = db.Column(db.Text)
    epitaph = db.Column(db.String(500))

    profile_photo_url = db.Column(db.String(500))
    profile_photo_public_id = db.Column(db.String(255))

    cemetery_name = db.Column(db.String(255))
    cemetery_location = db.Column(db.String(255))
    plot_section = db.Column(db.String(50))
    plot_number = db.Column(db.String(50))

    is_published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    photos = db.relationship('MemorialPhoto', backref='memorial', lazy=True,
                             cascade='all, delete-orphan', order_by='MemorialPhoto.order')
    memories = db.relationship('Memory', backref='memorial', lazy=True,
                               cascade='all, delete-orphan', order_by='Memory.created_at.desc()')
    collaborators = db.relationship('MemorialCollaborator', backref='memorial', lazy=True,
                                    cascade='all, delete-orphan')
    family_links = db.relationship('FamilyLink', foreign_keys='FamilyLink.memorial_id',
                                   backref='memorial', lazy=True, cascade='all, delete-orphan')

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def age(self):
        if self.birth_date and self.death_date:
            return self.death_date.year - self.birth_date.year
        return None

    @property
    def years_display(self):
        b = self.birth_date.year if self.birth_date else '?'
        d = self.death_date.year if self.death_date else '?'
        return f'{b} – {d}'

    def can_edit(self, user):
        if user.id == self.owner_id:
            return True
        return any(c.user_id == user.id for c in self.collaborators)


class MemorialPhoto(db.Model):
    __tablename__ = 'memorial_photos'

    id = db.Column(db.Integer, primary_key=True)
    memorial_id = db.Column(db.Integer, db.ForeignKey('memorials.id'), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    public_id = db.Column(db.String(255))
    caption = db.Column(db.String(255))
    year = db.Column(db.Integer)
    order = db.Column(db.Integer, default=0)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class Memory(db.Model):
    """A tribute left by a visitor scanning the QR code."""
    __tablename__ = 'memories'

    id = db.Column(db.Integer, primary_key=True)
    memorial_id = db.Column(db.Integer, db.ForeignKey('memorials.id'), nullable=False)
    author_name = db.Column(db.String(100), nullable=False)
    relationship_to_deceased = db.Column(db.String(100))
    content = db.Column(db.Text, nullable=False)
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MemorialCollaborator(db.Model):
    __tablename__ = 'memorial_collaborators'

    id = db.Column(db.Integer, primary_key=True)
    memorial_id = db.Column(db.Integer, db.ForeignKey('memorials.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)


class CollaboratorInvite(db.Model):
    __tablename__ = 'collaborator_invites'

    id = db.Column(db.Integer, primary_key=True)
    memorial_id = db.Column(db.Integer, db.ForeignKey('memorials.id'), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(32))
    invited_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    accepted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(days=7))

    memorial = db.relationship('Memorial')
    inviter = db.relationship('User')

    @property
    def is_expired(self):
        return datetime.utcnow() > self.expires_at


RELATION_TYPES = ['spouse', 'parent', 'child', 'sibling']
RELATION_LABELS = {
    'spouse': 'Spouse',
    'parent': 'Parent',
    'child': 'Child',
    'sibling': 'Sibling',
}


class FamilyLink(db.Model):
    """A family relationship from this memorial to another person."""
    __tablename__ = 'family_links'

    id = db.Column(db.Integer, primary_key=True)
    memorial_id = db.Column(db.Integer, db.ForeignKey('memorials.id'), nullable=False)
    relation_type = db.Column(db.String(50), nullable=False)

    # Link to another memorial on the platform (optional)
    linked_memorial_id = db.Column(db.Integer, db.ForeignKey('memorials.id'), nullable=True)
    # Fallback: just a name if not on the platform
    linked_name = db.Column(db.String(200))
    is_living = db.Column(db.Boolean, default=False, server_default='false', nullable=False)

    linked_memorial = db.relationship('Memorial', foreign_keys=[linked_memorial_id])

    @property
    def display_name(self):
        if self.linked_memorial:
            return self.linked_memorial.full_name
        return self.linked_name or 'Unknown'

    @property
    def label(self):
        return RELATION_LABELS.get(self.relation_type, self.relation_type.capitalize())
