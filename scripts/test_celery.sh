#!/bin/bash
# Celery System Test Script
# Tests all components of the Celery infrastructure

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Celery System Test Suite                        ║${NC}"
echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo ""

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo -n "Testing: $test_name... "
    
    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

# Function to run a test with output
run_test_with_output() {
    local test_name="$1"
    local test_command="$2"
    
    echo -e "${YELLOW}Testing: $test_name${NC}"
    
    if output=$(eval "$test_command" 2>&1); then
        echo -e "${GREEN}✓ PASS${NC}"
        echo "$output"
        ((TESTS_PASSED++))
        echo ""
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        echo "$output"
        ((TESTS_FAILED++))
        echo ""
        return 1
    fi
}

echo -e "${BLUE}1. Docker Container Tests${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

run_test "API container running" "docker ps | grep -q infomerics-scraper-api"
run_test "RabbitMQ container running" "docker ps | grep -q infomerics-rabbitmq"
run_test "Redis container running" "docker ps | grep -q infomerics-redis"
run_test "Celery scraper worker running" "docker ps | grep -q infomerics-celery-scraper"
run_test "Celery uploader worker running" "docker ps | grep -q infomerics-celery-uploader"
run_test "Celery general worker running" "docker ps | grep -q infomerics-celery-general"
run_test "Flower monitoring running" "docker ps | grep -q infomerics-flower"

echo ""
echo -e "${BLUE}2. Service Health Tests${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

run_test "API health check" "curl -s http://localhost:8000/health | grep -q healthy"
run_test "RabbitMQ reachable" "nc -z localhost 5672"
run_test "RabbitMQ Management UI" "curl -s http://localhost:15672 | grep -q RabbitMQ"
run_test "Redis reachable" "nc -z localhost 6379"
run_test "Flower dashboard" "curl -s http://localhost:5555 | grep -q Flower"

echo ""
echo -e "${BLUE}3. Celery Worker Tests${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

run_test_with_output "Active workers" "docker compose exec -T celery-general celery -A api.celery_app inspect active_queues"

echo ""
echo -e "${BLUE}4. Queue Tests${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if queues exist
run_test "Scraping queue exists" "curl -s -u guest:guest http://localhost:15672/api/queues/%2F/scraping | grep -q scraping"
run_test "Extraction queue exists" "curl -s -u guest:guest http://localhost:15672/api/queues/%2F/extraction | grep -q extraction"
run_test "Uploading queue exists" "curl -s -u guest:guest http://localhost:15672/api/queues/%2F/uploading | grep -q uploading"
run_test "Celery queue exists" "curl -s -u guest:guest http://localhost:15672/api/queues/%2F/celery | grep -q celery"

echo ""
echo -e "${BLUE}5. Redis Connection Test${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

run_test "Redis PING" "docker exec infomerics-redis redis-cli ping | grep -q PONG"

echo ""
echo -e "${BLUE}6. Configuration Tests${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

run_test "USE_CELERY enabled" "docker compose exec -T api python -c 'from api.config import settings; assert settings.USE_CELERY == True'"
run_test "RabbitMQ host configured" "docker compose exec -T api python -c 'from api.config import settings; assert settings.RABBITMQ_HOST == \"rabbitmq\"'"
run_test "Redis host configured" "docker compose exec -T api python -c 'from api.config import settings; assert settings.REDIS_HOST == \"redis\"'"

echo ""
echo -e "${BLUE}7. Task Registration Tests${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

run_test_with_output "Registered tasks" "docker compose exec -T celery-general celery -A api.celery_app inspect registered"

echo ""
echo -e "${BLUE}8. Integration Test${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Get API key from .env
if [ -f .env ]; then
    API_KEY=$(grep "^API_KEY=" .env | cut -d '=' -f2)
else
    echo -e "${YELLOW}Warning: .env file not found, using default API key${NC}"
    API_KEY="your-api-key-here"
fi

echo "Submitting test job..."
RESPONSE=$(curl -s -X POST "http://localhost:8000/infomerics/scrape" \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"start_date": "2025-10-01", "end_date": "2025-10-01"}')

if echo "$RESPONSE" | grep -q "job_id"; then
    JOB_ID=$(echo "$RESPONSE" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
    echo -e "${GREEN}✓ Job submitted successfully${NC}"
    echo "Job ID: $JOB_ID"
    ((TESTS_PASSED++))
    
    # Wait a moment
    echo "Waiting 5 seconds for job to start processing..."
    sleep 5
    
    # Check job status
    echo "Checking job status..."
    STATUS_RESPONSE=$(curl -s "http://localhost:8000/infomerics/jobs/$JOB_ID" \
        -H "X-API-Key: $API_KEY")
    
    if echo "$STATUS_RESPONSE" | grep -q "job_id"; then
        echo -e "${GREEN}✓ Job status retrieved successfully${NC}"
        echo "$STATUS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$STATUS_RESPONSE"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ Failed to retrieve job status${NC}"
        ((TESTS_FAILED++))
    fi
else
    echo -e "${RED}✗ Failed to submit job${NC}"
    echo "Response: $RESPONSE"
    ((TESTS_FAILED++))
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}                    Test Summary                           ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
echo -e "Total Tests: $TOTAL_TESTS"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✓ All tests passed! Celery system is working correctly ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Next steps:"
    echo "  • View Flower dashboard: http://localhost:5555"
    echo "  • View RabbitMQ management: http://localhost:15672"
    echo "  • Submit real jobs via the API"
    exit 0
else
    echo ""
    echo -e "${RED}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ✗ Some tests failed. Please check the output above.    ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  • Check logs: docker compose logs"
    echo "  • Check service status: docker compose ps"
    echo "  • Restart services: docker compose restart"
    echo "  • View CELERY.md for detailed troubleshooting"
    exit 1
fi

