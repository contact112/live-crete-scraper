#!/bin/bash

#############################################
# Live Crete Scraper - Installation Script
#############################################

set -e  # Exit on error

echo "============================================"
echo "Live Crete Events Scraper - Setup"
echo "============================================"
echo ""

# Check Python version
echo "[1/6] Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
echo "✓ Python $PYTHON_VERSION found"
echo ""

# Check if virtual environment exists
echo "[2/6] Setting up virtual environment..."
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "[3/6] Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Upgrade pip
echo "[4/6] Upgrading pip..."
pip install --upgrade pip --quiet
echo "✓ pip upgraded"
echo ""

# Install dependencies
echo "[5/6] Installing dependencies..."
echo "This may take a few minutes..."
pip install -r requirements.txt --quiet

if [ $? -eq 0 ]; then
    echo "✓ All dependencies installed successfully"
else
    echo "✗ Failed to install some dependencies"
    echo "Please check the error messages above"
    exit 1
fi
echo ""

# Install Chrome/Chromium for Selenium (optional)
echo "[6/6] Checking Chrome/Chromium..."
if command -v google-chrome &> /dev/null; then
    echo "✓ Google Chrome found"
elif command -v chromium &> /dev/null; then
    echo "✓ Chromium found"
elif command -v chromium-browser &> /dev/null; then
    echo "✓ Chromium browser found"
else
    echo "⚠ Warning: Chrome/Chromium not found"
    echo "Please install Chrome or Chromium for Selenium to work:"
    echo ""
    echo "Ubuntu/Debian:"
    echo "  sudo apt-get update"
    echo "  sudo apt-get install chromium-browser"
    echo ""
    echo "macOS:"
    echo "  brew install --cask google-chrome"
    echo ""
    echo "Alternatively, undetected-chromedriver will try to download it automatically"
fi
echo ""

# Make scripts executable
echo "Making scripts executable..."
chmod +x main.py
chmod +x import_to_wordpress.py
chmod +x run.sh
echo "✓ Scripts are now executable"
echo ""

# Create necessary directories
echo "Ensuring all directories exist..."
mkdir -p data/output data/cache data/backups data/logs
mkdir -p images/events/full images/events/medium images/events/thumbnail
mkdir -p cookies
echo "✓ Directories created"
echo ""

echo "============================================"
echo "✓ Setup completed successfully!"
echo "============================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Configure WordPress credentials in config.json:"
echo "   - wordpress.site_url"
echo "   - wordpress.username"
echo "   - wordpress.password"
echo ""
echo "2. Review other settings in config.json"
echo ""
echo "3. Run the scraper:"
echo "   ./run.sh"
echo ""
echo "   Or manually:"
echo "   source venv/bin/activate"
echo "   python3 main.py"
echo ""
echo "4. Import to WordPress:"
echo "   python3 import_to_wordpress.py data/output/crete_events_*.csv"
echo ""
echo "============================================"
