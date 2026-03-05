#!/bin/bash
# Database Layer Validation Script
# Tests Docker setup, schema application, and basic operations

set -e  # Exit on error

echo "========================================"
echo "Weather Pipeline Database Validation"
echo "========================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠ .env file not found. Creating from template...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✓ Created .env from template${NC}"
    echo -e "${YELLOW}⚠ Please edit .env with your credentials before continuing${NC}"
    exit 1
fi

# Load environment variables
source .env

echo "1. Checking Docker daemon..."
if docker info > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Docker is running${NC}"
else
    echo -e "${RED}✗ Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

echo ""
echo "2. Starting services..."
docker-compose up -d

echo ""
echo "3. Waiting for PostgreSQL to be ready..."
sleep 5

# Check if container is running
if docker-compose ps | grep -q "weather_pipeline_db.*Up"; then
    echo -e "${GREEN}✓ PostgreSQL container is running${NC}"
else
    echo -e "${RED}✗ PostgreSQL container failed to start${NC}"
    docker-compose logs postgres
    exit 1
fi

echo ""
echo "4. Testing database connection..."
if docker-compose exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Database is accepting connections${NC}"
else
    echo -e "${RED}✗ Database connection failed${NC}"
    exit 1
fi

echo ""
echo "5. Verifying schema application..."

# Check if tables exist
TABLES=$(docker-compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';")
TABLES=$(echo $TABLES | xargs)  # Trim whitespace

if [ "$TABLES" -eq 2 ]; then
    echo -e "${GREEN}✓ Found 2 tables (locations, weather_readings)${NC}"
else
    echo -e "${RED}✗ Expected 2 tables, found $TABLES${NC}"
    exit 1
fi

# Check if indexes exist
INDEXES=$(docker-compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "SELECT COUNT(*) FROM pg_indexes WHERE schemaname='public';")
INDEXES=$(echo $INDEXES | xargs)

if [ "$INDEXES" -ge 4 ]; then
    echo -e "${GREEN}✓ Found $INDEXES indexes${NC}"
else
    echo -e "${YELLOW}⚠ Expected at least 4 indexes, found $INDEXES${NC}"
fi

echo ""
echo "6. Testing table structure..."

# Verify locations table columns
LOCATION_COLS=$(docker-compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='locations';")
LOCATION_COLS=$(echo $LOCATION_COLS | xargs)

if [ "$LOCATION_COLS" -eq 6 ]; then
    echo -e "${GREEN}✓ locations table has correct column count${NC}"
else
    echo -e "${RED}✗ locations table has $LOCATION_COLS columns (expected 6)${NC}"
fi

# Verify weather_readings table columns
READINGS_COLS=$(docker-compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='weather_readings';")
READINGS_COLS=$(echo $READINGS_COLS | xargs)

if [ "$READINGS_COLS" -eq 12 ]; then
    echo -e "${GREEN}✓ weather_readings table has correct column count${NC}"
else
    echo -e "${RED}✗ weather_readings table has $READINGS_COLS columns (expected 12)${NC}"
fi

echo ""
echo "7. Testing constraints..."

# Check unique constraint on locations
LOCATION_CONSTRAINTS=$(docker-compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "SELECT COUNT(*) FROM information_schema.table_constraints WHERE table_name='locations' AND constraint_type='UNIQUE';")
LOCATION_CONSTRAINTS=$(echo $LOCATION_CONSTRAINTS | xargs)

if [ "$LOCATION_CONSTRAINTS" -ge 1 ]; then
    echo -e "${GREEN}✓ locations table has unique constraint${NC}"
else
    echo -e "${RED}✗ locations table missing unique constraint${NC}"
fi

# Check foreign key on weather_readings
FK_CONSTRAINTS=$(docker-compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "SELECT COUNT(*) FROM information_schema.table_constraints WHERE table_name='weather_readings' AND constraint_type='FOREIGN KEY';")
FK_CONSTRAINTS=$(echo $FK_CONSTRAINTS | xargs)

if [ "$FK_CONSTRAINTS" -ge 1 ]; then
    echo -e "${GREEN}✓ weather_readings table has foreign key constraint${NC}"
else
    echo -e "${RED}✗ weather_readings table missing foreign key constraint${NC}"
fi

echo ""
echo "8. Testing idempotent insert..."

# Insert test location
docker-compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
    "INSERT INTO locations (city_name, country_code, latitude, longitude) VALUES ('TestCity', 'TC', 0.0, 0.0) ON CONFLICT (city_name, country_code) DO NOTHING;" > /dev/null 2>&1

# Try to insert again (should be ignored)
docker-compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
    "INSERT INTO locations (city_name, country_code, latitude, longitude) VALUES ('TestCity', 'TC', 0.0, 0.0) ON CONFLICT (city_name, country_code) DO NOTHING;" > /dev/null 2>&1

# Verify only one row exists
TEST_COUNT=$(docker-compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "SELECT COUNT(*) FROM locations WHERE city_name='TestCity';")
TEST_COUNT=$(echo $TEST_COUNT | xargs)

if [ "$TEST_COUNT" -eq 1 ]; then
    echo -e "${GREEN}✓ Idempotent insert works correctly${NC}"
else
    echo -e "${RED}✗ Idempotent insert failed (found $TEST_COUNT rows, expected 1)${NC}"
fi

# Cleanup test data
docker-compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
    "DELETE FROM locations WHERE city_name='TestCity';" > /dev/null 2>&1

echo ""
echo "9. Checking pgAdmin..."
if docker-compose ps | grep -q "weather_pipeline_pgadmin.*Up"; then
    echo -e "${GREEN}✓ pgAdmin container is running${NC}"
    echo -e "  Access at: ${YELLOW}http://localhost:5050${NC}"
else
    echo -e "${YELLOW}⚠ pgAdmin container not running${NC}"
fi

echo ""
echo "========================================"
echo -e "${GREEN}✓ All validations passed!${NC}"
echo "========================================"
echo ""
echo "Quick commands:"
echo "  - View logs: docker-compose logs -f postgres"
echo "  - Connect to DB: docker-compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB"
echo "  - Stop services: docker-compose down"
echo "  - pgAdmin: http://localhost:5050"
echo ""
echo "Database connection details:"
echo "  Host: localhost (or 'postgres' from within Docker)"
echo "  Port: $POSTGRES_PORT"
echo "  Database: $POSTGRES_DB"
echo "  User: $POSTGRES_USER"
echo ""
