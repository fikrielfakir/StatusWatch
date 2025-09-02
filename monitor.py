import threading
import time
import logging
from app import app, db, socketio
from models import Service

class ServiceMonitor:
    def __init__(self, check_interval=60):  # Check every 60 seconds
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
                time.sleep(5)  # Short delay before retrying
    
    def _check_all_services(self):
        """Check the health of all services"""
        services = Service.query.all()
        status_updates = []
        
        for service in services:
            old_status = service.current_status
            new_status = service.check_health()
            
            # Save changes to database
            db.session.commit()
            
            # If status changed, add to updates
            if old_status != new_status:
                status_updates.append({
                    'service_id': service.id,
                    'name': service.name,
                    'old_status': old_status,
                    'new_status': new_status,
                    'response_time': service.response_time,
                    'last_checked': service.last_checked.isoformat()
                })
                logging.info(f"Service {service.name} status changed: {old_status} -> {new_status}")
        
        # Broadcast status updates to all connected clients
        if status_updates:
            socketio.emit('status_updates', status_updates)
            
        # Also send periodic status refresh
        service_statuses = []
        for service in services:
            service_statuses.append({
                'id': service.id,
                'name': service.name,
                'status': service.current_status,
                'response_time': service.response_time,
                'last_checked': service.last_checked.isoformat() if service.last_checked else None,
                'recent_reports': service.get_recent_reports_count()
            })
        
        socketio.emit('dashboard_refresh', service_statuses)

# Global monitor instance
monitor = ServiceMonitor()