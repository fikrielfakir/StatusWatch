"""
Stream Processing for Outage Detection
Handles message queuing and real-time data processing using Kafka/RabbitMQ
"""

import json
import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
import os

# Kafka imports
try:
    from kafka import KafkaProducer, KafkaConsumer
    from kafka.errors import KafkaError
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False

# RabbitMQ imports
try:
    import pika
    RABBITMQ_AVAILABLE = True
except ImportError:
    RABBITMQ_AVAILABLE = False

# Redis imports for caching
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class OutageEvent:
    """Data structure for outage events"""
    service_id: int
    service_name: str
    event_type: str  # 'user_report', 'api_detection', 'social_media'
    severity: str    # 'low', 'medium', 'high', 'critical'
    source: str      # 'twitter', 'reddit', 'google_api', 'internal'
    timestamp: str
    data: Dict
    confidence_score: float = 0.0

class KafkaStreamProcessor:
    """Kafka-based stream processor for outage events"""
    
    def __init__(self, bootstrap_servers: str = 'localhost:9092'):
        self.bootstrap_servers = bootstrap_servers
        self.producer = None
        self.consumer = None
        self.topics = {
            'outage_events': 'outage-events',
            'anomaly_detected': 'anomaly-detected',
            'status_updates': 'status-updates',
            'social_mentions': 'social-mentions'
        }
        
        if KAFKA_AVAILABLE:
            self._setup_kafka()
        else:
            logger.warning("Kafka not available, falling back to local processing")
    
    def _setup_kafka(self):
        """Initialize Kafka producer and consumer"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                retries=3,
                acks='all'
            )
            logger.info("Kafka producer initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}")
    
    def publish_event(self, topic: str, event: OutageEvent) -> bool:
        """Publish an outage event to Kafka"""
        if not self.producer:
            logger.warning("Kafka producer not available")
            return False
        
        try:
            event_data = asdict(event)
            future = self.producer.send(topic, event_data)
            result = future.get(timeout=10)
            logger.info(f"Event published to {topic}: {event.service_name}")
            return True
        except KafkaError as e:
            logger.error(f"Failed to publish event to Kafka: {e}")
            return False
    
    def consume_events(self, topic: str, callback: Callable[[OutageEvent], None]):
        """Consume events from Kafka topic"""
        if not KAFKA_AVAILABLE:
            logger.warning("Kafka not available")
            return
        
        try:
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=self.bootstrap_servers,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                group_id='outage-detection-group',
                auto_offset_reset='latest'
            )
            
            logger.info(f"Starting to consume from topic: {topic}")
            for message in consumer:
                try:
                    event_data = message.value
                    event = OutageEvent(**event_data)
                    callback(event)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
        except Exception as e:
            logger.error(f"Error setting up Kafka consumer: {e}")

class RabbitMQStreamProcessor:
    """RabbitMQ-based stream processor for outage events"""
    
    def __init__(self, connection_url: str = 'amqp://localhost'):
        self.connection_url = connection_url
        self.connection = None
        self.channel = None
        self.queues = {
            'outage_events': 'outage.events',
            'anomaly_detected': 'anomaly.detected',
            'status_updates': 'status.updates',
            'social_mentions': 'social.mentions'
        }
        
        if RABBITMQ_AVAILABLE:
            self._setup_rabbitmq()
        else:
            logger.warning("RabbitMQ not available, falling back to local processing")
    
    def _setup_rabbitmq(self):
        """Initialize RabbitMQ connection"""
        try:
            self.connection = pika.BlockingConnection(
                pika.URLParameters(self.connection_url)
            )
            self.channel = self.connection.channel()
            
            # Declare queues
            for queue_name in self.queues.values():
                self.channel.queue_declare(queue=queue_name, durable=True)
            
            logger.info("RabbitMQ connection established")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            self.connection = None
            self.channel = None
    
    def publish_event(self, queue: str, event: OutageEvent) -> bool:
        """Publish an outage event to RabbitMQ"""
        if not self.channel:
            logger.warning("RabbitMQ channel not available")
            return False
        
        try:
            event_data = json.dumps(asdict(event))
            self.channel.basic_publish(
                exchange='',
                routing_key=queue,
                body=event_data,
                properties=pika.BasicProperties(delivery_mode=2)  # Make message persistent
            )
            logger.info(f"Event published to {queue}: {event.service_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish event to RabbitMQ: {e}")
            return False
    
    def consume_events(self, queue: str, callback: Callable[[OutageEvent], None]):
        """Consume events from RabbitMQ queue"""
        if not self.channel:
            logger.warning("RabbitMQ channel not available")
            return
        
        def wrapper(ch, method, properties, body):
            try:
                event_data = json.loads(body.decode('utf-8'))
                event = OutageEvent(**event_data)
                callback(event)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        
        try:
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(queue=queue, on_message_callback=wrapper)
            logger.info(f"Starting to consume from queue: {queue}")
            self.channel.start_consuming()
        except Exception as e:
            logger.error(f"Error consuming from RabbitMQ: {e}")

class RedisCache:
    """Redis-based caching for outage detection data"""
    
    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0):
        self.redis_client = None
        
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
                self.redis_client.ping()
                logger.info("Redis connection established")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self.redis_client = None
        else:
            logger.warning("Redis not available, using memory cache")
            self._memory_cache = {}
    
    def set(self, key: str, value: str, ttl: int = 3600) -> bool:
        """Set a value in cache with TTL"""
        try:
            if self.redis_client:
                return self.redis_client.setex(key, ttl, value)
            else:
                # Fallback to memory cache
                self._memory_cache[key] = {
                    'value': value,
                    'expires': time.time() + ttl
                }
                return True
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False
    
    def get(self, key: str) -> Optional[str]:
        """Get a value from cache"""
        try:
            if self.redis_client:
                return self.redis_client.get(key)
            else:
                # Fallback to memory cache
                cached = self._memory_cache.get(key)
                if cached and cached['expires'] > time.time():
                    return cached['value']
                elif cached:
                    del self._memory_cache[key]
                return None
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return None
    
    def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter in cache"""
        try:
            if self.redis_client:
                return self.redis_client.incr(key, amount)
            else:
                # Fallback to memory cache
                current = self._memory_cache.get(key, {'value': '0'})
                new_value = int(current['value']) + amount
                self._memory_cache[key] = {
                    'value': str(new_value),
                    'expires': time.time() + 3600
                }
                return new_value
        except Exception as e:
            logger.error(f"Error incrementing cache key {key}: {e}")
            return 0

class StreamProcessorOrchestrator:
    """Orchestrates different stream processing backends"""
    
    def __init__(self, 
                 kafka_servers: Optional[str] = None,
                 rabbitmq_url: Optional[str] = None,
                 redis_host: Optional[str] = None):
        
        self.processors = []
        self.cache = RedisCache(host=redis_host or 'localhost')
        
        # Initialize available processors
        if kafka_servers and KAFKA_AVAILABLE:
            kafka_processor = KafkaStreamProcessor(kafka_servers)
            self.processors.append(kafka_processor)
            logger.info("Kafka processor added")
        
        if rabbitmq_url and RABBITMQ_AVAILABLE:
            rabbitmq_processor = RabbitMQStreamProcessor(rabbitmq_url)
            self.processors.append(rabbitmq_processor)
            logger.info("RabbitMQ processor added")
        
        if not self.processors:
            logger.warning("No stream processors available, using local processing")
    
    def publish_outage_event(self, event: OutageEvent) -> bool:
        """Publish outage event to all available processors"""
        success = False
        
        for processor in self.processors:
            try:
                if hasattr(processor, 'topics'):
                    # Kafka processor
                    topic = processor.topics['outage_events']
                else:
                    # RabbitMQ processor
                    topic = processor.queues['outage_events']
                
                if processor.publish_event(topic, event):
                    success = True
            except Exception as e:
                logger.error(f"Error publishing to processor: {e}")
        
        # Cache the event for quick access
        cache_key = f"outage:{event.service_name}:{event.timestamp}"
        self.cache.set(cache_key, json.dumps(asdict(event)), ttl=3600)
        
        return success
    
    def get_recent_events(self, service_name: str, hours: int = 1) -> List[Dict]:
        """Get recent events for a service from cache"""
        events = []
        
        # Try to get from cache first
        cache_pattern = f"outage:{service_name}:*"
        
        try:
            if self.cache.redis_client:
                keys = self.cache.redis_client.keys(cache_pattern)
                for key in keys[-50:]:  # Last 50 events
                    event_data = self.cache.get(key)
                    if event_data:
                        events.append(json.loads(event_data))
            
            # Filter by time
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
            recent_events = [
                event for event in events 
                if event.get('timestamp', '') >= cutoff
            ]
            
            return recent_events
            
        except Exception as e:
            logger.error(f"Error getting recent events: {e}")
            return []

# Factory function to create stream processor based on environment
def create_stream_processor() -> StreamProcessorOrchestrator:
    """Create stream processor based on available services"""
    
    # Try to detect available services
    kafka_servers = os.getenv('KAFKA_SERVERS', 'localhost:9092')
    rabbitmq_url = os.getenv('RABBITMQ_URL', 'amqp://localhost')
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    
    return StreamProcessorOrchestrator(
        kafka_servers=kafka_servers,
        rabbitmq_url=rabbitmq_url,
        redis_host=redis_host
    )

# Example usage
if __name__ == "__main__":
    # Create stream processor
    processor = create_stream_processor()
    
    # Create sample outage event
    sample_event = OutageEvent(
        service_id=1,
        service_name="Instagram",
        event_type="social_media",
        severity="medium",
        source="twitter",
        timestamp=datetime.now().isoformat(),
        data={"mention_count": 15, "sentiment": "negative"},
        confidence_score=0.8
    )
    
    # Publish event
    success = processor.publish_outage_event(sample_event)
    logger.info(f"Event published: {success}")
    
    # Get recent events
    recent = processor.get_recent_events("Instagram")
    logger.info(f"Recent events: {len(recent)}")