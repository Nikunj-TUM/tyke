#!/bin/bash
# Test script for Infomerics Scraper API

set -e

# Configuration
API_URL="${API_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-your_secure_api_key_here}"

echo "Testing Infomerics Scraper API"
echo "API URL: $API_URL"
echo "================================"

# Test 1: Health Check
echo ""
echo "Test 1: Health Check (no auth required)"
echo "----------------------------------------"
HEALTH_RESPONSE=$(curl -s "$API_URL/health")
echo "$HEALTH_RESPONSE" | python -m json.tool
echo "✓ Health check passed"

# Test 2: Start Scraping Job
echo ""
echo "Test 2: Start Scraping Job"
echo "----------------------------------------"
SCRAPE_RESPONSE=$(curl -s -X POST "$API_URL/infomerics/scrape" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2025-10-09",
    "end_date": "2025-10-12"
  }')

echo "$SCRAPE_RESPONSE" | python -m json.tool

# Extract job_id
JOB_ID=$(echo "$SCRAPE_RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin)['job_id'])")
echo "✓ Job created with ID: $JOB_ID"

# Test 3: Check Job Status
echo ""
echo "Test 3: Check Job Status (waiting 5 seconds...)"
echo "----------------------------------------"
sleep 5

JOB_STATUS=$(curl -s -X GET "$API_URL/infomerics/jobs/$JOB_ID" \
  -H "X-API-Key: $API_KEY")

echo "$JOB_STATUS" | python -m json.tool

STATUS=$(echo "$JOB_STATUS" | python -c "import sys, json; print(json.load(sys.stdin)['status'])")
PROGRESS=$(echo "$JOB_STATUS" | python -c "import sys, json; print(json.load(sys.stdin)['progress'])")

echo "✓ Job status: $STATUS"
echo "✓ Progress: $PROGRESS%"

# Test 4: Poll until completion
echo ""
echo "Test 4: Polling job until completion..."
echo "----------------------------------------"

MAX_POLLS=60
POLL_COUNT=0

while [ "$STATUS" != "completed" ] && [ "$STATUS" != "failed" ] && [ $POLL_COUNT -lt $MAX_POLLS ]; do
  sleep 3
  POLL_COUNT=$((POLL_COUNT + 1))
  
  JOB_STATUS=$(curl -s -X GET "$API_URL/infomerics/jobs/$JOB_ID" \
    -H "X-API-Key: $API_KEY")
  
  STATUS=$(echo "$JOB_STATUS" | python -c "import sys, json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "unknown")
  PROGRESS=$(echo "$JOB_STATUS" | python -c "import sys, json; print(json.load(sys.stdin)['progress'])" 2>/dev/null || echo "0")
  
  echo "Poll $POLL_COUNT: Status=$STATUS, Progress=$PROGRESS%"
done

# Final result
echo ""
echo "Final Job Result:"
echo "----------------------------------------"
echo "$JOB_STATUS" | python -m json.tool

if [ "$STATUS" = "completed" ]; then
  TOTAL_EXTRACTED=$(echo "$JOB_STATUS" | python -c "import sys, json; print(json.load(sys.stdin)['total_extracted'])")
  COMPANIES_CREATED=$(echo "$JOB_STATUS" | python -c "import sys, json; print(json.load(sys.stdin)['companies_created'])")
  RATINGS_CREATED=$(echo "$JOB_STATUS" | python -c "import sys, json; print(json.load(sys.stdin)['ratings_created'])")
  
  echo ""
  echo "================================"
  echo "✓ All tests passed!"
  echo "================================"
  echo "Total extracted: $TOTAL_EXTRACTED"
  echo "Companies created: $COMPANIES_CREATED"
  echo "Ratings created: $RATINGS_CREATED"
elif [ "$STATUS" = "failed" ]; then
  echo ""
  echo "================================"
  echo "✗ Job failed!"
  echo "================================"
  exit 1
else
  echo ""
  echo "================================"
  echo "⚠ Job did not complete in time"
  echo "================================"
  echo "Check status manually: curl -H \"X-API-Key: $API_KEY\" $API_URL/infomerics/jobs/$JOB_ID"
fi

