#!/bin/bash

# Migration Helper Script
# Helps transition from old Docker setup to new unified configuration

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Docker Setup Migration Helper${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Step 1: Check if old containers are running
echo -e "${YELLOW}[1/5]${NC} Checking for running containers..."
RUNNING=$(docker ps --filter "name=infomerics" --format "{{.Names}}" | wc -l)
if [ $RUNNING -gt 0 ]; then
    echo "Found $RUNNING running container(s)"
    echo "Container names:"
    docker ps --filter "name=infomerics" --format "  - {{.Names}}"
    echo ""
    read -p "Stop these containers? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping containers..."
        docker compose down 2>/dev/null || true
        docker ps --filter "name=infomerics" --format "{{.Names}}" | xargs -r docker stop
        echo -e "${GREEN}✓${NC} Containers stopped"
    else
        echo -e "${YELLOW}⚠${NC} Skipped. You may want to stop them manually later."
    fi
else
    echo -e "${GREEN}✓${NC} No running containers found"
fi
echo ""

# Step 2: Check .env file
echo -e "${YELLOW}[2/5]${NC} Checking .env configuration..."
if [ ! -f .env ]; then
    echo -e "${RED}✗${NC} .env file not found"
    read -p "Create from env.example? (Y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        cp env.example .env
        echo -e "${GREEN}✓${NC} Created .env from template"
        echo ""
        echo -e "${YELLOW}IMPORTANT:${NC} Edit .env file with your configuration:"
        echo "  nano .env"
        echo ""
        read -p "Press Enter to continue after editing .env..."
    else
        echo -e "${RED}Error:${NC} .env file is required. Please create it."
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} .env file exists"
    
    # Check for new required variables
    source .env
    NEEDS_UPDATE=false
    
    if [ -z "$ENVIRONMENT" ]; then
        echo -e "${YELLOW}⚠${NC} Missing ENVIRONMENT variable"
        NEEDS_UPDATE=true
    fi
    
    if [ "$NEEDS_UPDATE" = true ]; then
        echo ""
        echo -e "${YELLOW}Your .env file may need updates.${NC}"
        echo "Compare with env.example:"
        echo "  diff .env env.example"
        echo ""
        read -p "Press Enter to continue..."
    fi
fi
echo ""

# Step 3: Validate docker-compose.yml
echo -e "${YELLOW}[3/5]${NC} Validating docker-compose.yml..."
if docker compose config --quiet 2>/dev/null; then
    echo -e "${GREEN}✓${NC} docker-compose.yml is valid"
else
    echo -e "${RED}✗${NC} docker-compose.yml has errors"
    echo "Run: docker compose config"
    exit 1
fi
echo ""

# Step 4: Choose deployment mode
echo -e "${YELLOW}[4/5]${NC} Choose deployment mode:"
echo ""
echo "1) Local development (no SSL, no pgAdmin)"
echo "2) Local development with pgAdmin (database UI)"
echo "3) Production with HTTPS (requires domain and SSL setup)"
echo ""
read -p "Select option (1-3): " -n 1 -r DEPLOY_OPTION
echo ""
echo ""

case $DEPLOY_OPTION in
    1)
        COMPOSE_CMD="docker compose up -d"
        echo "Selected: Local development"
        ;;
    2)
        COMPOSE_CMD="docker compose --profile pgadmin up -d"
        echo "Selected: Local development with pgAdmin"
        ;;
    3)
        COMPOSE_CMD="docker compose --profile https up -d"
        echo "Selected: Production with HTTPS"
        
        # Check SSL requirements
        source .env
        if [ -z "$DOMAIN" ] || [ -z "$LETSENCRYPT_EMAIL" ]; then
            echo -e "${RED}Error:${NC} DOMAIN and LETSENCRYPT_EMAIL required for HTTPS"
            echo "Update .env file and run SSL setup:"
            echo "  ./init-letsencrypt.sh"
            exit 1
        fi
        
        # Check if SSL certificates exist
        if [ ! -d "./certbot/conf/live/$DOMAIN" ]; then
            echo ""
            echo -e "${YELLOW}⚠${NC} SSL certificates not found"
            echo "You need to run SSL setup first:"
            echo "  ./init-letsencrypt.sh"
            echo ""
            read -p "Run SSL setup now? (y/N) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                chmod +x init-letsencrypt.sh
                ./init-letsencrypt.sh
            else
                echo "Skipping SSL setup. Run it manually later."
            fi
        fi
        ;;
    *)
        echo -e "${RED}Invalid option${NC}"
        exit 1
        ;;
esac
echo ""

# Step 5: Start services
echo -e "${YELLOW}[5/5]${NC} Starting services..."
echo "Command: $COMPOSE_CMD"
echo ""
read -p "Start services now? (Y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    echo ""
    echo "Starting services..."
    eval $COMPOSE_CMD
    
    echo ""
    echo "Waiting for services to initialize (30 seconds)..."
    sleep 10
    echo "20 seconds remaining..."
    sleep 10
    echo "10 seconds remaining..."
    sleep 10
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Migration Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    
    # Show status
    echo "Service Status:"
    docker compose ps
    
    echo ""
    echo -e "${BLUE}Next Steps:${NC}"
    echo ""
    echo "1. Check all services are healthy:"
    echo "   docker compose ps"
    echo ""
    echo "2. View logs:"
    echo "   docker compose logs -f"
    echo ""
    echo "3. Test API:"
    if [ "$DEPLOY_OPTION" = "3" ]; then
        echo "   curl https://$DOMAIN/health"
    else
        echo "   curl http://localhost:8000/health"
    fi
    echo ""
    echo "4. Access services:"
    if [ "$DEPLOY_OPTION" = "3" ]; then
        echo "   API: https://$DOMAIN"
        echo "   Docs: https://$DOMAIN/docs"
        echo "   Flower: https://$DOMAIN/flower/"
    else
        echo "   API: http://localhost:8000"
        echo "   Docs: http://localhost:8000/docs"
        echo "   Flower: http://localhost:5555"
        [ "$DEPLOY_OPTION" = "2" ] && echo "   pgAdmin: http://localhost:5050"
    fi
    echo ""
    echo -e "${GREEN}For more help, see:${NC}"
    echo "  - START_HERE.md"
    echo "  - QUICKSTART_NEW.md"
    echo "  - DOCKER_USAGE.md"
    echo ""
else
    echo ""
    echo "Skipped starting services."
    echo ""
    echo "To start manually, run:"
    echo "  $COMPOSE_CMD"
    echo ""
fi

