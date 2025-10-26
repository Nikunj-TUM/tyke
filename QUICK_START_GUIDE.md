# Quick Start Guide - Infomerics Scraper API

This guide will help you get the Infomerics Scraper API up and running with PostgreSQL deduplication.

## Prerequisites

- Docker and Docker Compose installed
- Airtable account with API key and base ID
- At least 4GB RAM available for Docker

## 1. Environment Setup

### Clone and Navigate

```bash
cd /path/to/tyke
```

### Configure Environment Variables

Copy the example environment file and edit it:

```bash
cp env.example .env
```

Edit `.env` and set the following **required** variables:

```bash
# Airtable Configuration (REQUIRED)
AIRTABLE_API_KEY=your_actual_airtable_api_key_here
AIRTABLE_BASE_ID=your_actual_base_id_here

# API Configuration (REQUIRED)
API_KEY=your_secure_api_key_here

# PostgreSQL Configuration (Set a secure password)
POSTGRES_PASSWORD=your_secure_postgres_password_here

# Optional: Adjust worker concurrency based on your system
CELERY_SCRAPER_CONCURRENCY=5
CELERY_EXTRACTOR_CONCURRENCY=3
CELERY_UPLOADER_CONCURRENCY=10
```

**Important**: Replace all `your_*_here` placeholders with actual values.

## 2. Start the Services

### First Time Setup

```bash
# Build and start all services
docker-compose up -d

# Wait for services to be healthy (30-60 seconds)
docker-compose ps
```

You should see all services as "healthy" or "running":
- `infomerics-postgres` - PostgreSQL database
- `infomerics-rabbitmq` - Message broker
- `infomerics-redis` - Result backend  
- `infomerics-scraper-api` - FastAPI application
- `infomerics-flower` - Celery monitoring
- `celery-*` workers - Task processors

### Verify Setup

```bash
# Check API health
curl http://localhost:8000/health

# Expected output:
# {"status":"healthy","timestamp":"...","environment":"development"}
```

### Check Logs

```bash
# API logs
docker-compose logs -f api

# All services
docker-compose logs -f

# Specific service
docker-compose logs -f postgres
docker-compose logs -f celery-scraper
```

## 3. Verify Database Initialization

The PostgreSQL database schema is automatically initialized on first startup. Verify it:

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U infomerics_user -d infomerics

# Check tables
\dt

# You should see:
# - companies
# - credit_ratings
# - scrape_jobs

# Exit psql
\q
```

## 4. Run a Test Scrape

### Using curl

```bash
# Scrape data for a date range
curl -X POST "http://localhost:8000/infomerics/scrape" \
  -H "X-API-Key: your_secure_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2025-10-01",
    "end_date": "2025-10-03"
  }'

# Response will include a job_id:
# {"job_id":"abc-123-def","status":"queued","message":"...","created_at":"..."}
```

### Check Job Status

```bash
# Replace JOB_ID with the actual job_id from above
curl "http://localhost:8000/infomerics/jobs/JOB_ID" \
  -H "X-API-Key: your_secure_api_key_here"

# Response shows progress and statistics:
# {
#   "job_id": "...",
#   "status": "running" or "completed",
#   "progress": 75,
#   "total_extracted": 42,
#   "total_scraped": 42,
#   "new_records": 38,
#   "duplicate_records_skipped": 4,
#   "uploaded_to_airtable": 38,
#   "sync_failures": 0,
#   ...
# }
```

### Monitor with Flower

Open Celery Flower dashboard in your browser:

```
http://localhost:5555
```

You can see:
- Active tasks
- Task history
- Worker status
- Task queues

## 5. Test Duplicate Detection

Run the integration test script:

```bash
# Activate virtual environment (if using one)
source venv/bin/activate

# Run tests
python test_postgres_deduplication.py
```

This will:
1. Test database initialization
2. Test single insert with deduplication
3. Test batch insert with duplicates
4. Test Airtable sync
5. Show statistics

## 6. Query PostgreSQL Directly

### Connect to Database

```bash
docker-compose exec postgres psql -U infomerics_user -d infomerics
```

### Useful Queries

```sql
-- View recent jobs
SELECT * FROM recent_jobs_summary LIMIT 10;

-- Check duplicate detection stats
SELECT * FROM duplicate_detection_stats LIMIT 10;

-- View unsynced ratings
SELECT * FROM ratings_pending_sync LIMIT 20;

-- Daily activity
SELECT * FROM daily_scraping_stats LIMIT 30;

-- Company statistics
SELECT 
    company_name,
    COUNT(*) as rating_count
FROM credit_ratings
GROUP BY company_name
ORDER BY rating_count DESC
LIMIT 20;
```

## 7. Common Operations

### Stop Services

```bash
# Stop all services
docker-compose stop

# Stop specific service
docker-compose stop api
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart api
```

### View Resource Usage

```bash
# Container stats
docker stats

# Disk usage
docker-compose ps -a
docker system df
```

### Clean Up

```bash
# Stop and remove containers (keeps volumes/data)
docker-compose down

# Remove everything including data (CAUTION!)
docker-compose down -v
```

## 8. Scaling Workers

You can scale Celery workers based on your workload:

```bash
# Edit .env file
CELERY_SCRAPER_REPLICAS=2
CELERY_UPLOADER_REPLICAS=3

# Restart to apply changes
docker-compose up -d --scale celery-scraper=2 --scale celery-uploader=3
```

## 9. Backup and Restore

### Backup PostgreSQL

```bash
# Create backup
docker-compose exec postgres pg_dump -U infomerics_user infomerics > backup_$(date +%Y%m%d_%H%M%S).sql

# Or with compression
docker-compose exec postgres pg_dump -U infomerics_user infomerics | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Restore PostgreSQL

```bash
# From uncompressed backup
docker-compose exec -T postgres psql -U infomerics_user -d infomerics < backup.sql

# From compressed backup
gunzip -c backup.sql.gz | docker-compose exec -T postgres psql -U infomerics_user -d infomerics
```

## 10. Troubleshooting

### Service Won't Start

```bash
# Check logs for specific service
docker-compose logs postgres
docker-compose logs api

# Check if ports are already in use
lsof -i :5432  # PostgreSQL
lsof -i :8000  # API
lsof -i :5672  # RabbitMQ
lsof -i :6379  # Redis
```

### PostgreSQL Connection Issues

```bash
# Verify PostgreSQL is running
docker-compose ps postgres

# Check PostgreSQL logs
docker-compose logs postgres

# Test connection
docker-compose exec postgres psql -U infomerics_user -d infomerics -c "SELECT version();"
```

### Airtable Sync Failures

```sql
-- Check failed syncs
SELECT * FROM credit_ratings WHERE sync_failed = TRUE ORDER BY scraped_at DESC LIMIT 10;

-- Reset failed status to retry
UPDATE credit_ratings SET sync_failed = FALSE, sync_error = NULL WHERE sync_failed = TRUE;
```

### Clear Redis Cache

```bash
docker-compose exec redis redis-cli FLUSHALL
```

### Reset RabbitMQ Queues

```bash
# Via management UI (browser)
http://localhost:15672
# Login: guest/guest

# Or command line
docker-compose exec rabbitmq rabbitmqctl purge_queue celery
docker-compose exec rabbitmq rabbitmqctl purge_queue scraping
docker-compose exec rabbitmq rabbitmqctl purge_queue extraction
docker-compose exec rabbitmq rabbitmqctl purge_queue uploading
```

## 11. Development Mode

For development with live code reloading:

```bash
# API already mounts code as volume in docker-compose.yml
# Edit code and API will auto-reload

# Restart Celery workers to pick up code changes
docker-compose restart celery-scraper celery-extractor celery-uploader celery-general
```

## 12. Production Considerations

Before deploying to production:

1. **Security**:
   - Change all default passwords
   - Use strong API keys
   - Enable HTTPS/TLS
   - Restrict CORS origins

2. **Performance**:
   - Adjust worker concurrency based on server resources
   - Monitor with Flower and application logs
   - Set up log aggregation (e.g., ELK stack)

3. **Reliability**:
   - Set up automated backups for PostgreSQL
   - Monitor disk space
   - Configure log rotation
   - Set up health check monitoring

4. **Scalability**:
   - Use external PostgreSQL (e.g., AWS RDS)
   - Use managed Redis and RabbitMQ
   - Scale workers horizontally

## 13. API Endpoints

### Health Check
```bash
GET /health
# No authentication required
```

### Start Scraping Job
```bash
POST /infomerics/scrape
Headers: X-API-Key: your_api_key
Body: {
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD"
}
```

### Get Job Status
```bash
GET /infomerics/jobs/{job_id}
Headers: X-API-Key: your_api_key
```

### List All Jobs
```bash
GET /infomerics/jobs?limit=100
Headers: X-API-Key: your_api_key
```

## 14. Monitoring Dashboard URLs

- **API Health**: http://localhost:8000/health
- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **Celery Flower**: http://localhost:5555
- **RabbitMQ Management**: http://localhost:15672 (guest/guest)

## 15. Getting Help

1. **Documentation**:
   - This guide
   - `POSTGRES_MIGRATION.md` - PostgreSQL architecture details
   - `README.md` - Project overview

2. **Logs**:
   ```bash
   docker-compose logs api
   docker-compose logs celery-scraper
   ```

3. **Database Queries**:
   ```sql
   -- Check system status
   SELECT * FROM recent_jobs_summary LIMIT 5;
   SELECT * FROM duplicate_detection_stats LIMIT 5;
   ```

## Next Steps

- Review `POSTGRES_MIGRATION.md` for detailed PostgreSQL architecture
- Set up monitoring and alerting
- Configure automated backups
- Customize worker concurrency for your workload
- Explore the API documentation at http://localhost:8000/docs

---

**Need help?** Check the logs first, then review the troubleshooting section above.

