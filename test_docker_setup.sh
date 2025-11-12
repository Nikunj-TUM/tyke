#!/bin/bash

# Docker Setup Test Script
# This script validates your Docker configuration is correct

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "Docker Setup Validation Test"
echo "========================================="
echo ""

# Test 1: Check if .env exists
echo -n "Checking .env file... "
if [ -f .env ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo "Error: .env file not found. Run: cp env.example .env"
    exit 1
fi

# Test 2: Validate docker-compose.yml
echo -n "Validating docker-compose.yml... "
if docker compose config --quiet; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo "Error: docker-compose.yml has syntax errors"
    exit 1
fi

# Test 3: Check required environment variables
echo -n "Checking required environment variables... "
source .env
REQUIRED_VARS=("POSTGRES_PASSWORD" "POSTGRES_USER" "POSTGRES_DB")
MISSING_VARS=()

for VAR in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!VAR}" ]; then
        MISSING_VARS+=($VAR)
    fi
done

if [ ${#MISSING_VARS[@]} -eq 0 ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo "Error: Missing required variables: ${MISSING_VARS[*]}"
    exit 1
fi

# Test 4: Check if Docker is running
echo -n "Checking Docker daemon... "
if docker info > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo "Error: Docker daemon is not running"
    exit 1
fi

# Test 5: Check profile configuration
echo -n "Checking profile configuration... "
PROFILES=$(docker compose config --profiles)
if echo "$PROFILES" | grep -q "https" && echo "$PROFILES" | grep -q "pgadmin"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠${NC} Warning: Profiles may not be configured correctly"
fi

# Test 6: Check service definitions
echo -n "Checking service definitions... "
SERVICES=$(docker compose config --services | sort)
EXPECTED_SERVICES="api
celery-extractor
celery-general
celery-scraper
celery-uploader
certbot
flower
nginx
pgadmin
postgres
rabbitmq
redis
whatsapp-service"

if [ "$SERVICES" = "$EXPECTED_SERVICES" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠${NC} Warning: Service list may have changed"
fi

# Summary
echo ""
echo "========================================="
echo -e "${GREEN}All validation tests passed!${NC}"
echo "========================================="
echo ""
echo "You can now start your services:"
echo ""
echo "  Local development:"
echo "    docker compose up -d"
echo ""
echo "  With pgAdmin:"
echo "    docker compose --profile pgadmin up -d"
echo ""
echo "  Production (HTTPS):"
echo "    docker compose --profile https up -d"
echo ""
echo "Check status after starting:"
echo "  docker compose ps"
echo ""

