import threading
import time
import logging
from app import app, db, socketio
from models import Service
from outage_detector import outage_detector

class ServiceMonitor:
    def __init__(self, check_interval=300):  # Check every 5 minutes
        self.check_interval = check_interval
        self.running = False
        self.thread = None
        
    def start(self):
        """Start the monitoring service"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.thread.start()
            logging.info("Service monitor started")
    
    def stop(self):
        """Stop the monitoring service"""
        self.running = False
        if self.thread:
            self.thread.join()
        logging.info("Service monitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                with app.app_context():
                    self._check_all_services()
                time.sleep(self.check_interval)
            except Exception as e:
                logging.error(f"Error in monitoring loop: {e}")
                time.sleep(30)  # Short delay before retrying
    
    def _check_all_services(self):
        """Enhanced service checking with anomaly detection"""
        services = Service.query.all()
        status_updates = []
        
        for service in services:
            old_status = service.current_status
            
            # Run standard health check
            service.check_health()
            
            # Run anomaly detection
            anomaly_result = service.detect_anomaly()
            
            # Get enhanced status
            new_status = service.get_status_with_anomaly()
            
            # If status changed, add to updates
            if old_status != new_status:
                status_updates.append({
                    'service_id': service.id,
                    'name': service.name,
                    'old_status': old_status,
                    'new_status': new_status,
                    'response_time': service.response_time,
                    'last_checked': service.last_checked.isoformat() if service.last_checked else None,
                    'anomaly_detected': anomaly_result['anomaly_detected'],
                    'recent_reports': anomaly_result['recent_count']
                })
                logging.info(f"Service {service.name} status changed: {old_status} -> {new_status}")
                
                # Emit outage alert if anomaly detected
                if anomaly_result['anomaly_detected']:
                    logging.warning(f"Anomaly detected for {service.name}: {anomaly_result['recent_count']} reports vs {anomaly_result['threshold']:.1f} threshold")
        
        # Save all changes to database
        db.session.commit()
        
        # Broadcast status updates to all connected clients
        if status_updates:
            socketio.emit('status_updates', status_updates)
            
        # Also send periodic status refresh with enhanced data
        service_statuses = []
        for service in services:
            service_statuses.append({
                'id': service.id,
                'name': service.name,
                'status': service.get_status_with_anomaly(),  # Use enhanced status
                'response_time': service.response_time,
                'last_checked': service.last_checked.isoformat() if service.last_checked else None,
                'recent_reports': service.get_recent_reports_count()
            })
        
        socketio.emit('dashboard_refresh', service_statuses)

# Global monitor instance
monitor = ServiceMonitor()