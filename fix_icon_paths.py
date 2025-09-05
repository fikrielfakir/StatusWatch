#!/usr/bin/env python3
"""
Fix Icon Paths
Updates service icon paths to match the actual downloaded files
"""

import os
import glob
from app import app, db
from models import Service

def fix_icon_paths():
    """Fix icon paths to match downloaded files"""
    
    # Get all icon files in the logos directory
    icon_files = glob.glob('static/images/logos/*_icon.png')
    
    # Create mapping of service names to icon files
    icon_mapping = {}
    for icon_file in icon_files:
        # Extract service name from filename
        filename = os.path.basename(icon_file)
        # Remove _icon.png and convert underscores to spaces
        service_name_guess = filename.replace('_icon.png', '').replace('_', ' ')
        icon_mapping[service_name_guess.lower()] = f'images/logos/{filename}'
    
    print(f"Found {len(icon_mapping)} icon files")
    
    # Update services in database
    services = Service.query.all()
    updated_count = 0
    
    for service in services:
        service_name_lower = service.name.lower()
        
        # Try exact match first
        if service_name_lower in icon_mapping:
            service.icon_path = icon_mapping[service_name_lower]
            updated_count += 1
            print(f"Updated {service.name} -> {service.icon_path}")
        else:
            # Try partial matches for common naming patterns
            found = False
            for icon_name, icon_path in icon_mapping.items():
                # Check if service name is contained in icon name or vice versa
                if (service_name_lower in icon_name or 
                    icon_name in service_name_lower or
                    service_name_lower.replace(' ', '') == icon_name.replace(' ', '')):
                    service.icon_path = icon_path
                    updated_count += 1
                    print(f"Updated {service.name} -> {service.icon_path}")
                    found = True
                    break
            
            if not found:
                print(f"No icon found for {service.name}")
    
    db.session.commit()
    print(f"Updated {updated_count} services with correct icon paths")

if __name__ == '__main__':
    with app.app_context():
        fix_icon_paths()