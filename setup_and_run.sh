#!/bin/bash

echo "=========================================="
echo "🚀 Flask Backend Setup Script"
echo "=========================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Fix SSL certificate issue (macOS specific)
echo -e "\n${YELLOW}Step 1: Checking Python installation...${NC}"
python3 --version

# Try to fix SSL certificates on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "${YELLOW}Fixing SSL certificates for macOS...${NC}"
    
    # Find Python certificate installer
    CERT_PATH="/Applications/Python 3.*/Install Certificates.command"
    if ls /Applications/Python\ 3.*/Install\ Certificates.command 1> /dev/null 2>&1; then
        echo -e "${GREEN}Found Python certificate installer. Running it...${NC}"
        /Applications/Python\ 3.*/Install\ Certificates.command
    else
        echo -e "${YELLOW}Certificate installer not found. Trying alternative method...${NC}"
        pip3 install --upgrade certifi
    fi
fi

# Step 2: Create virtual environment
echo -e "\n${YELLOW}Step 2: Creating virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created!${NC}"
else
    echo -e "${GREEN}✓ Virtual environment already exists!${NC}"
fi

# Step 3: Activate virtual environment
echo -e "\n${YELLOW}Step 3: Activating virtual environment...${NC}"
source venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated!${NC}"

# Step 4: Upgrade pip
echo -e "\n${YELLOW}Step 4: Upgrading pip...${NC}"
pip install --upgrade pip

# Step 5: Install requirements
echo -e "\n${YELLOW}Step 5: Installing Python packages...${NC}"
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All packages installed successfully!${NC}"
else
    echo -e "${RED}✗ Package installation failed. See errors above.${NC}"
    echo -e "${YELLOW}Try running manually:${NC}"
    echo "  source venv/bin/activate"
    echo "  pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt"
    exit 1
fi

# Step 6: Success message
echo -e "\n${GREEN}=========================================="
echo "✅ Setup Complete!"
echo "==========================================${NC}"

echo -e "\n${YELLOW}To start your Flask backend, run:${NC}"
echo -e "  ${GREEN}source venv/bin/activate${NC}"
echo -e "  ${GREEN}python main.py${NC}"

echo -e "\n${YELLOW}Or use this shortcut script:${NC}"
echo -e "  ${GREEN}bash run_backend.sh${NC}"

echo -e "\n${YELLOW}Your social media API will be available at:${NC}"
echo -e "  ${GREEN}http://localhost:8423/api/post/all${NC}"

