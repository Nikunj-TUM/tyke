# Infomerics Scraper API - Setup Guide

## Quick Start

### Step 1: Get Your Airtable Base ID

1. Go to your Airtable base in the browser
2. The URL will look like: `https://airtable.com/appXXXXXXXXXXXXXX/...`
3. Copy the part that starts with `app` (e.g., `appXXXXXXXXXXXXXX`)
4. This is your `AIRTABLE_BASE_ID`

### Step 2: Create Environment File

```bash
# Copy the example file
cp env.example .env
```

Edit the `.env` file with your values:

```bash
# Airtable Configuration
AIRTABLE_API_KEY=56c9b82f7ce2bbe335831e18daa113547acc800f3dc7a5d93e6b64a980f35e65
AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX  # Replace with your actual base ID

# API Configuration (create a secure random string)
API_KEY=your_secure_api_key_here  # Replace with a strong random key

# Environment
ENVIRONMENT=production
LOG_LEVEL=INFO
```

**To generate a secure API key:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Step 3: Run with Docker (Recommended)

```bash
# Build and start the API
docker-compose up --build -d

# Check logs
docker-compose logs -f

# Stop the API
docker-compose down
```

The API will be available at `http://localhost:8000`

### Step 4: Test the API

#### 1. Health Check (no auth required)
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-21T...",
  "environment": "production"
}
```

#### 2. Start a Scraping Job
```bash
curl -X POST "http://localhost:8000/infomerics/scrape" \
  -H "X-API-Key: your_secure_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2025-10-01",
    "end_date": "2025-10-05"
  }'
```

Expected response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Scraping job queued for 2025-10-01 to 2025-10-05",
  "created_at": "2025-10-21T..."
}
```

#### 3. Check Job Status
```bash
curl -X GET "http://localhost:8000/infomerics/jobs/550e8400-e29b-41d4-a716-446655440000" \
  -H "X-API-Key: your_secure_api_key_here"
```

Expected response (while running):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "progress": 45,
  "total_extracted": 120,
  "uploaded_to_airtable": 60,
  "companies_created": 25,
  "ratings_created": 58,
  "errors": [],
  "created_at": "2025-10-21T...",
  "updated_at": "2025-10-21T...",
  "start_date": "2025-10-01",
  "end_date": "2025-10-05"
}
```

## Alternative: Run Locally (Without Docker)

### Prerequisites
- Python 3.11 or higher
- pip

### Installation

```bash
# Install dependencies
pip install -r api/requirements.txt

# Run the API
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## Verifying Airtable Integration

After a successful job:

1. Check your Airtable base
2. Go to the **Companies** table - you should see new company records
3. Go to the **Credit Ratings** table - you should see new rating records linked to companies
4. Each rating should have:
   - Company link
   - Instrument category
   - Rating
   - Outlook
   - Instrument amount
   - Date
   - Source URL

## Troubleshooting

### Error: "Invalid API Key"
- Make sure the `X-API-Key` header matches the `API_KEY` in your `.env` file

### Error: "Missing API Key"
- Add the header: `-H "X-API-Key: your_api_key_here"`

### Error: Airtable authentication failed
- Verify your `AIRTABLE_API_KEY` is correct
- Verify your `AIRTABLE_BASE_ID` is correct
- Check that the API key has write permissions to the base

### Error: "Date range cannot exceed 90 days"
- Reduce your date range to 90 days or less
- Or modify `MAX_DATE_RANGE_DAYS` in `.env`

### Job stays in "queued" status
- Check Docker logs: `docker-compose logs -f`
- The background worker may have encountered an error

### Job fails with errors
- Check the `errors` array in the job status response
- Review Docker logs for detailed error messages
- Common issues:
  - Network connectivity to Infomerics website
  - Invalid date range
  - Airtable API rate limits

## API Documentation

Once the API is running, visit:
- **Interactive docs**: http://localhost:8000/docs
- **Alternative docs**: http://localhost:8000/redoc

## Security Notes

1. **Never commit `.env` file to git**
2. Use strong, random API keys in production
3. Configure CORS properly for production (don't use "*")
4. Consider using HTTPS in production
5. Implement additional authentication for production (OAuth2, JWT)
6. Monitor rate limits and adjust as needed

## Production Deployment

For production deployment:

1. **Use a reverse proxy**: nginx, Caddy, or Traefik
2. **Enable HTTPS**: Use Let's Encrypt certificates
3. **Set up monitoring**: Prometheus, Grafana, or cloud monitoring
4. **Configure logging**: Send logs to centralized logging system
5. **Use Redis**: Replace in-memory job storage with Redis
6. **Scale horizontally**: Deploy multiple instances with load balancer
7. **Set resource limits**: Configure Docker memory and CPU limits

Example nginx configuration:
```nginx
server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## Support

For issues or questions, check:
1. API logs: `docker-compose logs -f`
2. Job status endpoint for detailed error messages
3. Airtable API status page
4. Original scraper test files in `infomerics/` directory

