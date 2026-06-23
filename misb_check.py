# -*- coding: utf-8 -*-
r"""
misb_check.py
=============

Checks the KLV channel of a MISB / STANAG 4609 video (the one produced by
misb_ffmpeg.py) by extracting it with FFmpeg and decoding it with the reference
library klvdata (https://github.com/paretech/klvdata).

Equivalent to:
    ffmpeg -i video.ts -map 0:d -codec copy -f data - | python -c "...klvdata..."

Modes:
    (default)      Dump every decoded ST0601 packet.
    --play         Playback: print the values to the console at the video's real
                   rate (using each packet's Precision Time Stamp).
    --structure    Show the tag tree of the first packet (klvdata.structure).

Requirements:
    - FFmpeg on the PATH.
    - klvdata:   pip install klvdata

Examples
--------
    python misb_check.py DJI_0047_MISB.ts
    python misb_check.py output.ts --play
    python misb_check.py output.ts --play --speed 4
    python misb_check.py output.ts --all
    python misb_check.py output.ts --structure
"""

from __future__ import annotations

import os
import sys
import time
import shutil
import argparse
import subprocess
from datetime import datetime

# Short labels for the most common ST0601 tags
LABELS = {
    2: "t", 5: "hdg", 6: "pitch", 7: "roll",
    13: "lat", 14: "lon", 15: "alt",
    16: "hfov", 17: "vfov", 18: "g_az", 19: "g_el", 20: "g_roll",
    21: "slant", 22: "tw", 23: "fc_lat", 24: "fc_lon", 25: "fc_elev", 65: "ver",
}
# Order of the fields shown by default
DEFAULT_FIELDS = [2, 13, 14, 15, 5, 6, 7, 21, 23, 24]


def extract_klv(ts_path: str) -> bytes:
    """Extract the KLV data stream from the TS with FFmpeg (-map 0:d -c copy -f data)."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("'ffmpeg' not found on the PATH.")
    cmd = [ffmpeg, "-v", "error", "-i", ts_path, "-map", "0:d", "-c", "copy", "-f", "data", "-"]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0 or not res.stdout:
        msg = res.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"FFmpeg could not extract the data channel.\n{msg}")
    return res.stdout


def _fmt_value(value: str) -> str:
    """Round floats to keep the line readable; leave the rest as-is."""
    try:
        return f"{float(value):.5f}"
    except (TypeError, ValueError):
        return value


def _line(metadata: dict, fields) -> str:
    parts = []
    for tag in fields:
        if tag in metadata:
            label = LABELS.get(tag, str(tag))
            value = metadata[tag][3]            # (LDSName, ESDName, UDSName, value)
            parts.append(f"{label}={_fmt_value(value)}" if tag != 2 else f"{value}")
    return "  ".join(parts)


def _timestamp(metadata: dict):
    """Return the Precision Time Stamp (tag 2) as a datetime, or None."""
    if 2 not in metadata:
        return None
    try:
        return datetime.fromisoformat(metadata[2][3])
    except (TypeError, ValueError):
        return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Check/decode the KLV channel of a MISB video with klvdata.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python misb_check.py DJI_0047_MISB.ts\n"
            "  python misb_check.py output.ts --play --speed 4\n"
            "  python misb_check.py output.ts --all\n"
            "  python misb_check.py output.ts --structure\n"
        ),
    )
    parser.add_argument("video", help="MISB/TS video to check")
    parser.add_argument("--ts", default=None,
                        help="Alternative to passing the video as a positional argument")
    parser.add_argument("--play", action="store_true",
                        help="Print the values at the video's real rate (per the timestamp)")
    parser.add_argument("--speed", type=float, default=1.0,
                        help="Speed multiplier for --play (e.g. 4 = x4)")
    parser.add_argument("--all", action="store_true",
                        help="Show every present tag (not just the main ones)")
    parser.add_argument("--structure", action="store_true",
                        help="Show the tag tree of the first packet and exit")
    args = parser.parse_args(argv)

    ts_path = args.ts or args.video       # --ts takes precedence if given
    if not os.path.isfile(ts_path):
        print(f"[ERROR] Video does not exist: {ts_path}", file=sys.stderr)
        return 2

    try:
        import klvdata
    except ImportError:
        print("[ERROR] The 'klvdata' library is missing. Install it with:\n"
              "        pip install klvdata", file=sys.stderr)
        return 3

    print(f"Extracting the KLV channel from {ts_path} ...")
    data = extract_klv(ts_path)
    packets = list(klvdata.StreamParser(data))
    if not packets:
        print("[ERROR] No KLV packets found in the video.", file=sys.stderr)
        return 4
    print(f"{len(packets)} ST0601 packets decoded.\n")

    if args.structure:
        packets[0].structure()
        return 0

    # List of metadata (OrderedDict {tag: (LDSName, ESDName, UDSName, value)})
    metas = [p.MetadataList() for p in packets]

    if not args.play:
        for i, md in enumerate(metas):
            fields = sorted(md) if args.all else DEFAULT_FIELDS
            print(f"[{i:4d}] {_line(md, fields)}")
        return 0

    # Playback mode: pause between packets according to the Precision Time Stamp
    print(f"Playing at x{args.speed:g} (Ctrl+C to stop)...\n")
    t0_meta = _timestamp(metas[0])
    t0_real = time.monotonic()
    for i, md in enumerate(metas):
        ts = _timestamp(md)
        if ts is not None and t0_meta is not None:
            target = (ts - t0_meta).total_seconds() / max(args.speed, 1e-6)
            delay = target - (time.monotonic() - t0_real)
            if delay > 0:
                time.sleep(delay)
        fields = sorted(md) if args.all else DEFAULT_FIELDS
        stamp = ts.strftime("%H:%M:%S.%f")[:-3] if ts else f"#{i}"
        print(f"[{stamp}] {_line(md, [f for f in fields if f != 2])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
