#!/usr/bin/env python3
"""
HTTP server with Range-request support for serving PMTiles AND a tile proxy
that reads tiles directly from .pmtiles files.

Replaces `python -m http.server 8000`.
Usage:
    cd Final_project
    python serve_range.py        # serves on port 8000
    python serve_range.py 8080   # serves on custom port

Tile endpoints (auto-discovered from *.pmtiles in the serve directory):
    GET /tiles/<name>/<z>/<x>/<y>.mvt  →  reads from <name>.pmtiles
"""

import os
import sys
import struct
import io
import gzip
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# ---------------------------------------------------------------------------
# PMTiles reader (minimal, spec v3 only)
# ---------------------------------------------------------------------------
HEADER_SIZE = 127

def _read_uint64(data, offset):
    return struct.unpack_from("<Q", data, offset)[0]

def _read_varint(buf, pos):
    val = 0
    shift = 0
    while True:
        b = buf[pos]
        pos += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return val, pos

def _deserialize_directory(data):
    buf = data
    pos = 0
    num_entries, pos = _read_varint(buf, pos)
    entries = []
    last_id = 0
    for _ in range(num_entries):
        v, pos = _read_varint(buf, pos)
        entries.append({"tile_id": last_id + v, "offset": 0, "length": 0, "run_length": 1})
        last_id += v
    for i in range(num_entries):
        entries[i]["run_length"], pos = _read_varint(buf, pos)
    for i in range(num_entries):
        entries[i]["length"], pos = _read_varint(buf, pos)
    for i in range(num_entries):
        v, pos = _read_varint(buf, pos)
        if v == 0 and i > 0:
            entries[i]["offset"] = entries[i-1]["offset"] + entries[i-1]["length"]
        else:
            entries[i]["offset"] = v - 1
    return entries

def _find_tile(entries, tile_id):
    lo, hi = 0, len(entries) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        cmp = tile_id - entries[mid]["tile_id"]
        if cmp > 0:
            lo = mid + 1
        elif cmp < 0:
            hi = mid - 1
        else:
            return entries[mid]
    if hi >= 0 and entries[hi]["run_length"] == 0:
        return entries[hi]
    if hi >= 0 and tile_id - entries[hi]["tile_id"] < entries[hi]["run_length"]:
        return entries[hi]
    return None

_ZXY_CACHE = {}  # (path, z, x, y) → bytes | None

def _zxy_to_tile_id(z, x, y):
    """Hilbert curve ZXY→tileId (PMTiles spec)."""
    tz = [0,1,5,21,85,341,1365,5461,21845,87381,349525,1398101,
          5592405,22369621,89478485,357913941,1431655765,5726623061,
          22906492245,91625968981,366503875925,1466015503701,
          5864062014805,23456248059221,93824992236885,375299968947541,1501199875790165]
    acc = tz[z]
    n = 1 << z
    xy = [x, y]
    d = 0
    s = n >> 1
    while s > 0:
        rx = 1 if (xy[0] & s) > 0 else 0
        ry = 1 if (xy[1] & s) > 0 else 0
        d += s * s * (3 * rx ^ ry)
        # rotate
        if ry == 0:
            if rx == 1:
                xy[0] = s - 1 - xy[0]
                xy[1] = s - 1 - xy[1]
            xy[0], xy[1] = xy[1], xy[0]
        s >>= 1
    return acc + d

def read_pmtiles_tile(pmtiles_path, z, x, y):
    """Read a single MVT tile from a PMTiles v3 file. Returns bytes or None."""
    key = (str(pmtiles_path), z, x, y)
    if key in _ZXY_CACHE:
        return _ZXY_CACHE[key]

    tile_id = _zxy_to_tile_id(z, x, y)

    with open(pmtiles_path, "rb") as f:
        header_raw = f.read(HEADER_SIZE)
        if len(header_raw) < HEADER_SIZE or header_raw[:7] != b"PMTiles":
            return None

        root_dir_offset = _read_uint64(header_raw, 8)
        root_dir_length = _read_uint64(header_raw, 16)
        leaf_dir_offset  = _read_uint64(header_raw, 40)
        tile_data_offset = _read_uint64(header_raw, 56)
        internal_compression = header_raw[97]  # 1=none, 2=gzip

        # Read root directory
        f.seek(root_dir_offset)
        root_raw = f.read(root_dir_length)
        if internal_compression == 2:
            root_raw = gzip.decompress(root_raw)
        root_dir = _deserialize_directory(root_raw)

        entry = _find_tile(root_dir, tile_id)
        if entry is None:
            _ZXY_CACHE[key] = None
            return None

        if entry["run_length"] == 0:
            # Leaf directory entry
            f.seek(leaf_dir_offset + entry["offset"])
            leaf_raw = f.read(entry["length"])
            if internal_compression == 2:
                leaf_raw = gzip.decompress(leaf_raw)
            leaf_dir = _deserialize_directory(leaf_raw)
            entry = _find_tile(leaf_dir, tile_id)
            if entry is None or entry["run_length"] == 0:
                _ZXY_CACHE[key] = None
                return None

        f.seek(tile_data_offset + entry["offset"])
        tile_data = f.read(entry["length"])

    # Tiles stored uncompressed (we wrote with Compression.NONE)
    tile_compression = header_raw[98]  # 1=none, 2=gzip
    if tile_compression == 2:
        tile_data = gzip.decompress(tile_data)

    _ZXY_CACHE[key] = tile_data
    return tile_data


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------
class RangeHTTPRequestHandler(SimpleHTTPRequestHandler):
    """Range-request capable HTTP server + PMTiles tile proxy."""

    SERVE_DIR = None  # set in main()

    def log_message(self, fmt, *args):
        pass  # suppress per-request logging

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def end_headers(self):
        self._send_cors_headers()
        super().end_headers()

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range, Content-Type")
        self.send_header("Access-Control-Expose-Headers",
                         "Content-Range, Accept-Ranges, Content-Length")
        self.send_header("Accept-Ranges", "bytes")

    def do_HEAD(self):
        f = self.send_head()
        if f:
            f.close()

    def do_GET(self):
        # Handle /tiles/<name>/<z>/<x>/<y>.mvt proxy requests
        path = self.path.split("?")[0]
        parts = path.strip("/").split("/")
        if len(parts) == 5 and parts[0] == "tiles" and parts[4].endswith(".mvt"):
            self._serve_tile_proxy(parts[1], parts[2], parts[3], parts[4][:-4])
            return

        range_header = self.headers.get("Range", "").strip()
        if range_header and range_header.startswith("bytes="):
            self._serve_range(range_header)
        else:
            f = self.send_head()
            if f:
                try:
                    self.copyfile(f, self.wfile)
                finally:
                    f.close()

    def _serve_tile_proxy(self, name, z_str, x_str, y_str):
        try:
            z, x, y = int(z_str), int(x_str), int(y_str)
        except ValueError:
            self.send_error(400, "Invalid tile coordinates")
            return

        pmtiles_path = Path(self.SERVE_DIR) / f"{name}.pmtiles"
        if not pmtiles_path.exists():
            self.send_error(404, f"PMTiles file not found: {name}.pmtiles")
            return

        try:
            tile_data = read_pmtiles_tile(pmtiles_path, z, x, y)
        except Exception as e:
            self.send_error(500, f"Error reading tile: {e}")
            return

        if tile_data is None:
            # Empty tile (200 with empty body is standard for vector tiles)
            self.send_response(204)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/x-protobuf")
        self.send_header("Content-Length", str(len(tile_data)))
        self.end_headers()
        self.wfile.write(tile_data)

    def _serve_range(self, range_header):
        path = self.translate_path(self.path)
        try:
            file_size = os.path.getsize(path)
        except OSError:
            self.send_error(404, "File not found")
            return

        spec = range_header[len("bytes="):].split(",")[0].strip()
        parts = spec.split("-")
        try:
            if parts[0] == "":
                start = max(0, file_size - int(parts[1]))
                end = file_size - 1
            elif parts[1] == "":
                start = int(parts[0])
                end = file_size - 1
            else:
                start = int(parts[0])
                end = int(parts[1])
        except (IndexError, ValueError):
            self.send_error(400, "Invalid Range header")
            return

        if start > end or start >= file_size:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{file_size}")
            self.end_headers()
            return

        end = min(end, file_size - 1)
        length = end - start + 1
        ctype = self.guess_type(path)

        self.send_response(206)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.send_header("Content-Length", str(length))
        self.end_headers()

        try:
            with open(path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (OSError, BrokenPipeError):
            pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    serve_dir = Path(__file__).parent
    os.chdir(serve_dir)
    RangeHTTPRequestHandler.SERVE_DIR = serve_dir

    # List discovered pmtiles files
    pmtiles_files = list(serve_dir.glob("*.pmtiles"))

    server = HTTPServer(("", port), RangeHTTPRequestHandler)
    print(f"Serving {serve_dir}")
    print(f"  → http://localhost:{port}/London_PTAL_Accessibility_Map.html")
    print(f"  Range requests: enabled")
    if pmtiles_files:
        for pf in pmtiles_files:
            print(f"  Tile proxy: /tiles/{pf.stem}/{{z}}/{{x}}/{{y}}.mvt → {pf.name}")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()

