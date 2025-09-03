#!/usr/bin/env python3
"""
Service Importer for Downlight
Imports services from a text file with automatic URL generation and icon fetching
"""

import os
import re
import sys
import requests
import logging
from urllib.parse import urlparse
from datetime import datetime

# Setup Flask app context
from app import app, db
from models import Service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ServiceImporter:
    def __init__(self):
        self.icon_dir = 'static/images/logos'
        self.ensure_icon_directory()
        
        # Common URL patterns and mappings
        self.url_mappings = {
            'Amazon': 'https://amazon.com',
            'Amazon Alexa': 'https://alexa.amazon.com',
            'Amazon Music': 'https://music.amazon.com',
            'Amazon Prime Video': 'https://primevideo.com',
            'Amazon Web Services': 'https://aws.amazon.com',
            'Apple TV+': 'https://tv.apple.com',
            'Apple Music': 'https://music.apple.com',
            'Apple Store': 'https://apple.com',
            'Apple Pay': 'https://apple.com/pay',
            'App Store': 'https://apps.apple.com',
            'Google': 'https://google.com',
            'YouTube': 'https://youtube.com',
            'Gmail': 'https://gmail.com',
            'Facebook': 'https://facebook.com',
            'Instagram': 'https://instagram.com',
            'Twitter': 'https://twitter.com',
            'LinkedIn': 'https://linkedin.com',
            'WhatsApp': 'https://whatsapp.com',
            'TikTok': 'https://tiktok.com',
            'Discord': 'https://discord.com',
            'Reddit': 'https://reddit.com',
            'Spotify': 'https://spotify.com',
            'Netflix': 'https://netflix.com',
            'Twitch': 'https://twitch.tv',
            'Steam': 'https://store.steampowered.com',
            'Epic Games': 'https://epicgames.com',
            'PlayStation': 'https://playstation.com',
            'Xbox': 'https://xbox.com',
            'Microsoft': 'https://microsoft.com',
            'Office 365': 'https://office.com',
            'Adobe Creative Cloud': 'https://creative.adobe.com',
            'Dropbox': 'https://dropbox.com',
            'Zoom': 'https://zoom.us',
            'Slack': 'https://slack.com',
            'Notion': 'https://notion.so',
            'Figma': 'https://figma.com',
            'Canva': 'https://canva.com',
            'GitHub': 'https://github.com',
            'GitLab': 'https://gitlab.com'
        }
        
    def ensure_icon_directory(self):
        """Create icon directory if it doesn't exist"""
        if not os.path.exists(self.icon_dir):
            os.makedirs(self.icon_dir, exist_ok=True)
    
    def clean_service_name(self, name):
        """Clean and normalize service name"""
        # Remove special characters but keep spaces
        cleaned = re.sub(r'[^\w\s.-]', '', name)
        return cleaned.strip()
    
    def generate_url(self, service_name):
        """Generate URL for a service based on name"""
        cleaned_name = self.clean_service_name(service_name)
        
        # Check if we have a specific mapping
        if service_name in self.url_mappings:
            return self.url_mappings[service_name]
            
        # Special cases
        if 'Bank' in service_name or 'Credit Union' in service_name:
            # Banks often have complex URLs, use generic pattern
            domain = cleaned_name.lower().replace(' ', '').replace('bank', '').replace('creditunion', '')
            return f'https://{domain}bank.com'
        
        if 'Electric' in service_name or 'Power' in service_name or 'Energy' in service_name:
            # Utility companies
            domain = cleaned_name.lower().replace(' ', '').replace('electric', '').replace('power', '').replace('energy', '')[:10]
            return f'https://{domain}.com'
            
        if '.gov' in service_name.lower() or 'DMV' in service_name or 'CDC' in service_name:
            # Government sites
            if 'DMV' in service_name:
                return 'https://dmv.ca.gov'  # Default to California DMV
            elif 'CDC' in service_name:
                return 'https://cdc.gov'
            else:
                domain = cleaned_name.lower().replace(' ', '').replace('.gov', '')
                return f'https://{domain}.gov'
        
        # Gaming services
        gaming_keywords = ['Online', 'Game', 'Gaming', 'Arena', 'Legends', 'Battle', 'War']
        if any(keyword in service_name for keyword in gaming_keywords):
            domain = cleaned_name.lower().replace(' ', '').replace('online', '').replace('game', '').replace('gaming', '')[:15]
            return f'https://{domain}.com'
        
        # Airlines
        airline_keywords = ['Airlines', 'Air']
        if any(keyword in service_name for keyword in airline_keywords):
            domain = cleaned_name.lower().replace(' ', '').replace('airlines', '').replace('air', '')
            return f'https://{domain}.com'
        
        # Default pattern: try to create a reasonable URL
        # Remove common words and create domain
        words_to_remove = ['Inc', 'LLC', 'Corp', 'Corporation', 'Company', 'Co', 'The', 'And', '&']
        domain_name = cleaned_name
        for word in words_to_remove:
            domain_name = domain_name.replace(f' {word}', '').replace(f'{word} ', '')
        
        # Convert to lowercase, remove spaces, limit length
        domain = re.sub(r'[^a-z0-9]', '', domain_name.lower())[:20]
        
        # If domain is too short or generic, add common suffixes
        if len(domain) < 3:
            domain = f"{domain}app"
        
        return f'https://{domain}.com'
    
    def get_icon_url(self, service_name, service_url):
        """Get icon URL using various services"""
        # Try Google's favicon service first
        try:
            parsed_url = urlparse(service_url)
            domain = parsed_url.netloc.lower()
            
            # Google S2 favicon service
            favicon_url = f'https://www.google.com/s2/favicons?domain={domain}&sz=64'
            
            response = requests.head(favicon_url, timeout=5)
            if response.status_code == 200:
                return favicon_url
                
        except Exception as e:
            logger.warning(f"Could not fetch favicon for {service_name}: {e}")
        
        # Fallback: try direct favicon
        try:
            parsed_url = urlparse(service_url)
            domain = parsed_url.netloc
            favicon_url = f'{parsed_url.scheme}://{domain}/favicon.ico'
            
            response = requests.head(favicon_url, timeout=5)
            if response.status_code == 200:
                return favicon_url
                
        except Exception as e:
            logger.warning(f"Could not fetch direct favicon for {service_name}: {e}")
        
        return None
    
    def download_icon(self, icon_url, service_name):
        """Download and save icon locally"""
        if not icon_url:
            return None
            
        try:
            # Create safe filename
            safe_name = re.sub(r'[^\w\s-]', '', service_name.lower())
            safe_name = re.sub(r'[-\s]+', '_', safe_name)
            filename = f'{safe_name}_icon.png'
            filepath = os.path.join(self.icon_dir, filename)
            
            # Download icon
            response = requests.get(icon_url, timeout=10)
            response.raise_for_status()
            
            # Save file
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            # Return relative path for database
            return f'images/logos/{filename}'
            
        except Exception as e:
            logger.warning(f"Could not download icon for {service_name}: {e}")
            return None
    
    def import_from_file(self, filename, limit=None):
        """Import services from text file"""
        imported_count = 0
        skipped_count = 0
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if limit and imported_count >= limit:
                        break
                        
                    service_name = line.strip()
                    if not service_name:
                        continue
                    
                    # Skip if service already exists
                    existing = Service.query.filter_by(name=service_name).first()
                    if existing:
                        logger.info(f"Skipping existing service: {service_name}")
                        skipped_count += 1
                        continue
                    
                    # Generate URL
                    service_url = self.generate_url(service_name)
                    
                    # Get icon
                    icon_url = self.get_icon_url(service_name, service_url)
                    icon_path = self.download_icon(icon_url, service_name) if icon_url else None
                    
                    # Create service
                    service = Service(
                        name=service_name,
                        url=service_url,
                        icon_path=icon_path
                    )
                    
                    db.session.add(service)
                    imported_count += 1
                    
                    logger.info(f"Added service {imported_count}: {service_name} -> {service_url}")
                    
                    # Commit every 50 services to avoid large transactions
                    if imported_count % 50 == 0:
                        db.session.commit()
                        logger.info(f"Committed {imported_count} services...")
            
            # Final commit
            db.session.commit()
            logger.info(f"Import completed: {imported_count} services added, {skipped_count} skipped")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Import failed: {e}")
            raise

def main():
    """Main function to run the importer"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Import services from text file')
    parser.add_argument('filename', help='Text file containing service names')
    parser.add_argument('--limit', type=int, help='Limit number of services to import')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be imported without actually doing it')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.filename):
        print(f"Error: File {args.filename} not found")
        sys.exit(1)
    
    # Initialize Flask app context
    with app.app_context():
        importer = ServiceImporter()
        
        if args.dry_run:
            print("DRY RUN MODE - No changes will be made")
            # In dry run, just show first 10 services
            with open(args.filename, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i >= 10:
                        break
                    service_name = line.strip()
                    if service_name:
                        url = importer.generate_url(service_name)
                        print(f"{service_name} -> {url}")
        else:
            importer.import_from_file(args.filename, args.limit)

if __name__ == '__main__':
    main()