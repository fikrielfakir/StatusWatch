import os
import logging
from datetime import datetime, timedelta
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
socketio = SocketIO(cors_allowed_origins="*")
login_manager = LoginManager()

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///downdetector.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize extensions
db.init_app(app)
socketio.init_app(app, async_mode='eventlet')
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

with app.app_context():
    # Import models
    import models
    
    # Create all tables
    db.create_all()
    
    # Create default admin user if not exists
    from werkzeug.security import generate_password_hash
    admin = models.User.query.filter_by(username='admin').first()
    if not admin:
        admin_user = models.User(
            username='admin',
            email='admin@downdetector.com',
            password_hash=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin_user)
        db.session.commit()
        logging.info("Default admin user created: admin/admin123")
    
    # Create default services if none exist
    if models.Service.query.count() == 0:
        default_services = [
            {'name': 'WhatsApp', 'url': 'https://whatsapp.com', 'icon_path': 'images/logos/WhatsApp_logo_icon.png'},
            {'name': 'Instagram', 'url': 'https://instagram.com', 'icon_path': 'images/logos/Instagram_logo_icon.png'},
            {'name': 'Facebook', 'url': 'https://facebook.com', 'icon_path': 'images/logos/Facebook_logo_icon.png'},
            {'name': 'Twitter', 'url': 'https://twitter.com', 'icon_path': 'images/logos/Twitter_X_logo_icon.png'},
            {'name': 'YouTube', 'url': 'https://youtube.com', 'icon_path': 'images/logos/YouTube_logo_icon.png'},
            {'name': 'Gmail', 'url': 'https://gmail.com', 'icon_path': 'images/logos/Gmail_logo_icon.png'},
            {'name': 'Discord', 'url': 'https://discord.com', 'icon_path': 'images/logos/Discord_logo_icon.png'},
            {'name': 'TikTok', 'url': 'https://tiktok.com', 'icon_path': 'images/logos/TikTok_logo_icon.png'},
            {'name': 'LinkedIn', 'url': 'https://linkedin.com', 'icon_path': 'images/logos/LinkedIn_logo_icon.png'},
            {'name': 'Snapchat', 'url': 'https://snapchat.com', 'icon_path': 'images/logos/Snapchat_logo_icon.png'},
            {'name': 'Reddit', 'url': 'https://reddit.com', 'icon_path': 'images/logos/Reddit_logo_icon.png'},
            {'name': 'Spotify', 'url': 'https://spotify.com', 'icon_path': 'images/logos/Spotify_logo_icon.png'},
        ]
        
        for service_data in default_services:
            service = models.Service(
                name=service_data['name'],
                url=service_data['url'],
                icon_path=service_data.get('icon_path')
            )
            db.session.add(service)
        
        db.session.commit()
        logging.info("Default services created")

# Import routes
import routes
import auth

# Register blueprints
app.register_blueprint(routes.bp)
app.register_blueprint(auth.bp)

@login_manager.user_loader
def load_user(user_id):
    return models.User.query.get(int(user_id))

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
