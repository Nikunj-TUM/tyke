# WhatsApp Integration Guide

This document explains how to use the WhatsApp integration in the Infomerics automation system.

## Overview

The WhatsApp integration allows you to send WhatsApp messages programmatically via API. It uses:

- **Node.js Service** with `whatsapp-web.js` for WhatsApp Web automation
- **RabbitMQ** for secure inter-process communication between Python and Node.js
- **Python FastAPI** endpoints for easy integration with your existing automation

## Architecture

```
Python API Endpoint → RabbitMQ Queue → Node.js WhatsApp Service → WhatsApp Web
                                                                    ↓
                                                            Your WhatsApp Account
```

### Key Features

✅ **Secure**: No exposed HTTP endpoints for WhatsApp service - all communication via internal RabbitMQ  
✅ **Reliable**: Message queuing ensures delivery even if WhatsApp is temporarily disconnected  
✅ **Asynchronous**: Non-blocking message sending  
✅ **Persistent**: WhatsApp session is saved, no need to re-scan QR code  
✅ **Scalable**: Can handle bulk messages with rate limiting  

## Setup Instructions

### 1. Start the Services

```bash
# Start all services including WhatsApp
docker-compose up -d

# Check logs
docker-compose logs -f whatsapp-service
```

### 2. Authenticate WhatsApp

When you first start the WhatsApp service, you need to authenticate by scanning a QR code.

**Option 1: Via Logs**
```bash
docker-compose logs -f whatsapp-service
# You'll see a QR code in the terminal - scan it with WhatsApp mobile app
```

**Option 2: Via API**
```bash
curl -H "X-API-Key: your_api_key_here" \
  http://localhost:8000/whatsapp/status
```

The response will include `qr_code` and `qr_image` (as data URL) if authentication is pending.

**Option 3: Via Browser**
```
Open: http://localhost:3000/qr
```

### 3. Verify Connection

Once you scan the QR code, verify the connection:

```bash
curl -H "X-API-Key: your_api_key_here" \
  http://localhost:8000/whatsapp/status
```

Response:
```json
{
  "connected": true,
  "qr_pending": false,
  "client_info": {
    "phone": "919876543210",
    "name": "Your Name",
    "platform": "android"
  },
  "rabbitmq_connected": true,
  "queue_stats": {
    "queue_name": "whatsapp_messages",
    "message_count": 0,
    "consumer_count": 1
  }
}
```

## API Endpoints

### 1. Get WhatsApp Status

**Endpoint**: `GET /whatsapp/status`

Check if WhatsApp is connected and get QR code if needed.

```bash
curl -H "X-API-Key: your_api_key_here" \
  http://localhost:8000/whatsapp/status
```

**Response**:
```json
{
  "connected": true,
  "qr_pending": false,
  "qr_code": null,
  "qr_image": null,
  "client_info": {
    "wid": "919876543210@c.us",
    "phone": "919876543210",
    "name": "Your Name",
    "platform": "android"
  },
  "error": null,
  "rabbitmq_connected": true,
  "queue_stats": {
    "queue_name": "whatsapp_messages",
    "message_count": 0,
    "consumer_count": 1
  }
}
```

### 2. Send Single WhatsApp Message

**Endpoint**: `POST /whatsapp/send`

Send a WhatsApp message to a single contact.

```bash
curl -X POST http://localhost:8000/whatsapp/send \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+919876543210",
    "message": "Hello! This is a test message from Infomerics.",
    "contact_name": "John Doe"
  }'
```

**Request Body**:
```json
{
  "phone_number": "+919876543210",  // Phone with country code
  "message": "Hello from Infomerics!",
  "contact_name": "John Doe"  // Optional
}
```

**Response**:
```json
{
  "success": true,
  "message": "Message queued successfully",
  "message_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "queued",
  "phone_number": "919876543210",
  "contact_name": "John Doe"
}
```

### 3. Send Bulk WhatsApp Messages

**Endpoint**: `POST /whatsapp/send/bulk`

Send WhatsApp messages to multiple contacts (up to 100 per request).

```bash
curl -X POST http://localhost:8000/whatsapp/send/bulk \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "contacts": [
      {
        "phone_number": "+919876543210",
        "message": "Hello John!",
        "name": "John Doe"
      },
      {
        "phone_number": "+919876543211",
        "message": "Hello Jane!",
        "name": "Jane Smith"
      }
    ]
  }'
```

**Request Body**:
```json
{
  "contacts": [
    {
      "phone_number": "+919876543210",
      "message": "Personalized message for this contact",
      "name": "John Doe"  // Optional
    }
    // ... up to 100 contacts
  ]
}
```

**Response**:
```json
{
  "success": true,
  "message": "Queued 2 messages, 0 failed",
  "total": 2,
  "queued": 2,
  "failed": 0,
  "message_ids": [
    {
      "message_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "phone_number": "919876543210",
      "contact_name": "John Doe"
    },
    {
      "message_id": "b2c3d4e5-f6g7-8901-bcde-fg2345678901",
      "phone_number": "919876543211",
      "contact_name": "Jane Smith"
    }
  ],
  "errors": []
}
```

## Python Integration Examples

### Example 1: Send Single Message

```python
from api.services.whatsapp_service import WhatsAppService

# Initialize service
whatsapp = WhatsAppService()

# Send message
result = whatsapp.send_message(
    phone_number="+919876543210",
    message="Hello! This is an automated message from Infomerics.",
    contact_name="John Doe"
)

print(f"Message ID: {result['message_id']}")
print(f"Status: {result['status']}")

# Clean up
whatsapp.close()
```

### Example 2: Send Bulk Messages

```python
from api.services.whatsapp_service import WhatsAppService

# Prepare contacts
contacts = [
    {
        'phone_number': '+919876543210',
        'message': 'Hello John! Your rating report is ready.',
        'name': 'John Doe'
    },
    {
        'phone_number': '+919876543211',
        'message': 'Hello Jane! Your rating report is ready.',
        'name': 'Jane Smith'
    }
]

# Send bulk messages
whatsapp = WhatsAppService()
result = whatsapp.send_bulk_messages(contacts)

print(f"Queued: {result['success']}")
print(f"Failed: {result['failed']}")
print(f"Message IDs: {result['message_ids']}")

whatsapp.close()
```

### Example 3: Using Context Manager

```python
from api.services.whatsapp_service import WhatsAppService

# Automatically closes connection
with WhatsAppService() as whatsapp:
    result = whatsapp.send_message(
        phone_number="+919876543210",
        message="Test message"
    )
    print(result)
```

### Example 4: Send Messages After Contact Fetch

```python
from api.services.contact_service import ContactService
from api.services.whatsapp_service import WhatsAppService

# Fetch contacts
contact_service = ContactService()
contact_result = contact_service.fetch_and_store_contacts(
    cin="L12345AB1234PLC123456",
    company_airtable_id="rec123456"
)

# Send WhatsApp messages to all contacts
if contact_result['success'] and contact_result['contacts']:
    whatsapp = WhatsAppService()
    
    contacts = []
    for contact in contact_result['contacts']:
        if contact.mobileNumber:
            contacts.append({
                'phone_number': contact.mobileNumber,
                'message': f"Hello {contact.fullName}, your company rating update is available.",
                'name': contact.fullName
            })
    
    if contacts:
        result = whatsapp.send_bulk_messages(contacts)
        print(f"Sent {result['success']} WhatsApp messages")
    
    whatsapp.close()
```

## Phone Number Formats

The service accepts phone numbers in various formats:

- `+919876543210` (with country code and +)
- `919876543210` (with country code, no +)
- `9876543210` (10-digit Indian number, auto-adds 91)

All are converted to WhatsApp format: `919876543210@c.us`

## Rate Limiting

To avoid WhatsApp bans, the Node.js service includes:

- 1-second delay between messages
- Queue-based processing (messages sent sequentially)
- Retry logic for failed messages

For bulk sending:
- API rate limits apply (configurable in `.env`)
- Messages are queued and sent at a safe rate
- Monitor queue status via `/whatsapp/status`

## Monitoring

### Check Service Health

```bash
# Docker logs
docker-compose logs -f whatsapp-service

# Health endpoint (direct to Node.js service)
curl http://localhost:3000/health
```

### Check Queue Status

```bash
# Via Python API
curl -H "X-API-Key: your_api_key_here" \
  http://localhost:8000/whatsapp/status

# RabbitMQ Management UI
# Open: http://localhost:15672 (guest/guest)
# Navigate to Queues → whatsapp_messages
```

## Troubleshooting

### Issue: QR Code Not Appearing

**Solution**:
```bash
# Restart the WhatsApp service
docker-compose restart whatsapp-service

# Check logs
docker-compose logs -f whatsapp-service
```

### Issue: Messages Not Sending

**Solution**:
1. Check WhatsApp connection status:
   ```bash
   curl -H "X-API-Key: your_api_key" http://localhost:8000/whatsapp/status
   ```

2. Check RabbitMQ queue:
   - Open http://localhost:15672
   - Check `whatsapp_messages` queue
   - If messages are stuck, check WhatsApp service logs

3. Verify phone number format:
   ```python
   # Must include country code
   phone = "+919876543210"  # ✓ Correct
   phone = "9876543210"     # ✓ OK (adds 91 automatically)
   phone = "123456"         # ✗ Too short
   ```

### Issue: WhatsApp Disconnected

**Solution**:
```bash
# Check logs for reason
docker-compose logs whatsapp-service

# If session expired, restart to get new QR code
docker-compose restart whatsapp-service

# Session data is persistent in Docker volume
# To reset completely:
docker-compose down
docker volume rm tyke_whatsapp_data tyke_whatsapp_cache
docker-compose up -d
```

### Issue: Cannot Reach WhatsApp Service

**Solution**:
1. Ensure service is running:
   ```bash
   docker-compose ps whatsapp-service
   ```

2. Check network connectivity:
   ```bash
   docker-compose exec api ping whatsapp-service
   ```

3. Verify Docker network:
   ```bash
   docker network inspect tyke_infomerics-network
   ```

## Security Considerations

1. **No Exposed Endpoints**: WhatsApp service only listens to internal RabbitMQ
2. **Port 3000**: Only for initial setup (QR code). Can be removed in production
3. **API Authentication**: All API endpoints require `X-API-Key` header
4. **Session Persistence**: WhatsApp session saved in Docker volume (secure)
5. **Rate Limiting**: Built-in rate limiting prevents abuse

## Production Recommendations

1. **Remove Port Exposure**:
   ```yaml
   # In docker-compose.yml, comment out:
   # ports:
   #   - "3000:3000"
   ```

2. **Use Environment Variables**:
   ```bash
   # Add to .env
   WHATSAPP_ENABLED=true
   ```

3. **Monitor Logs**:
   ```bash
   # Set up log aggregation
   docker-compose logs -f whatsapp-service | tee -a whatsapp.log
   ```

4. **Backup Session**:
   ```bash
   # Backup WhatsApp session data
   docker run --rm -v tyke_whatsapp_data:/data -v $(pwd):/backup \
     alpine tar czf /backup/whatsapp-session-backup.tar.gz /data
   ```

## Advanced Usage

### Custom Message Templates

```python
def send_rating_update(contact, company_name, rating):
    """Send customized rating update message"""
    message = f"""
Hello {contact['name']}!

{company_name} has received a new credit rating:

Rating: {rating}
Date: {datetime.now().strftime('%d-%b-%Y')}

For more details, please visit our portal.

Regards,
Infomerics Team
    """.strip()
    
    whatsapp = WhatsAppService()
    result = whatsapp.send_message(
        phone_number=contact['phone'],
        message=message,
        contact_name=contact['name']
    )
    whatsapp.close()
    
    return result
```

### Scheduled Messages with Celery

```python
from celery import shared_task
from api.services.whatsapp_service import WhatsAppService

@shared_task
def send_scheduled_whatsapp(phone_number, message, contact_name=None):
    """Celery task to send WhatsApp message"""
    whatsapp = WhatsAppService()
    result = whatsapp.send_message(phone_number, message, contact_name)
    whatsapp.close()
    return result

# Schedule for later
from datetime import datetime, timedelta
send_scheduled_whatsapp.apply_async(
    args=['+919876543210', 'Scheduled message!'],
    eta=datetime.now() + timedelta(hours=2)
)
```

## Support

For issues or questions:
1. Check logs: `docker-compose logs whatsapp-service`
2. Verify status: `GET /whatsapp/status`
3. Check RabbitMQ: http://localhost:15672

## References

- [whatsapp-web.js Documentation](https://wwebjs.dev/)
- [RabbitMQ Documentation](https://www.rabbitmq.com/documentation.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

