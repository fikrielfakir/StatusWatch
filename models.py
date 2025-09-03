from datetime import datetime, timedelta, timezone
import json
import ipaddress
import logging
from app import db
from flask_login import UserMixin
from sqlalchemy import func, text, desc, and_, or_

# Setup logging
logger = logging.getLogger(__name__)

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
    icon_path = db.Column(db.String(200), nullable=True)
    current_status = db.Column(db.String(20), default='up')
    last_checked = db.Column(db.DateTime, default=datetime.utcnow)
    response_time = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reports = db.relationship('Report', backref='service', lazy=True, cascade='all, delete-orphan')
    
    def get_status(self):
        """Get current status combining real monitoring and user reports"""
        # Use the real-time monitored status
        if self.current_status:
            return self.current_status
        
        # Fallback to report-based status if no monitoring data
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
    
    def check_health(self):
        """Check if the service is actually responding"""
        import requests
        import time
        
        try:
            start_time = time.time()
            response = requests.get(self.url, timeout=10, allow_redirects=True)
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            self.response_time = response_time
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
        return Report.query.filter(
            Report.service_id == self.id,
            Report.timestamp >= cutoff
        ).count()
    
    def detect_anomaly(self, minutes=15):
        """Advanced anomaly detection using baseline modeling"""
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=minutes)
        
        # Get recent reports count
        recent_count = Report.query.filter(
            Report.service_id == self.id,
            Report.timestamp >= cutoff
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
        
        # Record metric
        ServiceMetrics.add_metric(
            service_id=self.id,
            metric_type='reports',
            value=recent_count,
            metadata={'baseline': baseline_15min, 'threshold': threshold}
        )
        
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
                if recent_count > ongoing_outage.trigger_threshold * 2:
                    ongoing_outage.severity = 'critical'
                elif recent_count > ongoing_outage.trigger_threshold * 1.5:
                    ongoing_outage.severity = 'major'
        else:
            # Check if we should resolve any ongoing outages
            ongoing_outage = OutageEvent.query.filter(
                OutageEvent.service_id == self.id,
                OutageEvent.status == 'ongoing'
            ).first()
            
            if ongoing_outage and recent_count <= baseline_15min:
                ongoing_outage.mark_resolved()
                logger.info(f"Outage resolved for {self.name}: reports back to baseline")
        
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
        # Use real-time monitored status if available
        if self.current_status and self.last_checked:
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
    
    def update_baseline_data(self):
        """Update baseline data based on historical reports"""
        # Get reports from the last 30 days
        cutoff = datetime.utcnow() - timedelta(days=30)
        
        # Group reports by hour and day of week
        for hour in range(24):
            for day in range(7):
                # Calculate average reports for this hour/day combination
                reports = db.session.query(func.count(Report.id)).filter(
                    Report.service_id == self.id,
                    Report.timestamp >= cutoff,
                    text("EXTRACT(hour FROM timestamp) = :hour"),
                    text("EXTRACT(dow FROM timestamp) = :dow")
                ).params(hour=hour, dow=day).scalar()
                
                # Calculate weekly average
                weeks_of_data = min(4, (datetime.utcnow() - cutoff).days / 7)
                avg_reports = reports / max(weeks_of_data, 1)
                
                # Update baseline
                ServiceBaseline.update_baseline(
                    service_id=self.id,
                    hour=hour,
                    day=day,
                    new_avg=max(avg_reports, 1.0)  # Minimum baseline of 1
                )

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


class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    location = db.Column(db.String(100))
    description = db.Column(db.Text)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    user_ip = db.Column(db.String(45))  # To prevent spam
    
    # Enhanced geolocation and clustering fields
    city = db.Column(db.String(100), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    region = db.Column(db.String(100), nullable=True)
    isp = db.Column(db.String(200), nullable=True)
    asn = db.Column(db.String(100), nullable=True)
    issue_type = db.Column(db.String(50), default='general')
    severity = db.Column(db.Integer, default=1)  # 1-5 scale
    
    def to_dict(self):
        return {
            'id': self.id,
            'service_id': self.service_id,
            'timestamp': self.timestamp.isoformat(),
            'location': self.location,
            'description': self.description,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'city': self.city,
            'country': self.country,
            'region': self.region,
            'isp': self.isp,
            'asn': self.asn,
            'issue_type': self.issue_type,
            'severity': self.severity
        }


class ServiceBaseline(db.Model):
    """Store baseline traffic patterns for each service"""
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    hour_of_day = db.Column(db.Integer, nullable=False)  # 0-23
    day_of_week = db.Column(db.Integer, nullable=False)  # 0-6 (Monday=0)
    baseline_avg = db.Column(db.Float, default=5.0)  # Average reports per hour
    threshold_multiplier = db.Column(db.Float, default=3.0)  # Anomaly detection factor
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Create composite index for faster lookups
    __table_args__ = (db.Index('idx_service_time', 'service_id', 'hour_of_day', 'day_of_week'),)
    
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
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='ongoing')  # ongoing, resolved, false_positive
    severity = db.Column(db.String(20), default='minor')  # minor, major, critical
    peak_reports = db.Column(db.Integer, default=0)
    total_reports = db.Column(db.Integer, default=0)
    affected_regions = db.Column(db.Text, nullable=True)  # JSON string of regions
    trigger_threshold = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    service = db.relationship('Service', backref='outage_events')
    
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
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    metric_type = db.Column(db.String(50), nullable=False)  # reports, response_time, status_changes
    value = db.Column(db.Float, nullable=False)
    extra_data = db.Column(db.Text, nullable=True)  # JSON metadata
    
    # Create index for time-series queries
    __table_args__ = (db.Index('idx_service_metrics_time', 'service_id', 'metric_type', 'timestamp'),)
    
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
