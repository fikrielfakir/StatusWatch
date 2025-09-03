"""
Integration Service for Outage Detection System
Connects external monitoring, stream processing, and anomaly detection
"""

import asyncio
import threading
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from external_monitors import ExternalMonitorOrchestrator
from stream_processor import StreamProcessorOrchestrator, OutageEvent
from anomaly_detection import HybridAnomalyDetector, analyze_service_anomaly
from models_optimized import Service, OutageReport, OutageEvent as DBOutageEvent
from app import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntegratedOutageDetectionService:
    """Main service that integrates all outage detection components"""
    
    def __init__(self, credentials: Optional[Dict] = None):
        # Initialize components
        self.external_monitor = ExternalMonitorOrchestrator(
            twitter_credentials=credentials.get('twitter') if credentials else None,
            google_api_key=credentials.get('google_api_key') if credentials else None
        )
        
        self.stream_processor = StreamProcessorOrchestrator()
        self.anomaly_detector = HybridAnomalyDetector()
        
        # Configuration
        self.monitoring_interval = 300  # 5 minutes
        self.is_running = False
        self.executor = ThreadPoolExecutor(max_workers=10)
        
        # Tracking
        self.last_check = {}
        self.active_outages = {}
        
        logger.info("Integrated Outage Detection Service initialized")
    
    def start_monitoring(self):
        """Start the monitoring service"""
        if self.is_running:
            logger.warning("Monitoring service already running")
            return
        
        self.is_running = True
        logger.info("Starting integrated outage monitoring")
        
        # Start monitoring thread
        monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        monitoring_thread.start()
        
        # Start stream processing
        self._start_stream_processing()
    
    def stop_monitoring(self):
        """Stop the monitoring service"""
        self.is_running = False
        logger.info("Stopping integrated outage monitoring")
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                self._run_monitoring_cycle()
                time.sleep(self.monitoring_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)  # Wait before retrying
    
    def _run_monitoring_cycle(self):
        """Run one cycle of monitoring for all services"""
        logger.info("Starting monitoring cycle")
        
        # Get all active services
        try:
            with db.app.app_context():
                services = Service.query.filter_by(is_active=True).all()
                
                # Monitor services in parallel
                futures = []
                for service in services:
                    future = self.executor.submit(self._monitor_service, service)
                    futures.append(future)
                
                # Wait for all tasks to complete
                for future in as_completed(futures, timeout=300):
                    try:
                        result = future.result()
                        if result:
                            logger.info(f"Monitored service: {result.get('service_name')}")
                    except Exception as e:
                        logger.error(f"Error monitoring service: {e}")
                        
        except Exception as e:
            logger.error(f"Error getting services from database: {e}")
    
    def _monitor_service(self, service) -> Optional[Dict]:
        """Monitor a single service"""
        try:
            service_name = service.name
            service_id = service.id
            
            logger.debug(f"Monitoring service: {service_name}")
            
            # 1. External API monitoring
            external_data = self.external_monitor.check_service_status(service_name)
            
            # 2. Get recent reports from database
            recent_reports = self._get_recent_reports(service_id)
            
            # 3. Prepare data for anomaly detection
            current_report_count = len(recent_reports)
            current_response_time = service.response_time or 200
            
            # 4. Get historical data for training
            historical_data = self._get_historical_data(service_id)
            
            # 5. Run anomaly detection
            anomaly_result = analyze_service_anomaly(
                service_id=service_id,
                report_count=current_report_count,
                response_time=current_response_time,
                historical_data=historical_data
            )
            
            # 6. Analyze external sources
            external_anomaly = self._analyze_external_sources(external_data)
            
            # 7. Combine results and determine final status
            combined_result = self._combine_detection_results(
                service, anomaly_result, external_anomaly, external_data
            )
            
            # 8. Create and publish outage event if needed
            if combined_result['is_outage']:
                outage_event = self._create_outage_event(service, combined_result)
                self.stream_processor.publish_outage_event(outage_event)
                
                # Update database
                self._update_service_status(service, combined_result)
            
            # 9. Update last check time
            self.last_check[service_id] = datetime.now()
            
            return {
                'service_name': service_name,
                'service_id': service_id,
                'status': combined_result.get('final_status', 'unknown'),
                'is_outage': combined_result['is_outage'],
                'confidence': combined_result.get('confidence_score', 0)
            }
            
        except Exception as e:
            logger.error(f"Error monitoring service {service.name}: {e}")
            return None
    
    def _get_recent_reports(self, service_id: int, hours: int = 1) -> List[Dict]:
        """Get recent user reports for a service"""
        try:
            with db.app.app_context():
                cutoff = datetime.utcnow() - timedelta(hours=hours)
                reports = OutageReport.query.filter(
                    OutageReport.service_id == service_id,
                    OutageReport.created_at >= cutoff
                ).all()
                
                return [report.to_dict() for report in reports]
        except Exception as e:
            logger.error(f"Error getting recent reports for service {service_id}: {e}")
            return []
    
    def _get_historical_data(self, service_id: int, days: int = 7) -> List[Dict]:
        """Get historical data for anomaly detection training"""
        try:
            with db.app.app_context():
                cutoff = datetime.utcnow() - timedelta(days=days)
                
                # Get hourly report counts
                from sqlalchemy import func
                hourly_data = db.session.query(
                    func.date_trunc('hour', OutageReport.created_at).label('hour'),
                    func.count(OutageReport.id).label('report_count')
                ).filter(
                    OutageReport.service_id == service_id,
                    OutageReport.created_at >= cutoff
                ).group_by('hour').all()
                
                # Convert to format expected by anomaly detector
                historical_data = []
                for hour_data in hourly_data:
                    historical_data.append({
                        'timestamp': hour_data.hour.isoformat(),
                        'report_count': float(hour_data.report_count),
                        'response_time': 200.0  # Default, would be better from actual monitoring
                    })
                
                return historical_data
                
        except Exception as e:
            logger.error(f"Error getting historical data for service {service_id}: {e}")
            return []
    
    def _analyze_external_sources(self, external_data: Dict) -> Dict:
        """Analyze external source data for anomalies"""
        anomaly_indicators = {
            'twitter_high_mentions': False,
            'reddit_high_mentions': False,
            'downdetector_issues': False,
            'google_api_down': False,
            'overall_anomaly': False
        }
        
        confidence_scores = []
        
        try:
            sources = external_data.get('sources', {})
            
            # Twitter analysis
            twitter_data = sources.get('twitter', {})
            if twitter_data.get('mention_count', 0) > 10:
                anomaly_indicators['twitter_high_mentions'] = True
                confidence_scores.append(0.8)
            
            # Reddit analysis
            reddit_data = sources.get('reddit', {})
            if reddit_data.get('mention_count', 0) > 5:
                anomaly_indicators['reddit_high_mentions'] = True
                confidence_scores.append(0.7)
            
            # DownDetector analysis
            downdetector_data = sources.get('downdetector', {})
            if downdetector_data.get('status') in ['issues', 'down']:
                anomaly_indicators['downdetector_issues'] = True
                confidence_scores.append(0.9)
            
            # Google API analysis
            google_data = sources.get('google', {})
            if google_data.get('incidents'):
                anomaly_indicators['google_api_down'] = True
                confidence_scores.append(0.8)
            
            # Overall assessment
            anomaly_count = sum(anomaly_indicators.values())
            anomaly_indicators['overall_anomaly'] = anomaly_count >= 2
            
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
            
            return {
                'indicators': anomaly_indicators,
                'confidence_score': avg_confidence,
                'source_count': len([k for k, v in anomaly_indicators.items() if v and k != 'overall_anomaly'])
            }
            
        except Exception as e:
            logger.error(f"Error analyzing external sources: {e}")
            return {
                'indicators': anomaly_indicators,
                'confidence_score': 0.0,
                'source_count': 0
            }
    
    def _combine_detection_results(self, service, anomaly_result: Dict, 
                                 external_anomaly: Dict, external_data: Dict) -> Dict:
        """Combine internal anomaly detection with external source analysis"""
        
        # Internal anomaly detection
        internal_anomaly = anomaly_result.get('is_anomaly', False)
        internal_confidence = anomaly_result.get('confidence_score', 0)
        internal_severity = anomaly_result.get('severity', 'low')
        
        # External anomaly detection
        external_anomaly_detected = external_anomaly.get('indicators', {}).get('overall_anomaly', False)
        external_confidence = external_anomaly.get('confidence_score', 0)
        
        # Combine confidences (weighted)
        combined_confidence = (internal_confidence * 0.6) + (external_confidence * 0.4)
        
        # Determine if this is an outage
        is_outage = False
        final_status = 'up'
        
        if internal_anomaly and external_anomaly_detected:
            # Both internal and external detect anomaly - high confidence outage
            is_outage = True
            final_status = 'down' if internal_severity in ['critical', 'high'] else 'issues'
            combined_confidence = min(0.95, combined_confidence + 0.2)
        elif internal_anomaly and combined_confidence > 0.7:
            # Strong internal anomaly
            is_outage = True
            final_status = 'issues' if internal_severity == 'critical' else 'issues'
        elif external_anomaly_detected and external_confidence > 0.8:
            # Strong external evidence
            is_outage = True
            final_status = 'issues'
        elif internal_anomaly or external_anomaly_detected:
            # Weak evidence, mark as potential issues
            final_status = 'issues' if combined_confidence > 0.5 else 'up'
            is_outage = combined_confidence > 0.6
        
        return {
            'is_outage': is_outage,
            'final_status': final_status,
            'confidence_score': combined_confidence,
            'internal_anomaly': internal_anomaly,
            'external_anomaly': external_anomaly_detected,
            'internal_severity': internal_severity,
            'external_sources': external_anomaly.get('source_count', 0),
            'combined_evidence': {
                'internal': anomaly_result,
                'external': external_anomaly,
                'external_data': external_data
            }
        }
    
    def _create_outage_event(self, service, combined_result: Dict) -> OutageEvent:
        """Create an outage event for stream processing"""
        severity_map = {
            'low': 'low',
            'medium': 'medium', 
            'high': 'high',
            'critical': 'critical'
        }
        
        severity = severity_map.get(combined_result.get('internal_severity', 'medium'), 'medium')
        
        return OutageEvent(
            service_id=service.id,
            service_name=service.name,
            event_type='hybrid_detection',
            severity=severity,
            source='integrated_system',
            timestamp=datetime.now().isoformat(),
            data={
                'confidence_score': combined_result['confidence_score'],
                'internal_anomaly': combined_result['internal_anomaly'],
                'external_anomaly': combined_result['external_anomaly'],
                'final_status': combined_result['final_status'],
                'external_sources': combined_result['external_sources'],
                'detection_method': 'hybrid'
            },
            confidence_score=combined_result['confidence_score']
        )
    
    def _update_service_status(self, service, combined_result: Dict):
        """Update service status in database"""
        try:
            with db.app.app_context():
                service.current_status = combined_result['final_status']
                service.last_checked = datetime.utcnow()
                db.session.commit()
                
                # Create outage event record if needed
                if combined_result['is_outage']:
                    self._create_db_outage_event(service, combined_result)
                    
        except Exception as e:
            logger.error(f"Error updating service status: {e}")
    
    def _create_db_outage_event(self, service, combined_result: Dict):
        """Create outage event record in database"""
        try:
            with db.app.app_context():
                # Check if there's already an ongoing outage
                existing_outage = DBOutageEvent.query.filter(
                    DBOutageEvent.service_id == service.id,
                    DBOutageEvent.status == 'ongoing'
                ).first()
                
                if not existing_outage:
                    # Create new outage event
                    outage_event = DBOutageEvent(
                        service_id=service.id,
                        severity=combined_result.get('internal_severity', 'medium'),
                        peak_reports=combined_result.get('combined_evidence', {}).get('internal', {}).get('method_results', {}).get('z_score', {}).get('current_value', 0),
                        total_reports=1,
                        trigger_threshold=combined_result.get('confidence_score', 0.5)
                    )
                    db.session.add(outage_event)
                    db.session.commit()
                    
                    logger.info(f"Created outage event for service {service.name}")
                
        except Exception as e:
            logger.error(f"Error creating outage event: {e}")
    
    def _start_stream_processing(self):
        """Start stream processing for real-time event handling"""
        def handle_outage_event(event: OutageEvent):
            """Handle incoming outage events from stream"""
            logger.info(f"Processing outage event: {event.service_name} - {event.severity}")
            
            # Update active outages tracking
            self.active_outages[event.service_id] = {
                'event': event,
                'first_detected': datetime.now(),
                'last_updated': datetime.now()
            }
        
        # Start consuming events (this would run in background)
        # Note: In a real deployment, this would be a separate service
        logger.info("Stream processing handler registered")
    
    def get_service_status_summary(self) -> Dict:
        """Get summary of all service statuses"""
        try:
            with db.app.app_context():
                services = Service.query.filter_by(is_active=True).all()
                
                summary = {
                    'total_services': len(services),
                    'statuses': {'up': 0, 'issues': 0, 'down': 0, 'unknown': 0},
                    'active_outages': len(self.active_outages),
                    'last_check': max(self.last_check.values()) if self.last_check else None,
                    'services': []
                }
                
                for service in services:
                    status = service.current_status or 'unknown'
                    summary['statuses'][status] = summary['statuses'].get(status, 0) + 1
                    
                    summary['services'].append({
                        'id': service.id,
                        'name': service.name,
                        'status': status,
                        'last_checked': service.last_checked.isoformat() if service.last_checked else None,
                        'response_time': service.response_time
                    })
                
                return summary
                
        except Exception as e:
            logger.error(f"Error getting service status summary: {e}")
            return {'error': str(e)}

# Global service instance
integrated_service = None

def start_integrated_monitoring(credentials: Optional[Dict] = None):
    """Start the integrated monitoring service"""
    global integrated_service
    
    if integrated_service is None:
        integrated_service = IntegratedOutageDetectionService(credentials)
    
    integrated_service.start_monitoring()
    return integrated_service

def stop_integrated_monitoring():
    """Stop the integrated monitoring service"""
    global integrated_service
    
    if integrated_service:
        integrated_service.stop_monitoring()

def get_monitoring_status() -> Dict:
    """Get current monitoring status"""
    global integrated_service
    
    if integrated_service:
        return integrated_service.get_service_status_summary()
    else:
        return {'error': 'Monitoring service not started'}

if __name__ == "__main__":
    # Test the integrated service
    credentials = {
        # Add your credentials here for testing
        # 'twitter': {
        #     'api_key': 'your_key',
        #     'api_secret': 'your_secret',
        #     'access_token': 'your_token',
        #     'access_token_secret': 'your_token_secret'
        # },
        # 'google_api_key': 'your_google_api_key'
    }
    
    service = start_integrated_monitoring(credentials)
    
    try:
        # Keep running
        while True:
            time.sleep(60)
            status = get_monitoring_status()
            logger.info(f"Service summary: {status.get('statuses', {})}")
    except KeyboardInterrupt:
        logger.info("Stopping integrated monitoring service")
        stop_integrated_monitoring()