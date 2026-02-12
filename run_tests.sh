#!/bin/bash
# Test runner script for rigorq black-box tests

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}rigorq Black-Box Test Suite${NC}"
echo "=================================="
echo ""

# Check if rigorq is installed
if ! command -v rigorq &> /dev/null; then
    echo -e "${RED}Error: rigorq is not installed${NC}"
    echo "Install with: pipx install rigorq"
    exit 1
fi

echo -e "${GREEN}✓ rigorq is installed${NC}"
rigorq --version
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest is not installed${NC}"
    echo "Install with: pip install pytest"
    exit 1
fi

echo -e "${GREEN}✓ pytest is installed${NC}"
echo ""

# Parse command line arguments
PYTEST_ARGS=""
COVERAGE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --fast)
            PYTEST_ARGS="$PYTEST_ARGS -m 'not slow'"
            shift
            ;;
        --slow)
            PYTEST_ARGS="$PYTEST_ARGS -m 'slow'"
            shift
            ;;
        --coverage)
            COVERAGE="--cov=rigorq --cov-report=term --cov-report=html"
            shift
            ;;
        --failfast)
            PYTEST_ARGS="$PYTEST_ARGS -x"
            shift
            ;;
        --verbose)
            PYTEST_ARGS="$PYTEST_ARGS -vv"
            shift
            ;;
        *)
            PYTEST_ARGS="$PYTEST_ARGS $1"
            shift
            ;;
    esac
done

# Run tests
echo -e "${YELLOW}Running tests...${NC}"
echo "Command: pytest tests/test_cli_blackbox.py $PYTEST_ARGS $COVERAGE"
echo ""

if pytest tests/test_cli_blackbox.py $PYTEST_ARGS $COVERAGE; then
    echo ""
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi