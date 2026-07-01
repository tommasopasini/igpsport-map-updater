#!/usr/bin/env python3
"""Print 'MIN_LON MAX_LON MIN_LAT MAX_LAT' for a Mapsforge .map file's header bbox.

Exit 1 if the file is not a Mapsforge map. Used by script.sh to inherit the
stock-map bbox during the BiNavi Air alignment investigation (H3 trial).
"""
import struct
import sys

MAGIC = b"mapsforge binary OSM"


def main():
    if len(sys.argv) != 2:
        print("usage: read_map_bbox.py FILE.map", file=sys.stderr)
        sys.exit(2)
    try:
        with open(sys.argv[1], "rb") as f:
            head = f.read(64)
    except OSError:
        sys.exit(1)
    if not head.startswith(MAGIC):
        sys.exit(1)
    # Skip: magic(20) + header_size(4) + file_version(4) + file_size(8) + date(8)
    pos = len(MAGIC) + 4 + 4 + 8 + 8
    min_lat, min_lon, max_lat, max_lon = (v / 1e6 for v in struct.unpack_from(">iiii", head, pos))
    print(f"{min_lon:.6f} {max_lon:.6f} {min_lat:.6f} {max_lat:.6f}")


if __name__ == "__main__":
    main()
