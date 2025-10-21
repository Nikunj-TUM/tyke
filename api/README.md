# Infomerics Scraper API

Production-grade FastAPI application for scraping Infomerics press releases and storing data in Airtable.

## Features

- **Asynchronous Job Processing**: Submit scraping jobs and track their progress
- **Secure API**: API key authentication and rate limiting
- **Airtable Integration**: Automatic upsert of Companies and Credit Ratings
- **Docker Support**: Containerized deployment
- **Production-Ready**: Comprehensive error handling, logging, and monitoring

## Setup

### 1. Environment Variables

Create a `.env` file in the project root (use `env.example` as template):

```bash
# Copy the example file
cp env.example .env

# Edit with your credentials
nano .env
```

Required environment variables:
- `AIRTABLE_API_KEY`: Your Airtable API key (provided: 56c9b82f7ce2bbe335831e18daa113547acc800f3dc7a5d93e6b64a980f35e65)
- `AIRTABLE_BASE_ID`: Your Airtable base ID (extract from Airtable URL)
- `API_KEY`: Your chosen API key for securing the endpoint

### 2. Local Development

```bash
# Install dependencies
pip install -r api/requirements.txt

# Run the API
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up --build

# Or build and run manually
docker build -t infomerics-api .
docker run -p 8000:8000 --env-file .env infomerics-api
```

## API Endpoints

### POST /infomerics/scrape

Start a scraping job for the given date range.

**Request:**
```bash
curl -X POST "http://localhost:8000/infomerics/scrape" \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2025-10-01",
    "end_date": "2025-10-15"
  }'
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Scraping job queued for 2025-10-01 to 2025-10-15",
  "created_at": "2025-10-21T10:30:00"
}
```

### GET /infomerics/jobs/{job_id}

Get the status and results of a scraping job.

**Request:**
```bash
curl -X GET "http://localhost:8000/infomerics/jobs/550e8400-e29b-41d4-a716-446655440000" \
  -H "X-API-Key: your_api_key_here"
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 100,
  "total_extracted": 120,
  "uploaded_to_airtable": 120,
  "companies_created": 45,
  "ratings_created": 118,
  "errors": [],
  "created_at": "2025-10-21T10:30:00",
  "updated_at": "2025-10-21T10:35:00",
  "completed_at": "2025-10-21T10:35:00",
  "start_date": "2025-10-01",
  "end_date": "2025-10-15"
}
```

### GET /health

Health check endpoint (no authentication required).

**Request:**
```bash
curl -X GET "http://localhost:8000/health"
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-21T10:30:00",
  "environment": "production"
}
```

## Architecture

### Components

- **main.py**: FastAPI application with endpoints and background task orchestration
- **models.py**: Pydantic models for request/response validation
- **auth.py**: API key authentication middleware
- **jobs.py**: In-memory job management system
- **airtable_client.py**: Airtable API integration with upsert logic
- **scraper_service.py**: Scraping and extraction service (duplicated from infomerics/)
- **config.py**: Configuration management using environment variables

### Data Flow

1. Client sends POST request to `/infomerics/scrape` with date range
2. API validates request and creates a job with unique UUID
3. Job is queued and job_id is returned immediately
4. Background worker:
   - Scrapes Infomerics website for the date range
   - Extracts company and rating data using BeautifulSoup
   - Uploads to Airtable in batches
   - Updates job progress throughout
5. Client polls `/infomerics/jobs/{job_id}` to check status

### Airtable Schema Mapping

**Companies Table** (`tblMsZnCUfG783lWI`):
- `Company Name` ← company_name (upserted)

**Credit Ratings Table** (`tblRlxbOYMW8Rag7f`):
- `Company` ← Link to Companies record
- `Instrument` ← instrument_category
- `Rating` ← rating
- `Outlook` ← outlook (mapped to predefined choices)
- `Instrument Amount` ← instrument_amount
- `Date` ← date (parsed to YYYY-MM-DD)
- `Source URL` ← url

## Security Features

- **API Key Authentication**: All endpoints (except /health) require X-API-Key header
- **Rate Limiting**: 50 requests per hour per IP address
- **Input Validation**: Pydantic models validate all inputs
- **Date Range Limits**: Maximum 90 days to prevent abuse
- **CORS Configuration**: Configurable allowed origins
- **Non-root Container**: Docker container runs as non-root user

## Error Handling

- Comprehensive try-catch blocks throughout
- Detailed error logging with stack traces
- Job errors are tracked and returned in status responses
- Graceful degradation: batch processing continues even if individual records fail

## Monitoring

- Health check endpoint for load balancer integration
- Detailed logging at INFO level
- Job status tracking with timestamps
- Progress percentage updates

## Production Considerations

1. **Airtable Base ID**: Update `AIRTABLE_BASE_ID` in .env with your actual base ID
2. **API Key Security**: Use strong, randomly generated API keys
3. **Rate Limiting**: Adjust based on your usage patterns
4. **CORS**: Set specific origins instead of "*" in production
5. **Redis**: Consider replacing in-memory job storage with Redis for persistence
6. **Monitoring**: Integrate with monitoring tools (Prometheus, Datadog, etc.)
7. **Scaling**: Deploy multiple instances behind a load balancer

## Troubleshooting

### SSL Certificate Errors

The scraper disables SSL verification for the Infomerics website. This is intentional and matches the original implementation.

### Airtable API Errors

Check that:
- API key is valid and has write permissions
- Base ID is correct
- Table IDs match your Airtable schema

### Job Stuck in "running" State

Jobs are stored in-memory. If the container restarts, job state is lost. Consider implementing Redis for persistence.

## Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest
```

### Code Quality

```bash
# Format code
black api/

# Lint
flake8 api/

# Type checking
mypy api/
```

## License

Internal use only.

