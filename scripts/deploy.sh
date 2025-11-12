#!/bin/bash

# Production Deployment Script
# This script helps deploy or update the application in production

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

COMPOSE_FILE="docker-compose.yml"
COMPOSE_PROFILES="--profile https"

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if .env exists
if [ ! -f .env ]; then
    print_error ".env file not found!"
    print_info "Please create .env file with production values"
    exit 1
fi

# Parse command
COMMAND=${1:-help}

case $COMMAND in
    "build")
        print_header "Building Docker Images"
        docker compose -f $COMPOSE_FILE $COMPOSE_PROFILES build
        print_info "✅ Build complete!"
        ;;
        
    "start")
        print_header "Starting Services"
        docker compose -f $COMPOSE_FILE $COMPOSE_PROFILES up -d
        sleep 5
        docker compose -f $COMPOSE_FILE $COMPOSE_PROFILES ps
        print_info "✅ Services started!"
        ;;
        
    "stop")
        print_header "Stopping Services"
        docker compose -f $COMPOSE_FILE $COMPOSE_PROFILES down
        print_info "✅ Services stopped!"
        ;;
        
    "restart")
        print_header "Restarting Services"
        docker compose -f $COMPOSE_FILE $COMPOSE_PROFILES restart
        print_info "✅ Services restarted!"
        ;;
        
    "update")
        print_header "Updating Application"
        
        print_info "Pulling latest code..."
        git pull
        
        print_info "Building new images..."
        docker compose -f $COMPOSE_FILE $COMPOSE_PROFILES build
        
        print_info "Restarting services..."
        docker compose -f $COMPOSE_FILE $COMPOSE_PROFILES up -d
        
        print_info "Waiting for services to be ready..."
        sleep 10
        
        print_info "Checking service status..."
        docker compose -f $COMPOSE_FILE $COMPOSE_PROFILES ps
        
        print_info "✅ Update complete!"
        ;;
        
    "logs")
        SERVICE=${2:-}
        if [ -z "$SERVICE" ]; then
            print_info "Showing all logs (Ctrl+C to exit)..."
            docker compose -f $COMPOSE_FILE $COMPOSE_PROFILES logs -f
        else
            print_info "Showing logs for $SERVICE (Ctrl+C to exit)..."
            docker compose -f $COMPOSE_FILE $COMPOSE_PROFILES logs -f $SERVICE
        fi
        ;;
        
    "status")
        print_header "Service Status"
        docker compose -f $COMPOSE_FILE $COMPOSE_PROFILES ps
        echo ""
        print_info "To view logs: ./scripts/deploy.sh logs [service]"
        ;;
        
    "ssl")
        print_header "Setting Up SSL Certificate"
        if [ ! -f ./init-letsencrypt.sh ]; then
            print_error "init-letsencrypt.sh not found!"
            exit 1
        fi
        chmod +x ./init-letsencrypt.sh
        ./init-letsencrypt.sh
        ;;
        
    "backup")
        print_header "Creating Backup"
        
        if [ ! -f ./backup.sh ]; then
            print_warning "backup.sh not found. Creating it..."
            cat > ./backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups/infomerics"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

cd /opt/infomerics
source .env

# Backup PostgreSQL
docker exec infomerics-postgres pg_dump -U $POSTGRES_USER $POSTGRES_DB | gzip > $BACKUP_DIR/postgres_$DATE.sql.gz

# Keep only last 7 days
find $BACKUP_DIR -type f -mtime +7 -delete

echo "Backup completed: $DATE"
EOF
            chmod +x ./backup.sh
        fi
        
        ./backup.sh
        print_info "✅ Backup complete!"
        ;;
        
    "health")
        print_header "Health Check"
        
        # Check if containers are running
        print_info "Container status:"
        docker compose -f $COMPOSE_FILE $COMPOSE_PROFILES ps
        echo ""
        
        # Check API health
        print_info "Testing API endpoint..."
        if curl -f http://localhost:8000/health > /dev/null 2>&1; then
            print_info "✅ API is healthy (HTTP)"
        else
            print_warning "❌ API health check failed (HTTP)"
        fi
        
        # Check HTTPS if domain is configured
        source .env
        if [ ! -z "$DOMAIN" ]; then
            print_info "Testing HTTPS endpoint..."
            if curl -f https://$DOMAIN/health > /dev/null 2>&1; then
                print_info "✅ HTTPS is working"
            else
                print_warning "❌ HTTPS check failed"
            fi
        fi
        ;;
        
    "clean")
        print_header "Cleaning Up"
        print_warning "This will remove stopped containers and unused images"
        read -p "Continue? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker compose -f $COMPOSE_FILE $COMPOSE_PROFILES down
            docker system prune -f
            print_info "✅ Cleanup complete!"
        else
            print_info "Cancelled"
        fi
        ;;
        
    "help"|*)
        print_header "Production Deployment Helper"
        echo ""
        echo "Usage: ./scripts/deploy.sh [command]"
        echo ""
        echo "Commands:"
        echo "  build       Build Docker images"
        echo "  start       Start all services"
        echo "  stop        Stop all services"
        echo "  restart     Restart all services"
        echo "  update      Pull latest code and rebuild"
        echo "  logs        View logs (optionally specify service)"
        echo "  status      Show service status"
        echo "  ssl         Setup SSL certificate"
        echo "  backup      Create database backup"
        echo "  health      Run health checks"
        echo "  clean       Remove stopped containers and unused images"
        echo "  help        Show this help message"
        echo ""
        echo "Examples:"
        echo "  ./scripts/deploy.sh build"
        echo "  ./scripts/deploy.sh logs api"
        echo "  ./scripts/deploy.sh update"
        ;;
esac

