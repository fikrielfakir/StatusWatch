"""
External API Monitoring for Outage Detection
Monitors external sources like Google, Twitter APIs for service status
"""

import requests
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import tweepy
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TwitterOutageMonitor:
    """Monitor Twitter for outage mentions and trending topics"""
    
    def __init__(self, api_key: str, api_secret: str, access_token: str, access_token_secret: str):
        try:
            auth = tweepy.OAuthHandler(api_key, api_secret)
            auth.set_access_token(access_token, access_token_secret)
            self.api = tweepy.API(auth, wait_on_rate_limit=True)
            logger.info("Twitter API initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Twitter API: {e}")
            self.api = None
    
    def search_outage_mentions(self, service_name: str, hours_back: int = 1) -> List[Dict]:
        """Search for outage-related tweets about a service"""
        if not self.api:
            return []
        
        try:
            # Keywords that indicate outages
            outage_keywords = [
                f"{service_name} down",
                f"{service_name} not working",
                f"{service_name} offline",
                f"{service_name} outage",
                f"{service_name} broken",
                f"can't access {service_name}",
                f"{service_name} error"
            ]
            
            results = []
            for keyword in outage_keywords:
                try:
                    tweets = tweepy.Cursor(
                        self.api.search_tweets,
                        q=keyword,
                        lang="en",
                        result_type="recent",
                        tweet_mode="extended"
                    ).items(50)
                    
                    for tweet in tweets:
                        # Filter tweets from last N hours
                        if (datetime.now() - tweet.created_at).total_seconds() < hours_back * 3600:
                            results.append({
                                'id': tweet.id,
                                'text': tweet.full_text,
                                'created_at': tweet.created_at.isoformat(),
                                'user': tweet.user.screen_name,
                                'retweet_count': tweet.retweet_count,
                                'favorite_count': tweet.favorite_count,
                                'keyword': keyword,
                                'service': service_name
                            })
                    
                    time.sleep(1)  # Rate limiting
                except Exception as e:
                    logger.error(f"Error searching for keyword '{keyword}': {e}")
                    continue
                    
            return results
            
        except Exception as e:
            logger.error(f"Error searching Twitter for {service_name}: {e}")
            return []
    
    def get_trending_topics(self, location_id: int = 1) -> List[Dict]:
        """Get trending topics to identify potential outages"""
        if not self.api:
            return []
        
        try:
            trends = self.api.get_place_trends(location_id)[0]['trends']
            return [
                {
                    'name': trend['name'],
                    'url': trend['url'],
                    'tweet_volume': trend.get('tweet_volume'),
                    'timestamp': datetime.now().isoformat()
                }
                for trend in trends[:10]  # Top 10 trends
            ]
        except Exception as e:
            logger.error(f"Error getting trending topics: {e}")
            return []

class GoogleStatusMonitor:
    """Monitor Google Workspace/Cloud status pages"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.status_urls = {
            'google_workspace': 'https://www.google.com/appsstatus/dashboard/',
            'google_cloud': 'https://status.cloud.google.com/',
            'youtube': 'https://www.google.com/appsstatus/dashboard/',
            'gmail': 'https://www.google.com/appsstatus/dashboard/'
        }
    
    def check_google_workspace_status(self) -> Dict:
        """Check Google Workspace status dashboard"""
        try:
            url = self.status_urls['google_workspace']
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Parse service status from the dashboard
            services = {}
            status_elements = soup.find_all('div', class_='service-status')
            
            for element in status_elements:
                service_name = element.get('data-service-name', 'Unknown')
                status_class = element.get('class', [])
                
                if 'status-green' in status_class:
                    status = 'operational'
                elif 'status-yellow' in status_class:
                    status = 'partial_outage'
                elif 'status-red' in status_class:
                    status = 'major_outage'
                else:
                    status = 'unknown'
                
                services[service_name] = {
                    'status': status,
                    'last_checked': datetime.now().isoformat()
                }
            
            return {
                'source': 'google_workspace',
                'services': services,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking Google Workspace status: {e}")
            return {'source': 'google_workspace', 'services': {}, 'error': str(e)}
    
    def check_google_cloud_status(self) -> Dict:
        """Check Google Cloud status"""
        try:
            url = self.status_urls['google_cloud']
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Try to find JSON data or parse HTML
            if 'application/json' in response.headers.get('content-type', ''):
                data = response.json()
                return {
                    'source': 'google_cloud',
                    'data': data,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                # Parse HTML for status information
                soup = BeautifulSoup(response.content, 'html.parser')
                incidents = []
                
                # Look for incident information
                incident_elements = soup.find_all('div', class_='incident')
                for incident in incident_elements:
                    title = incident.find('h3')
                    status = incident.find('span', class_='status')
                    
                    incidents.append({
                        'title': title.text.strip() if title else 'Unknown',
                        'status': status.text.strip() if status else 'Unknown',
                        'timestamp': datetime.now().isoformat()
                    })
                
                return {
                    'source': 'google_cloud',
                    'incidents': incidents,
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error checking Google Cloud status: {e}")
            return {'source': 'google_cloud', 'incidents': [], 'error': str(e)}

class SocialMediaScraper:
    """Scrape social media mentions for outage detection"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape_reddit_mentions(self, service_name: str) -> List[Dict]:
        """Scrape Reddit for service mentions"""
        try:
            # Search Reddit for service outage mentions
            search_terms = [
                f"{service_name} down",
                f"{service_name} not working",
                f"{service_name} outage"
            ]
            
            results = []
            for term in search_terms:
                try:
                    url = f"https://www.reddit.com/search.json?q={term}&sort=new&limit=25"
                    response = self.session.get(url, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        posts = data.get('data', {}).get('children', [])
                        
                        for post in posts:
                            post_data = post.get('data', {})
                            
                            # Filter recent posts (last 24 hours)
                            created_utc = post_data.get('created_utc', 0)
                            if time.time() - created_utc < 24 * 3600:
                                results.append({
                                    'title': post_data.get('title', ''),
                                    'selftext': post_data.get('selftext', ''),
                                    'subreddit': post_data.get('subreddit', ''),
                                    'score': post_data.get('score', 0),
                                    'num_comments': post_data.get('num_comments', 0),
                                    'created_utc': created_utc,
                                    'url': f"https://reddit.com{post_data.get('permalink', '')}",
                                    'search_term': term,
                                    'service': service_name
                                })
                    
                    time.sleep(1)  # Rate limiting
                    
                except Exception as e:
                    logger.error(f"Error scraping Reddit for '{term}': {e}")
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"Error scraping Reddit for {service_name}: {e}")
            return []
    
    def scrape_downdetector_data(self, service_name: str) -> Dict:
        """Scrape DownDetector for comparison data"""
        try:
            # Format service name for DownDetector URL
            service_slug = service_name.lower().replace(' ', '-')
            url = f"https://downdetector.com/status/{service_slug}"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract current status
            status_element = soup.find('div', class_='status-indicator')
            current_status = 'unknown'
            
            if status_element:
                if 'green' in status_element.get('class', []):
                    current_status = 'operational'
                elif 'yellow' in status_element.get('class', []):
                    current_status = 'issues'
                elif 'red' in status_element.get('class', []):
                    current_status = 'down'
            
            # Extract report count
            report_count = 0
            report_element = soup.find('span', class_='report-count')
            if report_element:
                report_text = report_element.text.strip()
                numbers = re.findall(r'\d+', report_text)
                if numbers:
                    report_count = int(numbers[0])
            
            return {
                'service': service_name,
                'status': current_status,
                'report_count': report_count,
                'url': url,
                'timestamp': datetime.now().isoformat(),
                'source': 'downdetector'
            }
            
        except Exception as e:
            logger.error(f"Error scraping DownDetector for {service_name}: {e}")
            return {
                'service': service_name,
                'status': 'unknown',
                'report_count': 0,
                'error': str(e),
                'source': 'downdetector'
            }

class ExternalMonitorOrchestrator:
    """Orchestrates all external monitoring sources"""
    
    def __init__(self, twitter_credentials: Optional[Dict] = None, google_api_key: Optional[str] = None):
        self.twitter_monitor = None
        self.google_monitor = GoogleStatusMonitor(google_api_key)
        self.social_scraper = SocialMediaScraper()
        
        if twitter_credentials:
            self.twitter_monitor = TwitterOutageMonitor(**twitter_credentials)
    
    def check_service_status(self, service_name: str) -> Dict:
        """Check service status across all external sources"""
        results = {
            'service': service_name,
            'timestamp': datetime.now().isoformat(),
            'sources': {}
        }
        
        # Twitter monitoring
        if self.twitter_monitor:
            try:
                twitter_mentions = self.twitter_monitor.search_outage_mentions(service_name)
                results['sources']['twitter'] = {
                    'mention_count': len(twitter_mentions),
                    'mentions': twitter_mentions[:10],  # Limit to first 10
                    'status': 'issues' if len(twitter_mentions) > 5 else 'operational'
                }
            except Exception as e:
                results['sources']['twitter'] = {'error': str(e)}
        
        # Google services check
        try:
            if service_name.lower() in ['gmail', 'google', 'youtube', 'google drive']:
                google_status = self.google_monitor.check_google_workspace_status()
                results['sources']['google'] = google_status
        except Exception as e:
            results['sources']['google'] = {'error': str(e)}
        
        # Reddit scraping
        try:
            reddit_mentions = self.social_scraper.scrape_reddit_mentions(service_name)
            results['sources']['reddit'] = {
                'mention_count': len(reddit_mentions),
                'mentions': reddit_mentions[:5],  # Limit to first 5
                'status': 'issues' if len(reddit_mentions) > 3 else 'operational'
            }
        except Exception as e:
            results['sources']['reddit'] = {'error': str(e)}
        
        # DownDetector comparison
        try:
            downdetector_data = self.social_scraper.scrape_downdetector_data(service_name)
            results['sources']['downdetector'] = downdetector_data
        except Exception as e:
            results['sources']['downdetector'] = {'error': str(e)}
        
        # Aggregate status
        results['aggregated_status'] = self._aggregate_status(results['sources'])
        
        return results
    
    def _aggregate_status(self, sources: Dict) -> str:
        """Aggregate status from multiple sources"""
        statuses = []
        
        for source, data in sources.items():
            if isinstance(data, dict) and 'status' in data:
                statuses.append(data['status'])
        
        # Priority: down > issues > operational
        if 'down' in statuses or 'major_outage' in statuses:
            return 'down'
        elif 'issues' in statuses or 'partial_outage' in statuses:
            return 'issues'
        elif 'operational' in statuses:
            return 'operational'
        else:
            return 'unknown'

# Example usage function
def monitor_service_external(service_name: str, credentials: Optional[Dict] = None) -> Dict:
    """Monitor a service using external sources"""
    orchestrator = ExternalMonitorOrchestrator(
        twitter_credentials=credentials.get('twitter') if credentials else None,
        google_api_key=credentials.get('google_api_key') if credentials else None
    )
    
    return orchestrator.check_service_status(service_name)

if __name__ == "__main__":
    # Test the monitoring system
    test_services = ['Instagram', 'WhatsApp', 'Gmail', 'YouTube']
    
    for service in test_services:
        logger.info(f"Testing monitoring for {service}")
        result = monitor_service_external(service)
        logger.info(f"Result: {json.dumps(result, indent=2)}")
        time.sleep(2)