"""
Advanced Outage Detection System
Implements sophisticated anomaly detection, geolocation processing, and baseline modeling
"""

import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from app import db, socketio
from models import Service, Report, ServiceBaseline, OutageEvent, ServiceMetrics, GeoLocation

logger = logging.getLogger(__name__)

class OutageDetector:
    """Main class for advanced outage detection and processing"""
    
    def __init__(self):
        self.detection_window_minutes = 15
        self.baseline_update_interval_hours = 24
    
    def process_report(self, report_data, user_ip):
        """Process a new report with geolocation and anomaly detection"""
        # Get geolocation info
        geo_info = GeoLocation.get_location_info(user_ip)
        
        # Determine issue type from description
        issue_type = self._classify_issue_type(report_data.get('description', ''))
        
        # Create report with enhanced data
        report = Report(
            service_id=report_data['service_id'],
            location=report_data.get('location', ''),
            description=report_data.get('description', ''),
            latitude=report_data.get('latitude'),
            longitude=report_data.get('longitude'),
            user_ip=user_ip,
            city=geo_info['city'],
            country=geo_info['country'],
            region=geo_info['region'],
            isp=geo_info['isp'],
            asn=geo_info['asn'],
            issue_type=issue_type,
            severity=self._determine_report_severity(report_data.get('description', ''))
        )
        
        db.session.add(report)
        db.session.flush()  # Get the report ID
        
        # Run anomaly detection
        service = Service.query.get(report_data['service_id'])
        if service:
            anomaly_result = service.detect_anomaly(minutes=self.detection_window_minutes)
            
            # Broadcast real-time updates
            self._broadcast_updates(service, report, anomaly_result)
        
        return report
    
    def _classify_issue_type(self, description):
        """Classify the issue type based on description keywords"""
        if not description:
            return 'general'
        
        desc_lower = description.lower()
        
        # Connection issues
        if any(word in desc_lower for word in ['connect', 'login', 'signin', 'access', 'timeout']):
            return 'connection'
        
        # Performance issues
        if any(word in desc_lower for word in ['slow', 'loading', 'lag', 'performance', 'delay']):
            return 'performance'
        
        # Service down
        if any(word in desc_lower for word in ['down', 'offline', 'unavailable', 'not working', 'broken']):
            return 'outage'
        
        # Feature specific
        if any(word in desc_lower for word in ['video', 'audio', 'message', 'post', 'upload']):
            return 'feature'
        
        return 'general'
    
    def _determine_report_severity(self, description):
        """Determine severity level (1-5) based on description"""
        if not description:
            return 2
        
        desc_lower = description.lower()
        
        # Critical issues
        if any(word in desc_lower for word in ['completely down', 'not working at all', 'critical', 'urgent']):
            return 5
        
        # Major issues  
        if any(word in desc_lower for word in ['major', 'serious', 'broken', 'failed']):
            return 4
        
        # Moderate issues
        if any(word in desc_lower for word in ['slow', 'intermittent', 'sometimes']):
            return 3
        
        # Minor issues
        if any(word in desc_lower for word in ['minor', 'small', 'occasional']):
            return 1
        
        return 2  # Default severity
    
    def _broadcast_updates(self, service, report, anomaly_result):
        """Broadcast real-time updates via WebSocket"""
        # Emit new report event
        socketio.emit('new_report', {
            'service_id': service.id,
            'service_name': service.name,
            'report': report.to_dict(),
            'new_status': service.get_status_with_anomaly()
        })
        
        # If anomaly detected, emit outage alert
        if anomaly_result['anomaly_detected']:
            self._emit_outage_alert(service, anomaly_result)
        
        # Emit updated service data
        socketio.emit('service_update', {
            'service_id': service.id,
            'service_name': service.name,
            'status': service.get_status_with_anomaly(),
            'recent_reports': service.get_recent_reports_count(),
            'anomaly_data': anomaly_result
        })
    
    def _emit_outage_alert(self, service, anomaly_result):
        """Emit outage alert for dashboard notifications"""
        # Get affected regions
        affected_regions = self._get_affected_regions(service.id)
        
        socketio.emit('outage_alert', {
            'service_id': service.id,
            'service_name': service.name,
            'report_count': anomaly_result['recent_count'],
            'threshold': anomaly_result['threshold'],
            'affected_regions': affected_regions,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def _get_affected_regions(self, service_id, minutes=15):
        """Get list of affected regions for a service"""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        
        # Query recent reports grouped by region
        reports = db.session.query(
            Report.country,
            Report.region,
            Report.city,
            db.func.count(Report.id).label('count')
        ).filter(
            Report.service_id == service_id,
            Report.timestamp >= cutoff
        ).group_by(
            Report.country,
            Report.region, 
            Report.city
        ).having(db.func.count(Report.id) >= 2).all()
        
        regions = []
        for report in reports:
            if report.country and report.country != 'Unknown':
                region_name = f"{report.city}, {report.region}, {report.country}" if report.city else f"{report.region}, {report.country}"
                regions.append({
                    'name': region_name,
                    'count': report.count,
                    'country': report.country,
                    'region': report.region,
                    'city': report.city
                })
        
        return regions
    
    def update_baselines(self):
        """Update baseline data for all services"""
        logger.info("Updating service baselines...")
        
        services = Service.query.all()
        for service in services:
            try:
                service.update_baseline_data()
                db.session.commit()
                logger.debug(f"Updated baseline for {service.name}")
            except Exception as e:
                logger.error(f"Error updating baseline for {service.name}: {e}")
                db.session.rollback()
    
    def check_all_services(self):
        """Run anomaly detection on all services"""
        services = Service.query.all()
        updates = []
        
        for service in services:
            try:
                old_status = service.current_status
                anomaly_result = service.detect_anomaly(minutes=self.detection_window_minutes)
                new_status = service.get_status_with_anomaly()
                
                # Record status change metric
                if old_status != new_status:
                    ServiceMetrics.add_metric(
                        service_id=service.id,
                        metric_type='status_change',
                        value=1,
                        metadata={
                            'old_status': old_status,
                            'new_status': new_status,
                            'anomaly_detected': anomaly_result['anomaly_detected']
                        }
                    )
                    
                    updates.append({
                        'service_id': service.id,
                        'name': service.name,
                        'old_status': old_status,
                        'new_status': new_status,
                        'response_time': service.response_time,
                        'anomaly_data': anomaly_result
                    })
            
            except Exception as e:
                logger.error(f"Error checking service {service.name}: {e}")
        
        if updates:
            db.session.commit()
            socketio.emit('status_updates', updates)
        
        return updates
    
    def get_outage_summary(self, hours=24):
        """Get summary of outages in the last N hours"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        # Get active outages
        active_outages = OutageEvent.query.filter(
            OutageEvent.status == 'ongoing',
            OutageEvent.start_time >= cutoff
        ).all()
        
        # Get resolved outages
        resolved_outages = OutageEvent.query.filter(
            OutageEvent.status == 'resolved',
            OutageEvent.start_time >= cutoff
        ).all()
        
        # Calculate statistics
        total_outages = len(active_outages) + len(resolved_outages)
        critical_count = sum(1 for o in (active_outages + resolved_outages) if o.severity == 'critical')
        major_count = sum(1 for o in (active_outages + resolved_outages) if o.severity == 'major')
        
        return {
            'active_outages': [o.to_dict() for o in active_outages],
            'resolved_outages': [o.to_dict() for o in resolved_outages],
            'statistics': {
                'total_outages': total_outages,
                'active_count': len(active_outages),
                'resolved_count': len(resolved_outages),
                'critical_count': critical_count,
                'major_count': major_count,
                'average_duration': self._calculate_average_duration(resolved_outages)
            }
        }
    
    def _calculate_average_duration(self, outages):
        """Calculate average outage duration in minutes"""
        if not outages:
            return 0
        
        total_duration = sum(o.get_duration_minutes() for o in outages)
        return total_duration / len(outages)
    
    def get_heatmap_data(self, service_id, hours=24):
        """Get geolocation data for heatmap visualization"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        reports = db.session.query(
            Report.latitude,
            Report.longitude,
            Report.city,
            Report.country,
            Report.region,
            db.func.count(Report.id).label('count')
        ).filter(
            Report.service_id == service_id,
            Report.timestamp >= cutoff,
            Report.latitude.isnot(None),
            Report.longitude.isnot(None)
        ).group_by(
            Report.latitude,
            Report.longitude,
            Report.city,
            Report.country,
            Report.region
        ).all()
        
        heatmap_data = []
        for report in reports:
            heatmap_data.append({
                'lat': float(report.latitude),
                'lng': float(report.longitude),
                'count': report.count,
                'city': report.city,
                'country': report.country,
                'region': report.region
            })
        
        return heatmap_data


# Global instance
outage_detector = OutageDetector()