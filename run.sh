#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check for original maps directory argument
if [ $# -eq 0 ]; then
    echo "Usage: ./run.sh <directory_with_original_maps>"
    echo ""
    echo "Example:"
    echo "  ./run.sh backup/"
    echo "  ./run.sh /home/me/igpsport-maps/original"
    exit 1
fi

MAPS_DIR="$1"

if [ ! -d "$MAPS_DIR" ]; then
    echo "Error: '$MAPS_DIR' is not a directory." >&2
    exit 1
fi

# Step 1: Generate maps.csv
echo ""
echo "=========================================="
echo "Step 1: Generating maps.csv"
echo "=========================================="
echo ""

python3 "$SCRIPT_DIR/generate_maps_csv.py" "$MAPS_DIR" -o "$SCRIPT_DIR/maps.csv"

# Step 2: Generate maps
echo ""
echo "=========================================="
echo "Step 2: Generating maps"
echo "=========================================="
echo ""

"$SCRIPT_DIR/script.sh"
