#!/usr/bin/env python3
"""
Database Migration Script
Migrates from the current database schema to the optimized schema
"""

import logging
from datetime import datetime
from app import app, db
from sqlalchemy import text
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def backup_existing_data():
    """Backup existing data before migration"""
    logger.info("Backing up existing data...")
    
    backup_data = {
        'users': [],
        'services': [],
        'reports': []
    }
    
    try:
        # Backup users
        users = db.session.execute(text("SELECT * FROM user")).fetchall()
        for user in users:
            backup_data['users'].append(dict(user._mapping))
        
        # Backup services
        services = db.session.execute(text("SELECT * FROM service")).fetchall()
        for service in services:
            backup_data['services'].append(dict(service._mapping))
        
        # Backup reports
        reports = db.session.execute(text("SELECT * FROM report")).fetchall()
        for report in reports:
            backup_data['reports'].append(dict(report._mapping))
            
        logger.info(f"Backed up {len(backup_data['users'])} users, {len(backup_data['services'])} services, {len(backup_data['reports'])} reports")
        return backup_data
        
    except Exception as e:
        logger.warning(f"Could not backup existing data: {e}")
        return backup_data

def apply_schema_migration():
    """Apply the optimized database schema"""
    logger.info("Applying optimized database schema...")
    
    try:
        # Read and execute the optimized schema
        with open('database_schema_optimized.sql', 'r') as f:
            schema_sql = f.read()
        
        # Execute the schema in chunks
        statements = schema_sql.split(';')
        for statement in statements:
            statement = statement.strip()
            if statement and not statement.startswith('--'):
                try:
                    db.session.execute(text(statement))
                    db.session.commit()
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Statement failed: {statement[:100]}... Error: {e}")
                    
        logger.info("Schema migration completed successfully")
        
    except Exception as e:
        logger.error(f"Schema migration failed: {e}")
        db.session.rollback()
        raise

def migrate_existing_data(backup_data):
    """Migrate existing data to new schema"""
    logger.info("Migrating existing data to new schema...")
    
    try:
        # Create default service type if needed
        social_media_type_id = db.session.execute(
            text("INSERT INTO service_types (name, description, icon_class) VALUES ('Social Media', 'Social networking platforms', 'fas fa-users') ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id")
        ).scalar()
        
        if not social_media_type_id:
            social_media_type_id = db.session.execute(
                text("SELECT id FROM service_types WHERE name = 'Social Media'")
            ).scalar()
        
        # Migrate users
        for user_data in backup_data['users']:
            try:
                db.session.execute(text("""
                    INSERT INTO users (id, username, email, password_hash, is_admin, created_at)
                    VALUES (:id, :username, :email, :password_hash, :is_admin, :created_at)
                    ON CONFLICT (id) DO UPDATE SET
                        username = EXCLUDED.username,
                        email = EXCLUDED.email,
                        password_hash = EXCLUDED.password_hash,
                        is_admin = EXCLUDED.is_admin
                """), {
                    'id': user_data['id'],
                    'username': user_data['username'],
                    'email': user_data['email'],
                    'password_hash': user_data['password_hash'],
                    'is_admin': user_data.get('is_admin', False),
                    'created_at': user_data.get('created_at', datetime.utcnow())
                })
            except Exception as e:
                logger.warning(f"Failed to migrate user {user_data.get('username')}: {e}")
        
        # Migrate services
        for service_data in backup_data['services']:
            try:
                db.session.execute(text("""
                    INSERT INTO services (id, type_id, name, url, icon_path, current_status, last_checked, response_time, created_at)
                    VALUES (:id, :type_id, :name, :url, :icon_path, :current_status, :last_checked, :response_time, :created_at)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        url = EXCLUDED.url,
                        icon_path = EXCLUDED.icon_path,
                        current_status = EXCLUDED.current_status,
                        last_checked = EXCLUDED.last_checked,
                        response_time = EXCLUDED.response_time
                """), {
                    'id': service_data['id'],
                    'type_id': social_media_type_id,
                    'name': service_data['name'],
                    'url': service_data['url'],
                    'icon_path': service_data.get('icon_path'),
                    'current_status': service_data.get('current_status', 'up'),
                    'last_checked': service_data.get('last_checked'),
                    'response_time': int(service_data['response_time']) if service_data.get('response_time') else None,
                    'created_at': service_data.get('created_at', datetime.utcnow())
                })
            except Exception as e:
                logger.warning(f"Failed to migrate service {service_data.get('name')}: {e}")
        
        # Migrate reports
        for report_data in backup_data['reports']:
            try:
                db.session.execute(text("""
                    INSERT INTO outage_reports (id, service_id, user_id, description, country, region, city, latitude, longitude, user_ip, created_at)
                    VALUES (:id, :service_id, :user_id, :description, :country, :region, :city, :latitude, :longitude, :user_ip, :created_at)
                    ON CONFLICT (id) DO NOTHING
                """), {
                    'id': report_data['id'],
                    'service_id': report_data['service_id'],
                    'user_id': report_data.get('user_id'),
                    'description': report_data.get('description'),
                    'country': report_data.get('country'),
                    'region': report_data.get('region'),
                    'city': report_data.get('city'),
                    'latitude': report_data.get('latitude'),
                    'longitude': report_data.get('longitude'),
                    'user_ip': report_data.get('user_ip'),
                    'created_at': report_data.get('timestamp', datetime.utcnow())
                })
            except Exception as e:
                logger.warning(f"Failed to migrate report {report_data.get('id')}: {e}")
        
        db.session.commit()
        logger.info("Data migration completed successfully")
        
    except Exception as e:
        logger.error(f"Data migration failed: {e}")
        db.session.rollback()
        raise

def main():
    """Main migration function"""
    logger.info("Starting database migration...")
    
    with app.app_context():
        try:
            # Step 1: Backup existing data
            backup_data = backup_existing_data()
            
            # Step 2: Apply new schema
            apply_schema_migration()
            
            # Step 3: Migrate existing data
            migrate_existing_data(backup_data)
            
            logger.info("Database migration completed successfully!")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise

if __name__ == "__main__":
    main()