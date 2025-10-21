# Infomerics Credit Rating Data Platform

A comprehensive platform for scraping Infomerics press releases and managing credit rating data in Airtable.

## 🚀 New: Production API

**A secure, production-grade FastAPI application** for automated scraping and Airtable integration is now available!

### Quick Start

```bash
# 1. Configure environment
cp env.example .env
# Edit .env with your Airtable credentials

# 2. Run with Docker
docker-compose up --build -d

# 3. Test the API
./test_api.sh
```

### API Endpoints

- **POST /infomerics/scrape** - Start scraping job (async, returns job_id)
- **GET /infomerics/jobs/{job_id}** - Check job status and results
- **GET /health** - Health check

### Features

- ✅ **Asynchronous Processing** - Submit jobs and track progress
- ✅ **Secure** - API key authentication and rate limiting (50 req/hour)
- ✅ **Airtable Integration** - Automatic upsert to Companies and Credit Ratings tables
- ✅ **Production-Ready** - Docker, comprehensive error handling, logging
- ✅ **Robust** - Batch processing, duplicate detection, progress tracking

See [SETUP.md](SETUP.md) for detailed setup instructions and [api/README.md](api/README.md) for full API documentation.

---

## 📦 Original Test Scripts

The repository also includes standalone Python scripts for testing and development.

### What it extracts:

- **Company Names**: Names of companies being rated
- **Instrument Categories**: Types of financial instruments (e.g., "Long Term Bank Facilities", "Short Term Bank Facilities")
- **Ratings**: Credit ratings assigned by Infomerics (e.g., "IVR BBB-", "IVR A-")
- **Outlook**: Rating outlook (Positive, Negative, Stable, Nil)
- **Instrument Amount**: Financial amounts associated with each instrument
- **Date**: "As on" dates mentioned in the ratings
- **URL**: Links to detailed instrument reports

### Standalone Usage:

```bash
# Install dependencies
pip install -r infomerics/requirements.txt

# Scrape a date range
cd infomerics
python scrape_press_release_page.py 2025-10-09 2025-10-12

# Or use the batch scraper
python example_usage.py 2025-09-01 2025-10-31
```

### Output Files:

1. **infomerics_YYYY-MM-DD_YYYY-MM-DD.json** - Raw scraped data
2. **infomerics_YYYY-MM-DD_YYYY-MM-DD.csv** - Extracted data in CSV
3. **infomerics_YYYY-MM-DD_YYYY-MM-DD.xlsx** - Excel with analysis sheets

### Optional Dependencies:

For Excel export with additional analysis sheets:
```bash
pip install pandas openpyxl
```

### Example Output:

```
=== EXTRACTION SUMMARY ===
Total instruments extracted: 169
Unique companies: 143

Sample data:
1. Company: Chandanpani Limited
   Category: Long Term Bank Facilities
   Rating: IVR BBB- (Reaffirmed)
   Date: Oct 10, 2025
   URL: https://www.infomerics.com/admin/uploads/PR-ChandanpaniLtd10Oct25.pdf
```

---

## 📊 Airtable Schema

The platform integrates with two Airtable tables:

### Companies Table
- Company Name (primary)
- Credit Ratings (linked records)
- Latest Credit Rating (rollup)
- Most Recent Rating (rollup)

### Credit Ratings Table
- Rating (primary)
- Instrument
- Company (link to Companies)
- Outlook (single select)
- Instrument Amount
- Date
- Source URL

Schema defined in [airtable_base_schema.json](airtable_base_schema.json)

---

## 🛠️ Project Structure

```
tyke/
├── api/                          # Production API
│   ├── main.py                  # FastAPI application
│   ├── models.py                # Pydantic models
│   ├── auth.py                  # API key authentication
│   ├── jobs.py                  # Job management
│   ├── airtable_client.py       # Airtable integration
│   ├── scraper_service.py       # Scraping service
│   ├── config.py                # Configuration
│   └── requirements.txt         # API dependencies
│
├── infomerics/                   # Test scripts
│   ├── scrape_press_release_page.py
│   ├── extract_data_press_release_page.py
│   ├── example_usage.py
│   └── requirements.txt
│
├── Dockerfile                    # Docker image
├── docker-compose.yml           # Docker compose config
├── env.example                  # Environment template
├── test_api.sh                  # API test script
├── SETUP.md                     # Setup guide
└── airtable_base_schema.json   # Airtable schema
```

---

## 📝 License

Internal use only.
