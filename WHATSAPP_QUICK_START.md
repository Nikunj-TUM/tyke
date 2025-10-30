# WhatsApp Integration - Quick Start Guide

Get your WhatsApp integration up and running in 5 minutes!

## Prerequisites

- Docker and Docker Compose installed
- WhatsApp mobile app with an active account
- API key configured in `.env` file

## Step 1: Start the Services (1 minute)

```bash
# Navigate to project directory
cd /path/to/tyke

# Start all services including WhatsApp
docker-compose up -d

# Wait for services to be healthy
docker-compose ps
```

## Step 2: Authenticate WhatsApp (2 minutes)

You need to scan a QR code to authenticate WhatsApp Web.

**Method 1: Via Logs (Recommended)**
```bash
docker-compose logs -f whatsapp-service
```

You'll see a QR code printed in ASCII art. Scan it with your WhatsApp mobile app:
1. Open WhatsApp on your phone
2. Go to Settings → Linked Devices
3. Tap "Link a Device"
4. Scan the QR code shown in the terminal

**Method 2: Via Browser**
```
Open in browser: http://localhost:3000/qr
```

Once scanned, you'll see: `WhatsApp client is ready!`

## Step 3: Verify Connection (1 minute)

```bash
curl -H "X-API-Key: your_api_key_here" \
  http://localhost:8000/whatsapp/status
```

Expected response:
```json
{
  "connected": true,
  "qr_pending": false,
  "client_info": {
    "phone": "919876543210",
    "name": "Your Name"
  }
}
```

## Step 4: Send Your First Message (1 minute)

```bash
curl -X POST http://localhost:8000/whatsapp/send \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+919876543210",
    "message": "Hello! This is a test from Infomerics WhatsApp Integration!",
    "contact_name": "Test User"
  }'
```

Expected response:
```json
{
  "success": true,
  "message": "Message queued successfully",
  "message_id": "a1b2c3d4-...",
  "status": "queued"
}
```

Check your phone - you should receive the WhatsApp message within seconds!

## Step 5: Test from Python (Optional)

```python
from api.services.whatsapp_service import WhatsAppService

# Send a message
with WhatsAppService() as whatsapp:
    result = whatsapp.send_message(
        phone_number="+919876543210",
        message="Hello from Python!",
        contact_name="Test Contact"
    )
    print(f"Message ID: {result['message_id']}")
```

Or run the test script:
```bash
python test_whatsapp_integration.py
```

## Common Issues & Solutions

### Issue: QR Code Not Showing
```bash
# Restart the service
docker-compose restart whatsapp-service
docker-compose logs -f whatsapp-service
```

### Issue: Connection Lost
WhatsApp sessions can expire. Simply restart and re-scan:
```bash
docker-compose restart whatsapp-service
# Wait for QR code and scan again
```

### Issue: Messages Not Sending
1. Check WhatsApp is connected:
   ```bash
   curl -H "X-API-Key: your_api_key" http://localhost:8000/whatsapp/status
   ```

2. Check queue status:
   - Open http://localhost:15672 (RabbitMQ UI)
   - Login: guest/guest
   - Check `whatsapp_messages` queue

3. Check logs:
   ```bash
   docker-compose logs -f whatsapp-service
   ```

## What's Next?

- **Bulk Sending**: Send messages to multiple contacts
  ```bash
  curl -X POST http://localhost:8000/whatsapp/send/bulk \
    -H "X-API-Key: your_api_key" \
    -H "Content-Type: application/json" \
    -d @bulk_contacts.json
  ```

- **Integration**: Integrate with your contact fetch workflow
  ```python
  # After fetching contacts, send WhatsApp messages
  from api.services.contact_service import ContactService
  from api.services.whatsapp_service import WhatsAppService
  
  # Fetch contacts
  contacts = contact_service.fetch_and_store_contacts(...)
  
  # Send WhatsApp to all
  with WhatsAppService() as whatsapp:
      for contact in contacts['contacts']:
          if contact.mobileNumber:
              whatsapp.send_message(
                  phone_number=contact.mobileNumber,
                  message=f"Hello {contact.fullName}!",
                  contact_name=contact.fullName
              )
  ```

- **Monitoring**: Monitor your WhatsApp integration
  - RabbitMQ UI: http://localhost:15672
  - WhatsApp Service: http://localhost:3000/health
  - API Docs: http://localhost:8000/docs

## Important Notes

⚠️ **Rate Limiting**: WhatsApp may ban your number if you send too many messages. The service includes 1-second delays between messages.

⚠️ **Session Persistence**: Your WhatsApp session is saved in a Docker volume. If you remove the volume, you'll need to re-scan the QR code.

⚠️ **Production Use**: In production, remove the exposed port 3000 from docker-compose.yml after initial setup.

## Support

For detailed documentation, see: [WHATSAPP_INTEGRATION.md](./WHATSAPP_INTEGRATION.md)

For API reference, visit: http://localhost:8000/docs

