import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from flask_socketio import emit
from app import db, socketio
from models import Service, Report, ServiceBaseline, OutageEvent, ServiceMetrics
from outage_detector import outage_detector
from sqlalchemy import func

bp = Blueprint('main', __name__)

@bp.route('/')
def dashboard():
    """Main dashboard showing all services and their status"""
    services = Service.query.all()
    services_data = []
    
    for service in services:
        status = service.get_status()
        recent_count = service.get_recent_reports_count()
        services_data.append({
            'id': service.id,
            'name': service.name,
            'url': service.url,
            'icon_path': service.icon_path,
            'status': service.get_status_with_anomaly(),  # Use enhanced status
            'recent_reports': recent_count,
            'response_time': service.response_time,
            'last_checked': service.last_checked.isoformat() if service.last_checked else None
        })
    
    return render_template('dashboard.html', services=services_data)

@bp.route('/service/<int:service_id>')
def service_detail(service_id):
    """Service detail page with reporting form and charts"""
    service = Service.query.get_or_404(service_id)
    
    # Get reports for the last 24 hours for the chart
    cutoff = datetime.utcnow() - timedelta(hours=24)
    reports = Report.query.filter(
        Report.service_id == service_id,
        Report.created_at >= cutoff
    ).order_by(Report.created_at.desc()).all()
    
    return render_template('service_detail.html', service=service, reports=reports)

@bp.route('/api/services')
def api_services():
    """API endpoint to get all services"""
    services = Service.query.all()
    return jsonify([{
        'id': service.id,
        'name': service.name,
        'url': service.url,
        'icon_path': service.icon_path,
        'status': service.get_status_with_anomaly(),  # Use enhanced status
        'recent_reports': service.get_recent_reports_count()
    } for service in services])

@bp.route('/api/services', methods=['POST'])
@login_required
def api_create_service():
    """API endpoint to create a new service (admin only)"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    data = request.get_json()
    if not data or not data.get('name') or not data.get('url'):
        return jsonify({'error': 'Name and URL are required'}), 400
    
    service = Service(name=data['name'], url=data['url'])
    db.session.add(service)
    db.session.commit()
    
    return jsonify({
        'id': service.id,
        'name': service.name,
        'url': service.url,
        'status': service.get_status()
    }), 201

@bp.route('/api/reports/<int:service_id>')
def api_reports(service_id):
    """API endpoint to get reports for a service"""
    service = Service.query.get_or_404(service_id)
    
    # Parse query parameters
    hours = request.args.get('hours', 24, type=int)
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    
    reports = Report.query.filter(
        Report.service_id == service_id,
        Report.created_at >= cutoff
    ).order_by(Report.created_at.desc()).all()
    
    return jsonify([report.to_dict() for report in reports])

@bp.route('/api/report', methods=['POST'])
def api_submit_report():
    """API endpoint to submit a new outage report with enhanced processing"""
    data = request.get_json()
    
    if not data or not data.get('service_id'):
        return jsonify({'error': 'Service ID is required'}), 400
    
    service = Service.query.get(data['service_id'])
    if not service:
        return jsonify({'error': 'Service not found'}), 404
    
    # Check for spam (limit reports from same IP)
    user_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR'))
    recent_cutoff = datetime.utcnow() - timedelta(minutes=5)
    recent_reports = Report.query.filter(
        Report.user_ip == user_ip,
        Report.created_at >= recent_cutoff
    ).count()
    
    if recent_reports >= 3:
        return jsonify({'error': 'Too many reports. Please wait before submitting another.'}), 429
    
    # Use enhanced outage detector for processing
    report = outage_detector.process_report(data, user_ip)
    db.session.commit()
    
    return jsonify({
        'message': 'Report submitted successfully',
        'report_id': report.id,
        'geolocation': {
            'city': report.city,
            'country': report.country,
            'region': report.region
        }
    }), 201

@bp.route('/api/chart-data/<int:service_id>')
def api_chart_data(service_id):
    """API endpoint to get chart data for a service"""
    hours = request.args.get('hours', 24, type=int)
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    
    # Group reports by hour using PostgreSQL date_trunc
    reports = db.session.query(
        func.date_trunc('hour', Report.created_at).label('hour'),
        func.count(Report.id).label('count')
    ).filter(
        Report.service_id == service_id,
        Report.created_at >= cutoff
    ).group_by(
        func.date_trunc('hour', Report.created_at)
    ).all()
    
    # Create hourly data structure
    chart_data = []
    current_time = cutoff.replace(minute=0, second=0, microsecond=0)
    end_time = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    
    report_dict = {report.hour: report.count for report in reports}
    
    while current_time <= end_time:
        chart_data.append({
            'time': current_time.strftime('%H:00'),
            'reports': report_dict.get(current_time.replace(tzinfo=None), 0)
        })
        current_time += timedelta(hours=1)
    
    return jsonify(chart_data)

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    emit('connected', {'message': 'Connected to real-time updates'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    pass


# Enhanced Analytics APIs for Outage Detection

@bp.route('/api/service/<int:service_id>/heatmap')
def api_service_heatmap(service_id):
    """Get heatmap data for a service"""
    hours = request.args.get('hours', 24, type=int)
    service = Service.query.get_or_404(service_id)
    
    heatmap_data = outage_detector.get_heatmap_data(service_id, hours)
    
    return jsonify({
        'service_id': service_id,
        'service_name': service.name,
        'hours': hours,
        'heatmap_data': heatmap_data
    })

@bp.route('/api/service/<int:service_id>/trends')
def api_service_trends(service_id):
    """Get trending data and metrics for a service"""
    hours = request.args.get('hours', 24, type=int)
    service = Service.query.get_or_404(service_id)
    
    # Get report metrics
    report_metrics = ServiceMetrics.get_metrics(service_id, 'reports', hours)
    
    # Get status change metrics
    status_metrics = ServiceMetrics.get_metrics(service_id, 'status_change', hours)
    
    # Format data for charting
    report_trend = []
    for metric in report_metrics:
        report_trend.append({
            'timestamp': metric.timestamp.isoformat(),
            'value': metric.value,
            'metadata': json.loads(metric.extra_data) if metric.extra_data else {}
        })
    
    status_changes = []
    for metric in status_metrics:
        status_changes.append({
            'timestamp': metric.timestamp.isoformat(),
            'metadata': json.loads(metric.extra_data) if metric.extra_data else {}
        })
    
    return jsonify({
        'service_id': service_id,
        'service_name': service.name,
        'hours': hours,
        'report_trend': report_trend,
        'status_changes': status_changes,
        'current_status': service.get_status_with_anomaly()
    })

@bp.route('/api/outages')
def api_outages():
    """Get outage summary and active incidents"""
    hours = request.args.get('hours', 24, type=int)
    outage_summary = outage_detector.get_outage_summary(hours)
    
    return jsonify(outage_summary)

@bp.route('/api/analytics/overview')
def api_analytics_overview():
    """Get overall analytics dashboard data"""
    hours = request.args.get('hours', 24, type=int)
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    
    # Total services
    total_services = Service.query.count()
    
    # Service status breakdown
    services = Service.query.all()
    status_counts = {'up': 0, 'issues': 0, 'down': 0}
    for service in services:
        status = service.get_status_with_anomaly()
        status_counts[status] = status_counts.get(status, 0) + 1
    
    # Total reports in timeframe
    total_reports = Report.query.filter(Report.created_at >= cutoff).count()
    
    # Active outages
    active_outages = OutageEvent.query.filter_by(status='ongoing').count()
    
    return jsonify({
        'timeframe_hours': hours,
        'summary': {
            'total_services': total_services,
            'status_breakdown': status_counts,
            'total_reports': total_reports,
            'active_outages': active_outages
        }
    })
