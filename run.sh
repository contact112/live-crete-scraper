#!/bin/bash

#############################################
# Live Crete Scraper - Run Script
#############################################

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "============================================"
echo "Live Crete Events Scraper"
echo "============================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}Error: Virtual environment not found${NC}"
    echo "Please run ./setup.sh first"
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${RED}Error: Failed to activate virtual environment${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Virtual environment activated${NC}"
echo ""

# Parse command line arguments
WORKERS=5
NO_CACHE=""
NO_IMAGES=""
NO_TRANSLATION=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --workers)
            WORKERS="$2"
            shift 2
            ;;
        --no-cache)
            NO_CACHE="--no-cache"
            shift
            ;;
        --no-images)
            NO_IMAGES="--no-images"
            shift
            ;;
        --no-translation)
            NO_TRANSLATION="--no-translation"
            shift
            ;;
        --help)
            echo "Usage: ./run.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --workers N           Number of parallel workers (default: 5)"
            echo "  --no-cache           Disable caching"
            echo "  --no-images          Skip image downloading"
            echo "  --no-translation     Skip translation"
            echo "  --help               Show this help message"
            echo ""
            exit 0
            ;;
        *)
            echo -e "${YELLOW}Warning: Unknown option: $1${NC}"
            shift
            ;;
    esac
done

# Display settings
echo "Settings:"
echo "  Workers: $WORKERS"
echo "  Cache: $([ -z "$NO_CACHE" ] && echo 'enabled' || echo 'disabled')"
echo "  Images: $([ -z "$NO_IMAGES" ] && echo 'enabled' || echo 'disabled')"
echo "  Translation: $([ -z "$NO_TRANSLATION" ] && echo 'enabled' || echo 'disabled')"
echo ""

# Run the scraper
echo "Starting scraper..."
echo ""
echo "============================================"
echo ""

python3 main.py --workers $WORKERS $NO_CACHE $NO_IMAGES $NO_TRANSLATION

EXIT_CODE=$?

echo ""
echo "============================================"
echo ""

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Scraping completed successfully!${NC}"
    echo ""
    echo "Output files saved in: data/output/"
    echo ""
    echo "To import to WordPress, run:"
    echo "  python3 import_to_wordpress.py data/output/crete_events_*.csv"
    echo ""
else
    echo -e "${RED}✗ Scraping failed with exit code $EXIT_CODE${NC}"
    echo ""
    echo "Check the logs in data/logs/ for more information"
    echo ""
fi

exit $EXIT_CODE
