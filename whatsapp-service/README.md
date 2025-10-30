# WhatsApp Service

Node.js service using whatsapp-web.js for sending WhatsApp messages via RabbitMQ.

## Features

- WhatsApp Web integration using whatsapp-web.js
- RabbitMQ message queue for reliable message delivery
- QR code authentication
- Session persistence
- Health check endpoints
- Status updates via RabbitMQ

## Setup

1. Build and start the service:
```bash
docker-compose up whatsapp-service
```

2. Scan QR code to authenticate:
   - Check logs: `docker-compose logs -f whatsapp-service`
   - Or visit: `http://localhost:3000/qr`

3. Service is ready when you see "WhatsApp client is ready!"

## API Endpoints

- `GET /health` - Health check and status
- `GET /qr` - Get QR code for authentication
- `GET /status` - Connection status

## Message Format

Messages sent to `whatsapp_messages` queue should be JSON:

```json
{
  "message_id": "unique-id",
  "phone_number": "+919876543210",
  "message": "Hello from Infomerics!",
  "contact_name": "John Doe"
}
```

## Status Updates

The service publishes status updates to `whatsapp_status` queue:

- `qr_code` - QR code is ready
- `authenticated` - Successfully authenticated
- `ready` - Client is ready to send messages
- `message_sent` - Message sent successfully
- `message_failed` - Message failed to send
- `disconnected` - Client disconnected

