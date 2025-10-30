# WhatsApp API Endpoints

This document describes the WhatsApp-related API endpoints available in the Infomerics API.

## Base URL

```
http://localhost:8000
```

## Authentication

All endpoints require API key authentication via header:

```
X-API-Key: your_api_key_here
```

## Endpoints

### 1. Get WhatsApp Status

**GET** `/whatsapp/status`

Get the current WhatsApp connection status, including QR code if authentication is pending.

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

**Status Codes**:
- `200 OK`: Success
- `401 Unauthorized`: Invalid API key
- `500 Internal Server Error`: Server error

---

### 2. Send WhatsApp Message

**POST** `/whatsapp/send`

Send a single WhatsApp message to a contact.

**Request Body**:
```json
{
  "phone_number": "+919876543210",
  "message": "Hello! This is a test message.",
  "contact_name": "John Doe"
}
```

**Parameters**:
- `phone_number` (string, required): Phone number with country code
  - Formats accepted: `+919876543210`, `919876543210`, `9876543210`
  - Must be at least 10 digits
- `message` (string, required): Message text to send
  - Cannot be empty
  - Maximum 4096 characters
- `contact_name` (string, optional): Contact name for logging

**Response**:
```json
{
  "success": true,
  "message": "Message queued successfully",
  "message_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "queued",
  "phone_number": "919876543210",
  "contact_name": "John Doe",
  "error": null
}
```

**Status Codes**:
- `200 OK`: Message queued successfully
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Invalid API key
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

---

### 3. Send Bulk WhatsApp Messages

**POST** `/whatsapp/send/bulk`

Send WhatsApp messages to multiple contacts (up to 100 per request).

**Request Body**:
```json
{
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
}
```

**Parameters**:
- `contacts` (array, required): List of contacts
  - Minimum: 1 contact
  - Maximum: 100 contacts per request
  - Each contact has:
    - `phone_number` (string, required): Phone with country code
    - `message` (string, required): Message text
    - `name` (string, optional): Contact name

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

**Status Codes**:
- `200 OK`: Request processed (check `queued` and `failed` counts)
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Invalid API key
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

---

## Error Responses

All endpoints return errors in the following format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

Common errors:
- `Invalid API key`: Check your `X-API-Key` header
- `Phone number must be at least 10 digits`: Invalid phone format
- `Message cannot be empty`: Provide a message
- `WhatsApp service unreachable`: WhatsApp service is down

---

## Rate Limiting

Default rate limits (configurable in `.env`):
- 50 requests per hour per IP address
- Rate limit headers included in response:
  - `X-RateLimit-Limit`: Total requests allowed
  - `X-RateLimit-Remaining`: Requests remaining
  - `X-RateLimit-Reset`: Time when limit resets

---

## Message Flow

1. **API Request**: Client sends message via API
2. **Validation**: Request is validated and authenticated
3. **Queue**: Message is queued in RabbitMQ
4. **Processing**: Node.js WhatsApp service picks up message
5. **Send**: Message sent via WhatsApp Web
6. **Status**: Status updates published to status queue

Messages are processed asynchronously with 1-second delays to avoid rate limits.

---

## Examples

### cURL Examples

**Check Status**:
```bash
curl -H "X-API-Key: your_api_key" \
  http://localhost:8000/whatsapp/status
```

**Send Single Message**:
```bash
curl -X POST http://localhost:8000/whatsapp/send \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+919876543210",
    "message": "Hello from Infomerics!",
    "contact_name": "John Doe"
  }'
```

**Send Bulk Messages**:
```bash
curl -X POST http://localhost:8000/whatsapp/send/bulk \
  -H "X-API-Key: your_api_key" \
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

### Python Examples

**Using requests library**:
```python
import requests

API_KEY = "your_api_key_here"
BASE_URL = "http://localhost:8000"

# Send single message
response = requests.post(
    f"{BASE_URL}/whatsapp/send",
    headers={
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    },
    json={
        "phone_number": "+919876543210",
        "message": "Hello from Python!",
        "contact_name": "Test User"
    }
)

print(response.json())
```

**Using WhatsApp service directly**:
```python
from api.services.whatsapp_service import WhatsAppService

with WhatsAppService() as whatsapp:
    result = whatsapp.send_message(
        phone_number="+919876543210",
        message="Hello!",
        contact_name="Test User"
    )
    print(result)
```

### JavaScript Example

```javascript
const axios = require('axios');

const API_KEY = 'your_api_key_here';
const BASE_URL = 'http://localhost:8000';

async function sendWhatsAppMessage() {
  try {
    const response = await axios.post(
      `${BASE_URL}/whatsapp/send`,
      {
        phone_number: '+919876543210',
        message: 'Hello from JavaScript!',
        contact_name: 'Test User'
      },
      {
        headers: {
          'X-API-Key': API_KEY,
          'Content-Type': 'application/json'
        }
      }
    );
    
    console.log(response.data);
  } catch (error) {
    console.error('Error:', error.response?.data || error.message);
  }
}

sendWhatsAppMessage();
```

---

## API Documentation

For interactive API documentation, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Monitoring

Monitor your WhatsApp integration:

1. **API Status**: `GET /whatsapp/status`
2. **RabbitMQ UI**: http://localhost:15672 (guest/guest)
3. **WhatsApp Service**: http://localhost:3000/health
4. **Docker Logs**: `docker-compose logs -f whatsapp-service`

---

## Best Practices

1. **Phone Number Format**: Always include country code
2. **Message Length**: Keep messages under 4096 characters
3. **Rate Limiting**: Respect rate limits to avoid bans
4. **Error Handling**: Always check `success` field in response
5. **Bulk Sending**: Use `/send/bulk` for multiple messages
6. **Connection Check**: Verify WhatsApp is connected before sending

---

## Troubleshooting

### Message Not Sent

1. Check WhatsApp connection:
   ```bash
   curl -H "X-API-Key: $API_KEY" http://localhost:8000/whatsapp/status
   ```

2. Verify phone number format:
   - Must include country code
   - Remove any spaces or special characters

3. Check queue:
   - Visit http://localhost:15672
   - Check `whatsapp_messages` queue

### Rate Limit Exceeded

If you hit rate limits:
1. Wait for the limit to reset (check `X-RateLimit-Reset` header)
2. Adjust rate limits in `.env` if needed
3. Use bulk endpoint for multiple messages

### WhatsApp Disconnected

If WhatsApp disconnects:
1. Check logs: `docker-compose logs whatsapp-service`
2. Restart service: `docker-compose restart whatsapp-service`
3. Re-scan QR code if session expired

---

## Support

For more information:
- [WhatsApp Integration Guide](../WHATSAPP_INTEGRATION.md)
- [Quick Start Guide](../WHATSAPP_QUICK_START.md)
- [Test Script](../test_whatsapp_integration.py)

