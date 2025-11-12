#!/bin/bash

# Infomerics Docker Compose Startup Script
# This script helps you easily start services with the correct profiles

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() { echo -e "${BLUE}ℹ${NC} $1"; }
print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }

# Function to show usage
show_usage() {
    cat << EOF
${GREEN}Infomerics Docker Compose Startup Script${NC}

Usage: $0 [MODE]

${BLUE}Available Modes:${NC}
  dev               Start core services only (default)
  dev-ui            Start core services + pgAdmin
  prod              Start core services + HTTPS/Nginx
  prod-debug        Start everything (prod + pgAdmin)
  stop              Stop all services
  restart           Restart all services
  logs [SERVICE]    Show logs (optional: specific service)
  status            Show running containers
  clean             Stop and remove all containers and volumes ${YELLOW}(⚠️  DELETES DATA!)${NC}

${BLUE}Examples:${NC}
  $0                    # Start in development mode (default)
  $0 dev-ui             # Start with pgAdmin for database management
  $0 prod               # Start in production mode with HTTPS
  $0 logs api           # Show API logs
  $0 status             # Check which services are running
  $0 stop               # Stop all services

${BLUE}Profile Reference:${NC}
  - Core services always start: API, Celery, PostgreSQL, RabbitMQ, Redis, WhatsApp
  - pgAdmin: Database management UI (http://localhost:5050)
  - Nginx/Certbot: HTTPS reverse proxy (requires domain and SSL setup)

For more details, see: ${GREEN}DEPLOYMENT_MODES.md${NC}
EOF
}

# Function to check if .env exists
check_env() {
    if [ ! -f .env ]; then
        print_error ".env file not found!"
        print_info "Copy env.example to .env and configure it:"
        echo "  cp env.example .env"
        echo "  nano .env  # or your preferred editor"
        exit 1
    fi
}

# Function to start services
start_services() {
    local mode=$1
    local profiles=""
    local description=""

    case $mode in
        dev)
            profiles=""
            description="Development mode (core services only)"
            ;;
        dev-ui)
            profiles="--profile dev"
            description="Development mode with pgAdmin UI"
            ;;
        prod)
            profiles="--profile https"
            description="Production mode with HTTPS"
            # Check for required production settings
            if ! grep -q "^DOMAIN=" .env || ! grep -q "^LETSENCRYPT_EMAIL=" .env; then
                print_warning "Production mode requires DOMAIN and LETSENCRYPT_EMAIL in .env"
                print_info "Make sure you've configured these variables and run init-letsencrypt.sh first"
            fi
            ;;
        prod-debug)
            profiles="--profile https --profile pgadmin"
            description="Production mode with HTTPS + pgAdmin (⚠️  not recommended for security)"
            print_warning "pgAdmin should not be exposed in production!"
            ;;
        *)
            print_error "Unknown mode: $mode"
            show_usage
            exit 1
            ;;
    esac

    print_info "Starting services: $description"
    
    if [ -n "$profiles" ]; then
        docker compose $profiles up -d
    else
        docker compose up -d
    fi
    
    print_success "Services started successfully!"
    print_info "Run '$0 status' to see running containers"
    print_info "Run '$0 logs' to see logs"
}

# Function to stop services
stop_services() {
    print_info "Stopping all services..."
    docker compose down
    print_success "All services stopped"
}

# Function to restart services
restart_services() {
    print_info "Restarting services..."
    docker compose restart
    print_success "Services restarted"
}

# Function to show logs
show_logs() {
    local service=$1
    if [ -n "$service" ]; then
        print_info "Showing logs for: $service"
        docker compose logs -f "$service"
    else
        print_info "Showing logs for all services (press Ctrl+C to exit)"
        docker compose logs -f
    fi
}

# Function to show status
show_status() {
    print_info "Running containers:"
    docker compose ps
    echo ""
    print_info "To see all containers (including stopped profile services):"
    echo "  docker compose ps -a"
}

# Function to clean everything
clean_all() {
    print_warning "This will stop and remove ALL containers and volumes!"
    print_warning "ALL DATA will be deleted (database, RabbitMQ queues, etc.)"
    read -p "Are you sure? (type 'yes' to confirm): " confirm
    
    if [ "$confirm" = "yes" ]; then
        print_info "Stopping and removing all containers and volumes..."
        docker compose down -v
        print_success "All containers and volumes removed"
    else
        print_info "Cancelled"
    fi
}

# Main script logic
main() {
    local mode=${1:-dev}
    
    # Handle help flag
    if [ "$mode" = "-h" ] || [ "$mode" = "--help" ] || [ "$mode" = "help" ]; then
        show_usage
        exit 0
    fi
    
    # Special commands that don't need .env check
    case $mode in
        stop)
            stop_services
            exit 0
            ;;
        status)
            show_status
            exit 0
            ;;
        logs)
            show_logs "$2"
            exit 0
            ;;
        restart)
            restart_services
            exit 0
            ;;
        clean)
            clean_all
            exit 0
            ;;
    esac
    
    # Check for .env file before starting services
    check_env
    
    # Start services with the specified mode
    start_services "$mode"
}

# Run main function with all arguments
main "$@"

