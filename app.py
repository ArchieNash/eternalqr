import os
from flask import Flask, render_template, request
from flask_login import LoginManager, login_user, current_user
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

from models import db, User
from services.cloudinary_service import init_cloudinary
from blueprints.main import main_bp
from blueprints.auth import auth_bp
from blueprints.dashboard import dashboard_bp
from blueprints.memorial import memorial_bp
from blueprints.account import account_bp
from blueprints.support import support_bp

load_dotenv()

login_manager = LoginManager()
csrf = CSRFProtect()
mail = Mail()


def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.environ['FLASK_SECRET_KEY']
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL'].replace(
        'postgres://', 'postgresql://', 1
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['APP_BASE_URL'] = os.environ.get('APP_BASE_URL', '')
    app.config['STRIPE_SECRET_KEY'] = os.environ.get('STRIPE_SECRET_KEY', '')
    app.config['STRIPE_PUBLISHABLE_KEY'] = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')

    app.config['CLOUDINARY_CLOUD_NAME'] = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
    app.config['CLOUDINARY_API_KEY'] = os.environ.get('CLOUDINARY_API_KEY', '')
    app.config['CLOUDINARY_API_SECRET'] = os.environ.get('CLOUDINARY_API_SECRET', '')

    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', '')

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to continue.'
    login_manager.login_message_category = 'info'

    if app.config['CLOUDINARY_CLOUD_NAME']:
        init_cloudinary(app)

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(memorial_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(support_bp)

    # Demo mode: auto-login as a fixed user so reviewers can access the full site.
    # Enable by setting DEMO_USER_EMAIL in environment. Remove when done.
    demo_email = os.environ.get('DEMO_USER_EMAIL', '')
    if demo_email:
        @app.before_request
        def auto_login():
            if not current_user.is_authenticated and request.endpoint not in ('static',):
                user = User.query.filter_by(email=demo_email).first()
                if user:
                    login_user(user, remember=True)

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    with app.app_context():
        db.create_all()
        from sqlalchemy import text
        migrations = [
            'ALTER TABLE family_links ADD COLUMN is_living BOOLEAN NOT NULL DEFAULT false',
            'ALTER TABLE users ADD COLUMN is_verified BOOLEAN NOT NULL DEFAULT true',
            'ALTER TABLE users ADD COLUMN verification_token VARCHAR(100)',
            'ALTER TABLE users ADD COLUMN verification_token_expires TIMESTAMP',
        ]
        for sql in migrations:
            try:
                with db.engine.connect() as conn:
                    conn.execute(text(sql))
                    conn.commit()
            except Exception:
                pass

    return app


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, port=port)
