# Quick Start Guide - 5 Minutes to Running API

## Step 1: Get Airtable Base ID (1 min)

1. Open your Airtable base in a browser
2. Look at the URL: `https://airtable.com/appXXXXXXXXXXXXXX/...`
3. Copy the `appXXXXXXXXXXXXXX` part

## Step 2: Configure Environment (1 min)

Create a file named `.env` in the project root:

```bash
cat > .env << 'EOF'
# Airtable Configuration
AIRTABLE_API_KEY=56c9b82f7ce2bbe335831e18daa113547acc800f3dc7a5d93e6b64a980f35e65
AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX

# API Configuration
API_KEY=my-secret-api-key-12345

# Environment
ENVIRONMENT=production
LOG_LEVEL=INFO
EOF
```

**Replace:**
- `appXXXXXXXXXXXXXX` with your actual Airtable Base ID from Step 1
- `my-secret-api-key-12345` with a secure random string (or keep for testing)

## Step 3: Start the API (2 min)

```bash
# Start with Docker
docker-compose up --build -d

# Wait for startup
sleep 10

# Check health
curl http://localhost:8000/health
```

Expected output:
```json
{
  "status": "healthy",
  "timestamp": "...",
  "environment": "production"
}
```

## Step 4: Run Your First Scrape (1 min)

```bash
# Start a scraping job
curl -X POST "http://localhost:8000/infomerics/scrape" \
  -H "X-API-Key: my-secret-api-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2025-10-09",
    "end_date": "2025-10-12"
  }'
```

You'll get a response with a `job_id`. Copy it!

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Scraping job queued for 2025-10-09 to 2025-10-12",
  "created_at": "..."
}
```

## Step 5: Check Job Status

```bash
# Replace JOB_ID with your actual job_id from Step 4
curl -X GET "http://localhost:8000/infomerics/jobs/550e8400-e29b-41d4-a716-446655440000" \
  -H "X-API-Key: my-secret-api-key-12345"
```

Status values:
- `queued` - Job is waiting to start
- `running` - Job is currently processing
- `completed` - Job finished successfully
- `failed` - Job encountered an error

## Automated Test

Or use the provided test script:

```bash
# Edit the script to set your API key
export API_KEY=my-secret-api-key-12345

# Run the test
./test_api.sh
```

## View Results in Airtable

1. Open your Airtable base
2. Go to the **Companies** table - see new companies
3. Go to the **Credit Ratings** table - see new ratings with links to companies

## Troubleshooting

### "Invalid API Key"
Make sure the `X-API-Key` header matches the `API_KEY` in your `.env` file.

### "Airtable authentication failed"
- Check `AIRTABLE_API_KEY` is correct
- Check `AIRTABLE_BASE_ID` is correct (should start with `app`)

### Docker not working
```bash
# Check if Docker is running
docker ps

# View logs
docker-compose logs -f

# Restart
docker-compose restart
```

## Next Steps

- Read [SETUP.md](SETUP.md) for detailed configuration
- Read [api/README.md](api/README.md) for full API documentation
- Check the interactive API docs at http://localhost:8000/docs

## Security Note

**Never commit the `.env` file to git!** It contains sensitive credentials.

The `.gitignore` file is already configured to exclude it.

