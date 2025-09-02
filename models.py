from datetime import datetime, timedelta
from app import db
from flask_login import UserMixin
from sqlalchemy import func

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reports = db.relationship('Report', backref='service', lazy=True, cascade='all, delete-orphan')
    
    def get_status(self):
        """Determine service status based on recent reports"""
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        
        # Count reports in the last hour
        recent_reports = Report.query.filter(
            Report.service_id == self.id,
            Report.timestamp >= one_hour_ago
        ).count()
        
        # If more than 5 reports in the last hour, consider it down
        if recent_reports >= 5:
            return 'down'
        elif recent_reports >= 2:
            return 'issues'
        else:
            return 'up'
    
    def get_recent_reports_count(self, hours=24):
        """Get count of reports in the last N hours"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return Report.query.filter(
            Report.service_id == self.id,
            Report.timestamp >= cutoff
        ).count()

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    location = db.Column(db.String(100))
    description = db.Column(db.Text)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    user_ip = db.Column(db.String(45))  # To prevent spam
    
    def to_dict(self):
        return {
            'id': self.id,
            'service_id': self.service_id,
            'timestamp': self.timestamp.isoformat(),
            'location': self.location,
            'description': self.description,
            'latitude': self.latitude,
            'longitude': self.longitude
        }
