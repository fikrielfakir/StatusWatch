import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from flask_socketio import emit
from app import db, socketio
from models import Service, Report
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
            'status': status,
            'recent_reports': recent_count
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
        Report.timestamp >= cutoff
    ).order_by(Report.timestamp.desc()).all()
    
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
        'status': service.get_status(),
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
        Report.timestamp >= cutoff
    ).order_by(Report.timestamp.desc()).all()
    
    return jsonify([report.to_dict() for report in reports])

@bp.route('/api/report', methods=['POST'])
def api_submit_report():
    """API endpoint to submit a new outage report"""
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
        Report.timestamp >= recent_cutoff
    ).count()
    
    if recent_reports >= 3:
        return jsonify({'error': 'Too many reports. Please wait before submitting another.'}), 429
    
    report = Report(
        service_id=data['service_id'],
        location=data.get('location', ''),
        description=data.get('description', ''),
        latitude=data.get('latitude'),
        longitude=data.get('longitude'),
        user_ip=user_ip
    )
    
    db.session.add(report)
    db.session.commit()
    
    # Emit real-time update
    socketio.emit('new_report', {
        'service_id': service.id,
        'service_name': service.name,
        'report': report.to_dict(),
        'new_status': service.get_status()
    })
    
    return jsonify({
        'message': 'Report submitted successfully',
        'report_id': report.id
    }), 201

@bp.route('/api/chart-data/<int:service_id>')
def api_chart_data(service_id):
    """API endpoint to get chart data for a service"""
    hours = request.args.get('hours', 24, type=int)
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    
    # Group reports by hour
    reports = db.session.query(
        func.strftime('%Y-%m-%d %H:00:00', Report.timestamp).label('hour'),
        func.count(Report.id).label('count')
    ).filter(
        Report.service_id == service_id,
        Report.timestamp >= cutoff
    ).group_by(
        func.strftime('%Y-%m-%d %H:00:00', Report.timestamp)
    ).all()
    
    # Create hourly data structure
    chart_data = []
    current_time = cutoff.replace(minute=0, second=0, microsecond=0)
    end_time = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    
    report_dict = {report.hour: report.count for report in reports}
    
    while current_time <= end_time:
        hour_str = current_time.strftime('%Y-%m-%d %H:00:00')
        chart_data.append({
            'time': current_time.strftime('%H:00'),
            'reports': report_dict.get(hour_str, 0)
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
