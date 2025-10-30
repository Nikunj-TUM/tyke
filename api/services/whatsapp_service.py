"""
WhatsApp messaging service - communicates with Node.js whatsapp-web.js service via RabbitMQ
"""
import logging
import json
import uuid
from typing import Optional, Dict, Any, List
import pika
from datetime import datetime

from ..config import settings

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Service to send WhatsApp messages via RabbitMQ to Node.js whatsapp-web.js service"""
    
    MESSAGE_QUEUE = 'whatsapp_messages'
    STATUS_QUEUE = 'whatsapp_status'
    
    def __init__(self):
        """Initialize RabbitMQ connection"""
        self.connection = None
        self.channel = None
        self._connect()
    
    def _connect(self):
        """Establish RabbitMQ connection"""
        try:
            credentials = pika.PlainCredentials('guest', 'guest')
            parameters = pika.ConnectionParameters(
                host=settings.RABBITMQ_HOST,
                port=5672,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # Declare queues (idempotent)
            self.channel.queue_declare(queue=self.MESSAGE_QUEUE, durable=True)
            self.channel.queue_declare(queue=self.STATUS_QUEUE, durable=True)
            
            logger.info("Connected to RabbitMQ for WhatsApp messaging")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    def _ensure_connection(self):
        """Ensure connection is alive, reconnect if needed"""
        try:
            if self.connection is None or self.connection.is_closed:
                self._connect()
            elif self.channel is None or self.channel.is_closed:
                self.channel = self.connection.channel()
                self.channel.queue_declare(queue=self.MESSAGE_QUEUE, durable=True)
                self.channel.queue_declare(queue=self.STATUS_QUEUE, durable=True)
        except Exception as e:
            logger.error(f"Error ensuring connection: {e}")
            self._connect()
    
    def send_message(
        self,
        phone_number: str,
        message: str,
        contact_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Queue a WhatsApp message to be sent
        
        Args:
            phone_number: Phone number with country code (e.g., +919876543210)
            message: Message text to send
            contact_name: Optional contact name for logging
            
        Returns:
            Dict with message_id and status
        """
        try:
            self._ensure_connection()
            
            message_id = str(uuid.uuid4())
            
            message_data = {
                'message_id': message_id,
                'phone_number': phone_number,
                'message': message,
                'contact_name': contact_name or phone_number,
                'queued_at': datetime.now().isoformat()
            }
            
            self.channel.basic_publish(
                exchange='',
                routing_key=self.MESSAGE_QUEUE,
                body=json.dumps(message_data),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type='application/json'
                )
            )
            
            logger.info(f"WhatsApp message queued: {message_id} for {contact_name} ({phone_number})")
            
            return {
                'success': True,
                'message_id': message_id,
                'status': 'queued',
                'phone_number': phone_number,
                'contact_name': contact_name
            }
            
        except Exception as e:
            logger.error(f"Failed to queue WhatsApp message: {e}")
            return {
                'success': False,
                'error': str(e),
                'phone_number': phone_number,
                'contact_name': contact_name
            }
    
    def send_bulk_messages(self, contacts: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Queue multiple WhatsApp messages
        
        Args:
            contacts: List of dicts with 'phone_number', 'message', 'name'
            
        Returns:
            Dict with success and failure counts and message IDs
        """
        success_count = 0
        failure_count = 0
        message_ids = []
        errors = []
        
        for contact in contacts:
            result = self.send_message(
                phone_number=contact['phone_number'],
                message=contact['message'],
                contact_name=contact.get('name')
            )
            
            if result.get('success'):
                success_count += 1
                message_ids.append({
                    'message_id': result['message_id'],
                    'phone_number': contact['phone_number'],
                    'contact_name': contact.get('name')
                })
            else:
                failure_count += 1
                errors.append({
                    'phone_number': contact['phone_number'],
                    'error': result.get('error')
                })
        
        logger.info(f"Bulk WhatsApp send complete: {success_count} queued, {failure_count} failed")
        
        return {
            'success': success_count,
            'failed': failure_count,
            'total': len(contacts),
            'message_ids': message_ids,
            'errors': errors
        }
    
    def get_connection_status(self) -> Dict[str, Any]:
        """
        Get WhatsApp connection status from the Node.js service
        
        This method can be enhanced to check the status queue or
        call the Node.js service health endpoint directly
        
        Returns:
            Dict with connection status
        """
        try:
            # For now, return RabbitMQ connection status
            # In production, you might want to call the Node.js /health endpoint
            return {
                'rabbitmq_connected': self.connection is not None and not self.connection.is_closed,
                'channel_open': self.channel is not None and not self.channel.is_closed,
                'message_queue': self.MESSAGE_QUEUE,
                'status_queue': self.STATUS_QUEUE
            }
        except Exception as e:
            logger.error(f"Error getting connection status: {e}")
            return {
                'error': str(e),
                'rabbitmq_connected': False
            }
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the message queue
        
        Returns:
            Dict with queue statistics
        """
        try:
            self._ensure_connection()
            
            # Declare queue to get message count (passive=False to ensure it exists)
            method = self.channel.queue_declare(queue=self.MESSAGE_QUEUE, durable=True, passive=False)
            
            return {
                'queue_name': self.MESSAGE_QUEUE,
                'message_count': method.method.message_count,
                'consumer_count': method.method.consumer_count
            }
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {
                'error': str(e)
            }
    
    def close(self):
        """Close RabbitMQ connection"""
        try:
            if self.channel and not self.channel.is_closed:
                self.channel.close()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("Closed RabbitMQ connection")
        except Exception as e:
            logger.error(f"Error closing connection: {e}")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close connection"""
        self.close()


class WhatsAppStatusListener:
    """
    Service to listen to WhatsApp status updates from the Node.js service
    
    This can be used in a separate worker or background task to process
    status updates (message sent, failed, etc.)
    """
    
    STATUS_QUEUE = 'whatsapp_status'
    
    def __init__(self):
        """Initialize RabbitMQ connection for status listening"""
        self.connection = None
        self.channel = None
        self._connect()
    
    def _connect(self):
        """Establish RabbitMQ connection"""
        try:
            credentials = pika.PlainCredentials('guest', 'guest')
            parameters = pika.ConnectionParameters(
                host=settings.RABBITMQ_HOST,
                port=5672,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # Declare status queue
            self.channel.queue_declare(queue=self.STATUS_QUEUE, durable=True)
            
            logger.info("Connected to RabbitMQ for WhatsApp status updates")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    def consume_status_updates(self, callback):
        """
        Start consuming status updates
        
        Args:
            callback: Function to call with status update (receives dict)
        """
        def on_message(ch, method, properties, body):
            try:
                status_data = json.loads(body.decode())
                logger.info(f"Received status update: {status_data.get('status')}")
                
                # Call the callback function
                callback(status_data)
                
                # Acknowledge the message
                ch.basic_ack(delivery_tag=method.delivery_tag)
                
            except Exception as e:
                logger.error(f"Error processing status update: {e}")
                # Reject and don't requeue on error
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        
        logger.info(f"Starting to consume status updates from {self.STATUS_QUEUE}")
        self.channel.basic_consume(
            queue=self.STATUS_QUEUE,
            on_message_callback=on_message,
            auto_ack=False
        )
        
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.channel.stop_consuming()
            self.close()
    
    def close(self):
        """Close RabbitMQ connection"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("Closed RabbitMQ status listener connection")
        except Exception as e:
            logger.error(f"Error closing connection: {e}")

