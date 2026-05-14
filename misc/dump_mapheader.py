#!/usr/bin/env python3
"""Print the Mapsforge binary map-file header for one or more .map files.

Used during the BiNavi Air alignment investigation to compare stock vs
generated map headers. See INVESTIGATION.md.

Spec: https://github.com/mapsforge/mapsforge/blob/master/docs/Specification-Binary-Map-File.md
"""
import struct
import sys
from datetime import datetime, timezone

MAGIC = b"mapsforge binary OSM"


def read_string(buf, pos):
    n = buf[pos]
    pos += 1
    # 1-byte length, but spec allows VBE-U; in practice header strings fit in <128
    if n & 0x80:
        # VBE-U continuation
        value = n & 0x7F
        shift = 7
        while True:
            b = buf[pos]
            pos += 1
            value |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7
        n = value
    s = buf[pos:pos + n].decode("utf-8", errors="replace")
    return s, pos + n


def parse_header(path):
    with open(path, "rb") as f:
        head = f.read(4096)
    if not head.startswith(MAGIC):
        raise ValueError(f"{path}: not a Mapsforge map file (bad magic)")
    pos = len(MAGIC)
    (header_size,) = struct.unpack_from(">I", head, pos); pos += 4
    (file_version,) = struct.unpack_from(">I", head, pos); pos += 4
    (file_size,) = struct.unpack_from(">q", head, pos); pos += 8
    (date_created,) = struct.unpack_from(">q", head, pos); pos += 8
    bbox = struct.unpack_from(">iiii", head, pos); pos += 16
    min_lat, min_lon, max_lat, max_lon = (v / 1e6 for v in bbox)
    (tile_size,) = struct.unpack_from(">H", head, pos); pos += 2
    projection, pos = read_string(head, pos)
    flags = head[pos]; pos += 1
    has_start_pos = bool(flags & 0x40)
    has_start_zoom = bool(flags & 0x20)
    has_pref_lang = bool(flags & 0x10)
    has_comment = bool(flags & 0x08)
    has_created_by = bool(flags & 0x04)

    start_lat = start_lon = None
    if has_start_pos:
        sp = struct.unpack_from(">ii", head, pos); pos += 8
        start_lat, start_lon = sp[0] / 1e6, sp[1] / 1e6
    start_zoom = None
    if has_start_zoom:
        start_zoom = head[pos]; pos += 1
    pref_lang = comment = created_by = None
    if has_pref_lang:
        pref_lang, pos = read_string(head, pos)
    if has_comment:
        comment, pos = read_string(head, pos)
    if has_created_by:
        created_by, pos = read_string(head, pos)

    n_poi = head[pos]; pos += 1
    poi_tags = []
    for _ in range(n_poi):
        s, pos = read_string(head, pos)
        poi_tags.append(s)
    n_way = head[pos]; pos += 1
    way_tags = []
    for _ in range(n_way):
        s, pos = read_string(head, pos)
        way_tags.append(s)

    n_intervals = head[pos]; pos += 1
    intervals = []
    for _ in range(n_intervals):
        base_zoom = head[pos]; pos += 1
        min_zoom = head[pos]; pos += 1
        max_zoom = head[pos]; pos += 1
        (sub_start,) = struct.unpack_from(">q", head, pos); pos += 8
        (sub_size,) = struct.unpack_from(">q", head, pos); pos += 8
        intervals.append((base_zoom, min_zoom, max_zoom, sub_start, sub_size))

    return {
        "path": path,
        "header_size": header_size,
        "file_version": file_version,
        "file_size": file_size,
        "date_created": datetime.fromtimestamp(date_created / 1000, tz=timezone.utc),
        "bbox": (min_lat, min_lon, max_lat, max_lon),
        "tile_size": tile_size,
        "projection": projection,
        "flags": flags,
        "start_pos": (start_lat, start_lon),
        "start_zoom": start_zoom,
        "pref_lang": pref_lang,
        "comment": comment,
        "created_by": created_by,
        "poi_tags_count": len(poi_tags),
        "way_tags_count": len(way_tags),
        "intervals": intervals,
    }


def print_one(h):
    p = h["path"]
    print(f"== {p}")
    print(f"  file_version : {h['file_version']}")
    print(f"  file_size    : {h['file_size']:,}")
    print(f"  date_created : {h['date_created'].isoformat()}")
    mnlat, mnlon, mxlat, mxlon = h["bbox"]
    print(f"  bbox (lon,lat): {mnlon:.6f}, {mnlat:.6f}  ->  {mxlon:.6f}, {mxlat:.6f}")
    print(f"  span         : {mxlon - mnlon:.6f} x {mxlat - mnlat:.6f}")
    print(f"  tile_size    : {h['tile_size']}")
    print(f"  projection   : {h['projection']}")
    print(f"  flags        : 0x{h['flags']:02x}")
    if h["start_pos"][0] is not None:
        print(f"  start_pos    : {h['start_pos'][1]:.6f}, {h['start_pos'][0]:.6f}")
    if h["start_zoom"] is not None:
        print(f"  start_zoom   : {h['start_zoom']}")
    if h["pref_lang"]:
        print(f"  pref_lang    : {h['pref_lang']}")
    if h["comment"]:
        print(f"  comment      : {h['comment']}")
    if h["created_by"]:
        print(f"  created_by   : {h['created_by']}")
    print(f"  poi_tags     : {h['poi_tags_count']}")
    print(f"  way_tags     : {h['way_tags_count']}")
    print(f"  intervals    :")
    for base, mn, mx, ss, sz in h["intervals"]:
        print(f"    base={base} zoom={mn}-{mx} sub_start={ss} sub_size={sz}")


def main():
    if len(sys.argv) < 2:
        print("usage: dump_mapheader.py FILE.map [FILE.map ...]", file=sys.stderr)
        sys.exit(2)
    for p in sys.argv[1:]:
        try:
            h = parse_header(p)
            print_one(h)
        except Exception as exc:
            print(f"== {p}\n  ERROR: {exc}")
        print()


if __name__ == "__main__":
    main()
