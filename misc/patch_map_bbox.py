#!/usr/bin/env python3
"""Overwrite the bbox in a Mapsforge .map header with the bbox from another .map.

Mapsforge 0.27's map-writer shrinks the header bbox to the actual data extent
when the bounding-polygon clips inside the requested --bounding-box. That makes
the BiNavi Air anchor its tile grid at the wrong corner. This tool copies the
bbox from a stock (reference) map into a generated map by overwriting the
16 bytes at file offset 44 (4x int32 BE microdegrees: minLat, minLon, maxLat,
maxLon). Everything else in the file is untouched.

Usage:
    patch_map_bbox.py <reference.map> <target.map> [--no-backup]

The target's previous content is saved as <target.map>.bak unless --no-backup
is passed. Re-running the tool on an already-patched file is safe (it will
just overwrite the same 16 bytes with the same values).
"""
import struct
import sys
from pathlib import Path

MAGIC = b"mapsforge binary OSM"
BBOX_OFFSET = len(MAGIC) + 4 + 4 + 8 + 8  # magic + header_size + file_version + file_size + date_created


def read_bbox(path: Path):
    with path.open("rb") as f:
        head = f.read(BBOX_OFFSET + 16)
    if not head.startswith(MAGIC):
        raise ValueError(f"{path}: not a Mapsforge map file")
    return struct.unpack_from(">iiii", head, BBOX_OFFSET)


def write_bbox(path: Path, bbox):
    with path.open("rb") as f:
        head = f.read(BBOX_OFFSET + 16)
    if not head.startswith(MAGIC):
        raise ValueError(f"{path}: not a Mapsforge map file")
    packed = struct.pack(">iiii", *bbox)
    with path.open("r+b") as f:
        f.seek(BBOX_OFFSET)
        f.write(packed)


def fmt(bbox):
    min_lat, min_lon, max_lat, max_lon = (v / 1e6 for v in bbox)
    return f"lon={min_lon:.6f}..{max_lon:.6f}  lat={min_lat:.6f}..{max_lat:.6f}"


def main():
    args = sys.argv[1:]
    backup = True
    if "--no-backup" in args:
        backup = False
        args.remove("--no-backup")
    if len(args) != 2:
        print("usage: patch_map_bbox.py <reference.map> <target.map> [--no-backup]", file=sys.stderr)
        sys.exit(2)

    ref_path = Path(args[0])
    tgt_path = Path(args[1])

    ref_bbox = read_bbox(ref_path)
    tgt_bbox_before = read_bbox(tgt_path)

    print(f"reference: {ref_path}")
    print(f"  bbox: {fmt(ref_bbox)}")
    print(f"target:    {tgt_path}")
    print(f"  bbox before: {fmt(tgt_bbox_before)}")

    if ref_bbox == tgt_bbox_before:
        print("  (no change needed)")
        return

    if backup:
        bak = tgt_path.with_suffix(tgt_path.suffix + ".bak")
        if not bak.exists():
            bak.write_bytes(tgt_path.read_bytes())
            print(f"  backup: {bak}")
        else:
            print(f"  backup already exists: {bak} (not overwritten)")

    write_bbox(tgt_path, ref_bbox)
    tgt_bbox_after = read_bbox(tgt_path)
    print(f"  bbox after:  {fmt(tgt_bbox_after)}")
    if tgt_bbox_after != ref_bbox:
        print("  ERROR: write-back verification failed", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
