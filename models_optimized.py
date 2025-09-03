from datetime import datetime, timedelta, timezone
import json
import ipaddress
import logging
from app import db
from flask_login import UserMixin
from sqlalchemy import func, text, desc, and_, or_, Index

# Setup logging
logger = logging.getLogger(__name__)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100))
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime(timezone=True))
    
    # Relationships
    favorites = db.relationship('UserFavorite', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    reports = db.relationship('OutageReport', backref='user', lazy='dynamic')

class ServiceType(db.Model):
    __tablename__ = 'service_types'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    icon_class = db.Column(db.String(50))
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    services = db.relationship('Service', backref='service_type', lazy='dynamic')
    subtypes = db.relationship('ServiceSubtype', backref='service_type', lazy='dynamic', cascade='all, delete-orphan')

class ServiceSubtype(db.Model):
    __tablename__ = 'service_subtypes'
    
    id = db.Column(db.Integer, primary_key=True)
    type_id = db.Column(db.Integer, db.ForeignKey('service_types.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    services = db.relationship('Service', backref='service_subtype', lazy='dynamic')
    
    __table_args__ = (db.UniqueConstraint('type_id', 'name', name='uq_type_subtype'),)

class NotificationChannel(db.Model):
    __tablename__ = 'notification_channels'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    type = db.Column(db.String(50), nullable=False)  # email, sms, webhook, push
    configuration = db.Column(db.JSON)  # Store channel-specific config
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    service_channels = db.relationship('ServiceChannel', backref='channel', lazy='dynamic', cascade='all, delete-orphan')

class Service(db.Model):
    __tablename__ = 'services'
    
    id = db.Column(db.Integer, primary_key=True)
    type_id = db.Column(db.Integer, db.ForeignKey('service_types.id'), nullable=False)
    subtype_id = db.Column(db.Integer, db.ForeignKey('service_subtypes.id'))
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    url = db.Column(db.String(500))
    company = db.Column(db.String(100))
    logo_url = db.Column(db.String(500))
    icon_path = db.Column(db.String(255))
    current_status = db.Column(db.String(20), default='up')  # up, issues, down
    last_checked = db.Column(db.DateTime(timezone=True))
    response_time = db.Column(db.Integer)  # in milliseconds
    is_active = db.Column(db.Boolean, default=True)
    priority = db.Column(db.Integer, default=1)  # 1=low, 2=medium, 3=high
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    reports = db.relationship('OutageReport', backref='service', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='service', lazy='dynamic', cascade='all, delete-orphan')
    favorites = db.relationship('UserFavorite', backref='service', lazy='dynamic', cascade='all, delete-orphan')
    service_channels = db.relationship('ServiceChannel', backref='service', lazy='dynamic', cascade='all, delete-orphan')
    outage_events = db.relationship('OutageEvent', backref='service', lazy='dynamic')
    
    # Indexes
    __table_args__ = (
        Index('idx_services_name', 'name'),
        Index('idx_services_type_id', 'type_id'),
        Index('idx_services_status', 'current_status'),
        Index('idx_services_company', 'company'),
    )
    
    def get_status(self):
        """Get current status combining real monitoring and user reports"""
        if self.current_status:
            return self.current_status
        
        # Fallback to report-based status if no monitoring data
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        
        # Count reports in the last hour
        recent_reports = OutageReport.query.filter(
            OutageReport.service_id == self.id,
            OutageReport.created_at >= one_hour_ago
        ).count()
        
        # If more than 5 reports in the last hour, consider it down
        if recent_reports >= 5:
            return 'down'
        elif recent_reports >= 2:
            return 'issues'
        else:
            return 'up'
    
    def check_health(self):
        """Check if the service is actually responding"""
        import requests
        import time
        
        try:
            start_time = time.time()
            response = requests.get(self.url, timeout=10, allow_redirects=True)
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            self.response_time = int(response_time)
            self.last_checked = datetime.utcnow()
            
            if response.status_code == 200:
                self.current_status = 'up'
            elif response.status_code in [500, 502, 503, 504]:
                self.current_status = 'down'
            else:
                self.current_status = 'issues'
                
        except requests.exceptions.Timeout:
            self.current_status = 'down'
            self.response_time = None
            self.last_checked = datetime.utcnow()
        except requests.exceptions.ConnectionError:
            self.current_status = 'down'  
            self.response_time = None
            self.last_checked = datetime.utcnow()
        except Exception:
            self.current_status = 'issues'
            self.response_time = None
            self.last_checked = datetime.utcnow()
            
        return self.current_status
    
    def get_recent_reports_count(self, hours=24):
        """Get count of reports in the last N hours"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return OutageReport.query.filter(
            OutageReport.service_id == self.id,
            OutageReport.created_at >= cutoff
        ).count()
    
    def detect_anomaly(self, minutes=15):
        """Advanced anomaly detection using baseline modeling"""
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=minutes)
        
        # Get recent reports count
        recent_count = OutageReport.query.filter(
            OutageReport.service_id == self.id,
            OutageReport.created_at >= cutoff
        ).count()
        
        # Get baseline for current time
        baseline = ServiceBaseline.get_baseline(self.id)
        
        if not baseline:
            # Create default baseline if none exists
            baseline = ServiceBaseline(
                service_id=self.id,
                hour_of_day=now.hour,
                day_of_week=now.weekday(),
                baseline_avg=5.0,
                threshold_multiplier=3.0
            )
            db.session.add(baseline)
        
        # Calculate threshold (reports per 15-minute window)
        baseline_15min = baseline.baseline_avg / 4  # Convert hourly to 15-min
        threshold = baseline_15min * baseline.threshold_multiplier
        
        # Check for anomaly
        is_anomaly = recent_count > threshold
        
        if is_anomaly:
            # Check if there's already an ongoing outage
            ongoing_outage = OutageEvent.query.filter(
                OutageEvent.service_id == self.id,
                OutageEvent.status == 'ongoing'
            ).first()
            
            if not ongoing_outage:
                # Create new outage event
                severity = self._determine_severity(recent_count, threshold)
                outage = OutageEvent(
                    service_id=self.id,
                    severity=severity,
                    peak_reports=recent_count,
                    total_reports=recent_count,
                    trigger_threshold=threshold
                )
                db.session.add(outage)
                logger.info(f"Outage detected for {self.name}: {recent_count} reports (threshold: {threshold:.1f})")
            else:
                # Update existing outage
                ongoing_outage.peak_reports = max(ongoing_outage.peak_reports, recent_count)
                ongoing_outage.total_reports += recent_count
        
        return {
            'anomaly_detected': is_anomaly,
            'recent_count': recent_count,
            'baseline': baseline_15min,
            'threshold': threshold,
            'multiplier': baseline.threshold_multiplier
        }
    
    def _determine_severity(self, count, threshold):
        """Determine outage severity based on report count vs threshold"""
        ratio = count / threshold if threshold > 0 else float('inf')
        
        if ratio >= 3.0:
            return 'critical'
        elif ratio >= 2.0:
            return 'major'
        else:
            return 'minor'
    
    def get_status_with_anomaly(self):
        """Enhanced status that combines monitoring and anomaly detection"""
        if self.current_status and self.last_checked:
            # Handle timezone-aware vs timezone-naive datetime comparison
            if self.last_checked.tzinfo is not None:
                time_since_check = datetime.now(timezone.utc) - self.last_checked
            else:
                time_since_check = datetime.utcnow() - self.last_checked
            if time_since_check.total_seconds() < 300:  # 5 minutes
                # Check for active outages from user reports
                ongoing_outage = OutageEvent.query.filter(
                    OutageEvent.service_id == self.id,
                    OutageEvent.status == 'ongoing'
                ).first()
                
                if ongoing_outage:
                    if ongoing_outage.severity == 'critical':
                        return 'down'
                    elif ongoing_outage.severity in ['major', 'minor']:
                        return 'issues' if self.current_status == 'up' else self.current_status
                
                return self.current_status
        
        # Fallback to anomaly detection
        anomaly_result = self.detect_anomaly()
        if anomaly_result['anomaly_detected']:
            if anomaly_result['recent_count'] > anomaly_result['threshold'] * 2:
                return 'down'
            else:
                return 'issues'
        
        return 'up'

class OutageReport(db.Model):
    __tablename__ = 'outage_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    type = db.Column(db.String(50), default='user_report')  # user_report, automatic, webhook
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    country = db.Column(db.String(100))
    region = db.Column(db.String(100))
    city = db.Column(db.String(100))
    latitude = db.Column(db.Numeric(10, 8))
    longitude = db.Column(db.Numeric(11, 8))
    user_ip = db.Column(db.String(45))  # INET type equivalent
    user_agent = db.Column(db.Text)
    source = db.Column(db.String(100))
    severity = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    status = db.Column(db.String(20), default='open')  # open, investigating, resolved, closed
    resolved_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # For backward compatibility with existing code
    @property
    def timestamp(self):
        return self.created_at
    
    @property 
    def location(self):
        if self.city and self.region:
            return f"{self.city}, {self.region}"
        elif self.city:
            return self.city
        elif self.region:
            return self.region
        return self.country
    
    # Relationships
    comments = db.relationship('Comment', backref='report', lazy='dynamic', cascade='all, delete-orphan')
    
    # Indexes
    __table_args__ = (
        Index('idx_outage_reports_service_id', 'service_id'),
        Index('idx_outage_reports_user_id', 'user_id'),
        Index('idx_outage_reports_created_at', 'created_at'),
        Index('idx_outage_reports_location', 'country', 'region', 'city'),
        Index('idx_outage_reports_status', 'status'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'service_id': self.service_id,
            'timestamp': self.created_at.isoformat(),
            'location': self.location,
            'description': self.description,
            'latitude': float(self.latitude) if self.latitude else None,
            'longitude': float(self.longitude) if self.longitude else None,
            'city': self.city,
            'country': self.country,
            'region': self.region,
            'severity': self.severity,
            'status': self.status
        }

class Comment(db.Model):
    __tablename__ = 'comments'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'))
    report_id = db.Column(db.Integer, db.ForeignKey('outage_reports.id'))
    parent_comment_id = db.Column(db.Integer, db.ForeignKey('comments.id'))
    content = db.Column(db.Text, nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    is_pinned = db.Column(db.Boolean, default=False)
    likes_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    replies = db.relationship('Comment', backref=db.backref('parent_comment', remote_side=[id]), lazy='dynamic')
    
    # Indexes
    __table_args__ = (
        Index('idx_comments_service_id', 'service_id'),
        Index('idx_comments_report_id', 'report_id'),
        Index('idx_comments_user_id', 'user_id'),
        Index('idx_comments_created_at', 'created_at'),
        db.CheckConstraint('service_id IS NOT NULL OR report_id IS NOT NULL', name='check_comment_reference')
    )
    
    # For backward compatibility
    @property
    def time(self):
        return self.created_at
    
    @property
    def comment(self):
        return self.content

class UserFavorite(db.Model):
    __tablename__ = 'user_favorites'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    notification_enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    
    # For backward compatibility
    @property
    def name(self):
        return self.service.name if self.service else None
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'service_id', name='uq_user_service_favorite'),
        Index('idx_user_favorites_user_id', 'user_id'),
        Index('idx_user_favorites_service_id', 'service_id'),
    )

class ServiceChannel(db.Model):
    __tablename__ = 'service_channels'
    
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('notification_channels.id'), primary_key=True)
    is_active = db.Column(db.Boolean, default=True)
    configuration = db.Column(db.JSON)  # Channel-specific settings for this service
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)

# Keep existing advanced models for compatibility
class ServiceBaseline(db.Model):
    """Store baseline traffic patterns for each service"""
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    hour_of_day = db.Column(db.Integer, nullable=False)  # 0-23
    day_of_week = db.Column(db.Integer, nullable=False)  # 0-6 (Monday=0)
    baseline_avg = db.Column(db.Float, default=5.0)  # Average reports per hour
    threshold_multiplier = db.Column(db.Float, default=3.0)  # Anomaly detection factor
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Create composite index for faster lookups
    __table_args__ = (Index('idx_service_time', 'service_id', 'hour_of_day', 'day_of_week'),)
    
    @classmethod
    def get_baseline(cls, service_id, hour=None, day=None):
        """Get baseline for a specific service, hour, and day"""
        if hour is None or day is None:
            now = datetime.utcnow()
            hour = now.hour
            day = now.weekday()
            
        return cls.query.filter_by(
            service_id=service_id,
            hour_of_day=hour,
            day_of_week=day
        ).first()
    
    @classmethod
    def update_baseline(cls, service_id, hour, day, new_avg):
        """Update or create baseline data"""
        baseline = cls.query.filter_by(
            service_id=service_id,
            hour_of_day=hour,
            day_of_week=day
        ).first()
        
        if baseline:
            baseline.baseline_avg = new_avg
            baseline.updated_at = datetime.utcnow()
        else:
            baseline = cls(
                service_id=service_id,
                hour_of_day=hour,
                day_of_week=day,
                baseline_avg=new_avg
            )
            db.session.add(baseline)
        
        return baseline

class OutageEvent(db.Model):
    """Track outage events and their lifecycle"""
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    start_time = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    end_time = db.Column(db.DateTime(timezone=True), nullable=True)
    status = db.Column(db.String(20), default='ongoing')  # ongoing, resolved, false_positive
    severity = db.Column(db.String(20), default='minor')  # minor, major, critical
    peak_reports = db.Column(db.Integer, default=0)
    total_reports = db.Column(db.Integer, default=0)
    affected_regions = db.Column(db.Text, nullable=True)  # JSON string of regions
    trigger_threshold = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'service_id': self.service_id,
            'service_name': self.service.name if self.service else None,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'status': self.status,
            'severity': self.severity,
            'peak_reports': self.peak_reports,
            'total_reports': self.total_reports,
            'affected_regions': json.loads(self.affected_regions) if self.affected_regions else [],
            'trigger_threshold': self.trigger_threshold,
            'duration_minutes': self.get_duration_minutes()
        }
    
    def get_duration_minutes(self):
        """Get outage duration in minutes"""
        if not self.end_time:
            return int((datetime.utcnow() - self.start_time).total_seconds() / 60)
        return int((self.end_time - self.start_time).total_seconds() / 60)
    
    def mark_resolved(self):
        """Mark the outage as resolved"""
        self.end_time = datetime.utcnow()
        self.status = 'resolved'

class ServiceMetrics(db.Model):
    """Store time-series metrics for services"""
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    metric_type = db.Column(db.String(50), nullable=False)  # reports, response_time, status_changes
    value = db.Column(db.Float, nullable=False)
    extra_data = db.Column(db.Text, nullable=True)  # JSON metadata
    
    # Create index for time-series queries
    __table_args__ = (Index('idx_service_metrics_time', 'service_id', 'metric_type', 'timestamp'),)
    
    @classmethod
    def add_metric(cls, service_id, metric_type, value, metadata=None):
        """Add a metric entry"""
        metric = cls(
            service_id=service_id,
            metric_type=metric_type,
            value=value,
            extra_data=json.dumps(metadata) if metadata else None
        )
        db.session.add(metric)
        return metric
    
    @classmethod
    def get_metrics(cls, service_id, metric_type, hours=24):
        """Get metrics for the last N hours"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return cls.query.filter(
            cls.service_id == service_id,
            cls.metric_type == metric_type,
            cls.timestamp >= cutoff
        ).order_by(cls.timestamp.desc()).all()

class GeoLocation:
    """Helper class for IP geolocation"""
    
    @staticmethod
    def get_location_info(ip_address):
        """Get geolocation info from IP address"""
        try:
            # Try to parse the IP to validate it
            ip_obj = ipaddress.ip_address(ip_address)
            
            # Skip private/local IPs
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                return {
                    'city': 'Local',
                    'country': 'Local',
                    'region': 'Local',
                    'isp': 'Local Network',
                    'asn': 'Local'
                }
            
            # For demo purposes, return mock data based on IP patterns
            # In production, you would use a real GeoIP database like MaxMind
            ip_str = str(ip_address)
            
            # Simple pattern matching for demo
            if ip_str.startswith(('8.8.', '8.4.')):
                return {
                    'city': 'Mountain View',
                    'country': 'United States',
                    'region': 'California',
                    'isp': 'Google LLC',
                    'asn': 'AS15169'
                }
            elif ip_str.startswith(('1.1.', '1.0.')):
                return {
                    'city': 'San Francisco',
                    'country': 'United States', 
                    'region': 'California',
                    'isp': 'Cloudflare Inc',
                    'asn': 'AS13335'
                }
            else:
                # Default for unknown IPs
                return {
                    'city': 'Unknown',
                    'country': 'Unknown',
                    'region': 'Unknown',
                    'isp': 'Unknown ISP',
                    'asn': 'Unknown'
                }
                
        except (ValueError, TypeError):
            return {
                'city': 'Unknown',
                'country': 'Unknown',
                'region': 'Unknown',
                'isp': 'Unknown ISP',
                'asn': 'Unknown'
            }

# Backward compatibility aliases
Report = OutageReport
Favorite = UserFavorite