#!/bin/bash

# SSL Certificate Initialization Script for Let's Encrypt
# This script sets up SSL certificates for your domain using Certbot

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.prod.yml"
NGINX_CONF_DIR="./nginx/conf.d"
CERTBOT_DIR="./certbot"

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Load environment variables
if [ ! -f .env ]; then
    print_error ".env file not found!"
    print_info "Please create .env file with DOMAIN variable"
    exit 1
fi

source .env

# Check if DOMAIN is set
if [ -z "$DOMAIN" ]; then
    print_error "DOMAIN variable not set in .env file!"
    print_info "Add: DOMAIN=api.yourdomain.com"
    exit 1
fi

# Check if email is set (for Let's Encrypt notifications)
if [ -z "$LETSENCRYPT_EMAIL" ]; then
    print_error "LETSENCRYPT_EMAIL variable not set in .env file!"
    print_info "Add: LETSENCRYPT_EMAIL=your-email@example.com"
    exit 1
fi

# Ask for confirmation
print_info "This script will:"
print_info "  1. Set up SSL certificates for: $DOMAIN"
print_info "  2. Use email: $LETSENCRYPT_EMAIL"
print_info "  3. Create necessary directories"
print_info "  4. Request certificates from Let's Encrypt"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Aborted by user"
    exit 0
fi

# Create necessary directories
print_info "Creating directories..."
mkdir -p "$CERTBOT_DIR/conf"
mkdir -p "$CERTBOT_DIR/www"
mkdir -p "$NGINX_CONF_DIR"

# Download recommended TLS parameters
if [ ! -e "$CERTBOT_DIR/conf/options-ssl-nginx.conf" ] || [ ! -e "$CERTBOT_DIR/conf/ssl-dhparams.pem" ]; then
    print_info "Downloading recommended TLS parameters..."
    curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf > "$CERTBOT_DIR/conf/options-ssl-nginx.conf"
    curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem > "$CERTBOT_DIR/conf/ssl-dhparams.pem"
fi

# Check if certificate already exists
if [ -d "$CERTBOT_DIR/conf/live/$DOMAIN" ]; then
    print_warning "Certificate for $DOMAIN already exists!"
    read -p "Do you want to recreate it? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Removing existing certificate..."
        rm -rf "$CERTBOT_DIR/conf/live/$DOMAIN"
        rm -rf "$CERTBOT_DIR/conf/archive/$DOMAIN"
        rm -rf "$CERTBOT_DIR/conf/renewal/$DOMAIN.conf"
    else
        print_info "Using existing certificate"
        exit 0
    fi
fi

# Create dummy certificate for Nginx to start
print_info "Creating dummy certificate for Nginx..."
mkdir -p "$CERTBOT_DIR/conf/live/$DOMAIN"

openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout "$CERTBOT_DIR/conf/live/$DOMAIN/privkey.pem" \
    -out "$CERTBOT_DIR/conf/live/$DOMAIN/fullchain.pem" \
    -subj "/CN=$DOMAIN"

# Create initial Nginx configuration (using default.conf)
print_info "Setting up initial Nginx configuration..."
cp ./nginx/default.conf "$NGINX_CONF_DIR/default.conf"

# Start Nginx
print_info "Starting Nginx..."
docker-compose -f $COMPOSE_FILE up -d nginx

# Wait for Nginx to start
print_info "Waiting for Nginx to be ready..."
sleep 5

# Delete dummy certificate
print_info "Removing dummy certificate..."
rm -rf "$CERTBOT_DIR/conf/live/$DOMAIN"

# Request the real certificate
print_info "Requesting Let's Encrypt certificate for $DOMAIN..."
docker-compose -f $COMPOSE_FILE run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email $LETSENCRYPT_EMAIL \
    --agree-tos \
    --no-eff-email \
    --force-renewal \
    -d $DOMAIN

if [ $? -eq 0 ]; then
    print_info "Certificate obtained successfully!"
    
    # Create production Nginx configuration from template
    print_info "Setting up production Nginx configuration..."
    envsubst '${DOMAIN}' < ./nginx/app.conf.template > "$NGINX_CONF_DIR/app.conf"
    rm "$NGINX_CONF_DIR/default.conf"
    
    # Reload Nginx
    print_info "Reloading Nginx..."
    docker-compose -f $COMPOSE_FILE exec nginx nginx -s reload
    
    print_info "✅ SSL setup complete!"
    print_info "Your site is now available at: https://$DOMAIN"
else
    print_error "Certificate request failed!"
    print_info "Please check:"
    print_info "  1. DNS is pointing to this server"
    print_info "  2. Port 80 is accessible from the internet"
    print_info "  3. Domain name is correct"
    exit 1
fi

# Show certificate information
print_info "Certificate information:"
docker-compose -f $COMPOSE_FILE run --rm certbot certificates

print_info "🎉 All done! SSL is now active."
print_info "Certificates will auto-renew via the certbot service."

