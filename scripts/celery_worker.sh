#!/bin/bash
# Celery Worker Startup Script
# This script provides convenient commands to start different worker pools

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
WORKER_TYPE="${1:-all}"
LOG_LEVEL="${2:-info}"

echo -e "${GREEN}Starting Celery Workers for Infomerics Scraper${NC}"
echo "========================================"

case "$WORKER_TYPE" in
  scraper)
    echo -e "${YELLOW}Starting Scraper Worker (Queue: scraping, Concurrency: 5)${NC}"
    celery -A api.celery_app worker \
      -Q scraping \
      --loglevel=$LOG_LEVEL \
      --concurrency=5 \
      -n scraper@%h \
      --max-tasks-per-child=1000
    ;;
  
  extractor)
    echo -e "${YELLOW}Starting Extractor Worker (Queue: extraction, Concurrency: 3)${NC}"
    celery -A api.celery_app worker \
      -Q extraction \
      --loglevel=$LOG_LEVEL \
      --concurrency=3 \
      -n extractor@%h \
      --max-tasks-per-child=500
    ;;
  
  uploader)
    echo -e "${YELLOW}Starting Uploader Worker (Queue: uploading, Concurrency: 10)${NC}"
    celery -A api.celery_app worker \
      -Q uploading \
      --loglevel=$LOG_LEVEL \
      --concurrency=10 \
      -n uploader@%h \
      --max-tasks-per-child=2000
    ;;
  
  general)
    echo -e "${YELLOW}Starting General Worker (Queue: celery, Concurrency: 4)${NC}"
    celery -A api.celery_app worker \
      -Q celery \
      --loglevel=$LOG_LEVEL \
      --concurrency=4 \
      -n general@%h \
      --max-tasks-per-child=1000
    ;;
  
  all)
    echo -e "${YELLOW}Starting All-in-One Worker (All queues)${NC}"
    celery -A api.celery_app worker \
      -Q celery,scraping,extraction,uploading \
      --loglevel=$LOG_LEVEL \
      --concurrency=8 \
      -n all@%h \
      --max-tasks-per-child=1000
    ;;
  
  flower)
    echo -e "${YELLOW}Starting Flower Monitoring Dashboard (Port: 5555)${NC}"
    celery -A api.celery_app flower --port=5555
    ;;
  
  *)
    echo -e "${RED}Error: Unknown worker type '$WORKER_TYPE'${NC}"
    echo ""
    echo "Usage: $0 [worker_type] [log_level]"
    echo ""
    echo "Worker Types:"
    echo "  scraper   - Scraping queue worker (5 concurrent)"
    echo "  extractor - Extraction queue worker (3 concurrent)"
    echo "  uploader  - Upload queue worker (10 concurrent)"
    echo "  general   - General/orchestrator queue worker (4 concurrent)"
    echo "  all       - All queues in one worker (8 concurrent)"
    echo "  flower    - Monitoring dashboard"
    echo ""
    echo "Log Levels: debug, info, warning, error, critical"
    echo ""
    echo "Examples:"
    echo "  $0 scraper info"
    echo "  $0 uploader debug"
    echo "  $0 all"
    echo "  $0 flower"
    exit 1
    ;;
esac

