#!/bin/bash
# Verification script to check if everything is set up correctly

echo "========================================="
echo "Infomerics Scraper API - Setup Verification"
echo "========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check 1: API directory exists
echo -n "Checking API directory... "
if [ -d "api" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ Missing${NC}"
    exit 1
fi

# Check 2: Required API files
echo -n "Checking API files... "
REQUIRED_FILES=(
    "api/main.py"
    "api/models.py"
    "api/auth.py"
    "api/jobs.py"
    "api/airtable_client.py"
    "api/scraper_service.py"
    "api/config.py"
    "api/requirements.txt"
)

MISSING_FILES=()
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -eq 0 ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ Missing files:${NC}"
    for file in "${MISSING_FILES[@]}"; do
        echo "  - $file"
    done
    exit 1
fi

# Check 3: Docker files
echo -n "Checking Docker files... "
if [ -f "Dockerfile" ] && [ -f "docker-compose.yml" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ Missing Dockerfile or docker-compose.yml${NC}"
    exit 1
fi

# Check 4: Documentation
echo -n "Checking documentation... "
if [ -f "SETUP.md" ] && [ -f "QUICKSTART.md" ] && [ -f "README.md" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ Missing documentation files${NC}"
    exit 1
fi

# Check 5: Environment file
echo -n "Checking .env file... "
if [ -f ".env" ]; then
    echo -e "${GREEN}✓${NC}"
    
    # Check if values are configured
    echo -n "  Checking AIRTABLE_BASE_ID... "
    if grep -q "AIRTABLE_BASE_ID=app" .env; then
        BASE_ID=$(grep "AIRTABLE_BASE_ID" .env | cut -d'=' -f2)
        if [ "$BASE_ID" = "appYourBaseId" ]; then
            echo -e "${YELLOW}⚠ Not configured${NC}"
        else
            echo -e "${GREEN}✓${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ Not found${NC}"
    fi
    
    echo -n "  Checking API_KEY... "
    if grep -q "API_KEY=" .env; then
        API_KEY=$(grep "API_KEY" .env | cut -d'=' -f2)
        if [ "$API_KEY" = "your_secure_api_key_here" ] || [ "$API_KEY" = "your-api-key-here" ]; then
            echo -e "${YELLOW}⚠ Using default (change for production)${NC}"
        else
            echo -e "${GREEN}✓${NC}"
        fi
    else
        echo -e "${RED}✗ Not found${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Missing (copy from env.example)${NC}"
    echo ""
    echo "  Run: cp env.example .env"
    echo "  Then edit .env with your Airtable credentials"
fi

# Check 6: Python dependencies (if Python is available)
echo -n "Checking Python... "
if command -v python3 &> /dev/null; then
    echo -e "${GREEN}✓ $(python3 --version)${NC}"
else
    echo -e "${YELLOW}⚠ Not found (needed for local development)${NC}"
fi

# Check 7: Docker (if available)
echo -n "Checking Docker... "
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✓ $(docker --version)${NC}"
    
    echo -n "Checking Docker Compose... "
    if command -v docker-compose &> /dev/null; then
        echo -e "${GREEN}✓ $(docker-compose --version)${NC}"
    else
        echo -e "${YELLOW}⚠ Not found${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Not found (needed for deployment)${NC}"
fi

# Check 8: Airtable schema
echo -n "Checking Airtable schema... "
if [ -f "airtable_base_schema.json" ]; then
    if [ -s "airtable_base_schema.json" ]; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗ File is empty${NC}"
    fi
else
    echo -e "${RED}✗ Missing${NC}"
fi

echo ""
echo "========================================="
echo "Verification Complete"
echo "========================================="
echo ""

# Final recommendations
echo "Next Steps:"
echo ""
if [ ! -f ".env" ]; then
    echo "1. ${YELLOW}Create .env file:${NC}"
    echo "   cp env.example .env"
    echo ""
fi

echo "2. ${YELLOW}Configure .env with your credentials:${NC}"
echo "   - Get Airtable Base ID from your Airtable URL"
echo "   - Set AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX"
echo "   - Generate secure API_KEY"
echo ""

echo "3. ${YELLOW}Start the API:${NC}"
echo "   docker-compose up --build -d"
echo ""

echo "4. ${YELLOW}Test the API:${NC}"
echo "   ./test_api.sh"
echo ""

echo "For detailed instructions, see:"
echo "  - QUICKSTART.md (5-minute setup)"
echo "  - SETUP.md (comprehensive guide)"
echo "  - api/README.md (API documentation)"
echo ""

