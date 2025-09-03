import os
import logging
from datetime import datetime, timedelta
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_compress import Compress

# Configure logging
logging.basicConfig(level=logging.INFO)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
socketio = SocketIO(cors_allowed_origins="*", async_mode='gevent', logger=False, engineio_logger=False)
login_manager = LoginManager()

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Enable compression for better performance
compress = Compress(app)

# Configure static file caching
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1 year cache for static files

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///downdetector.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize extensions
db.init_app(app)
socketio.init_app(app, async_mode='gevent', cors_allowed_origins="*")
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
    
    # Create default service types if none exist
    if hasattr(models, 'ServiceType') and models.ServiceType.query.count() == 0:
        default_types = [
            {'name': 'Social Media', 'description': 'Social networking platforms', 'icon_class': 'fas fa-users'},
            {'name': 'Email & Communication', 'description': 'Email and messaging services', 'icon_class': 'fas fa-envelope'},
            {'name': 'Entertainment', 'description': 'Video and music streaming', 'icon_class': 'fas fa-play'},
        ]
        
        for type_data in default_types:
            service_type = models.ServiceType(
                name=type_data['name'],
                description=type_data['description'],
                icon_class=type_data.get('icon_class')
            )
            db.session.add(service_type)
        
        db.session.commit()
        logging.info("Default service types created")
    
    # Get default service type
    social_media_type = None
    email_type = None
    entertainment_type = None
    
    if hasattr(models, 'ServiceType'):
        social_media_type = models.ServiceType.query.filter_by(name='Social Media').first()
        email_type = models.ServiceType.query.filter_by(name='Email & Communication').first()
        entertainment_type = models.ServiceType.query.filter_by(name='Entertainment').first()
    
    # Create default services if none exist
    if models.Service.query.count() == 0:
        default_services = [
            {'name': 'WhatsApp', 'url': 'https://whatsapp.com', 'icon_path': 'images/logos/WhatsApp_logo_icon.png', 'type': 'social'},
            {'name': 'Instagram', 'url': 'https://instagram.com', 'icon_path': 'images/logos/Instagram_logo_icon.png', 'type': 'social'},
            {'name': 'Facebook', 'url': 'https://facebook.com', 'icon_path': 'images/logos/Facebook_logo_icon.png', 'type': 'social'},
            {'name': 'Twitter', 'url': 'https://twitter.com', 'icon_path': 'images/logos/Twitter_X_logo_icon.png', 'type': 'social'},
            {'name': 'YouTube', 'url': 'https://youtube.com', 'icon_path': 'images/logos/YouTube_logo_icon.png', 'type': 'entertainment'},
            {'name': 'Gmail', 'url': 'https://gmail.com', 'icon_path': 'images/logos/Gmail_logo_icon.png', 'type': 'email'},
            {'name': 'Discord', 'url': 'https://discord.com', 'icon_path': 'images/logos/Discord_logo_icon.png', 'type': 'social'},
            {'name': 'TikTok', 'url': 'https://tiktok.com', 'icon_path': 'images/logos/TikTok_logo_icon.png', 'type': 'entertainment'},
            {'name': 'LinkedIn', 'url': 'https://linkedin.com', 'icon_path': 'images/logos/LinkedIn_logo_icon.png', 'type': 'social'},
            {'name': 'Snapchat', 'url': 'https://snapchat.com', 'icon_path': 'images/logos/Snapchat_logo_icon.png', 'type': 'social'},
            {'name': 'Reddit', 'url': 'https://reddit.com', 'icon_path': 'images/logos/Reddit_logo_icon.png', 'type': 'social'},
            {'name': 'Spotify', 'url': 'https://spotify.com', 'icon_path': 'images/logos/Spotify_logo_icon.png', 'type': 'entertainment'},
        ]
        
        for service_data in default_services:
            # Determine type_id based on service type
            type_id = 1  # Default fallback
            if hasattr(models, 'ServiceType'):
                if service_data.get('type') == 'social' and social_media_type:
                    type_id = social_media_type.id
                elif service_data.get('type') == 'email' and email_type:
                    type_id = email_type.id
                elif service_data.get('type') == 'entertainment' and entertainment_type:
                    type_id = entertainment_type.id
            
            service = models.Service(
                name=service_data['name'],
                url=service_data['url'],
                icon_path=service_data.get('icon_path'),
                type_id=type_id
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

# Start the service monitor
from monitor import monitor
monitor.start()

@login_manager.user_loader
def load_user(user_id):
    return models.User.query.get(int(user_id))

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
