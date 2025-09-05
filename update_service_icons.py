#!/usr/bin/env python3
"""
Update Service Icons
Updates existing services to fetch and download their real icons
"""

import os
import re
import requests
import logging
from urllib.parse import urlparse

# Setup Flask app context
from app import app, db
from models import Service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_service_icons():
    """Update icons for services that don't have them"""
    
    icon_dir = 'static/images/logos'
    if not os.path.exists(icon_dir):
        os.makedirs(icon_dir, exist_ok=True)
    
    updated_count = 0
    skipped_count = 0
    
    # Get services without icons
    services = Service.query.filter(
        (Service.icon_path.is_(None)) | (Service.icon_path == '')
    ).all()
    
    logger.info(f"Found {len(services)} services without icons")
    
    for service in services:
        try:
            # Generate favicon URL
            if service.url:
                parsed_url = urlparse(service.url)
                domain = parsed_url.netloc.lower().replace('www.', '')
            else:
                # Fallback to service name
                domain = service.name.lower().replace(' ', '').replace('-', '') + '.com'
            
            # Google S2 favicon service - high resolution
            favicon_url = f'https://www.google.com/s2/favicons?domain={domain}&sz=128'
            
            # Create safe filename
            safe_name = re.sub(r'[^\w\s-]', '', service.name.lower())
            safe_name = re.sub(r'[-\s]+', '_', safe_name)
            filename = f'{safe_name}_icon.png'
            filepath = os.path.join(icon_dir, filename)
            
            # Skip if file already exists
            if os.path.exists(filepath):
                # Update database with existing path
                service.icon_path = f'images/logos/{filename}'
                updated_count += 1
                logger.info(f"Found existing icon for {service.name}")
                continue
            
            # Download icon
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(favicon_url, timeout=15, headers=headers)
            response.raise_for_status()
            
            # Only save if we got actual content
            if len(response.content) > 100:  # Avoid saving tiny error images
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                # Update database
                service.icon_path = f'images/logos/{filename}'
                updated_count += 1
                logger.info(f"Downloaded and updated icon for {service.name}")
            else:
                logger.warning(f"Icon too small for {service.name}, skipping")
                skipped_count += 1
                
        except Exception as e:
            logger.warning(f"Could not update icon for {service.name}: {e}")
            skipped_count += 1
        
        # Commit every 20 services
        if (updated_count + skipped_count) % 20 == 0:
            db.session.commit()
            logger.info(f"Processed {updated_count + skipped_count} services...")
    
    # Final commit
    db.session.commit()
    logger.info(f"Icon update completed: {updated_count} icons updated, {skipped_count} skipped")

if __name__ == '__main__':
    with app.app_context():
        update_service_icons()