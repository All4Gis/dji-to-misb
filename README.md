# MISB / STANAG 4609 from a DJI video + telemetry

Turns **DJI drone footage** into a **MISB ST0601 / STANAG 4609** video: an
**MPEG-TS** with **video**, **audio** (if present) and a timed
**KLV telemetry channel**, built from the DJI video and its telemetry log
exported to CSV.

The result is ready to open and analyze in the
[**QGISFMV**](https://github.com/All4Gis/QGISFMV) QGIS plugin (Full Motion Video),
so you can play the video on the map and visualize the platform track, sensor
footprint and frame center from the embedded telemetry.

| File | Muxer | Requirements | Notes |
|------|-------|--------------|-------|
| **`misb_ffmpeg.py`** | FFmpeg + Python injection | Python + FFmpeg | The generator. KLV with per-packet PTS. |
| `misb_common.py` | — | Python (stdlib only) | MISB/CSV core (ST0601 encoder + CSV parsing). Not run directly. |
| `misb_check.py` | — | Python + FFmpeg + klvdata | Decodes/verifies the KLV channel of the result. |

> Why not use `klvdata` to *write* the KLV? `klvdata` is a parser; it can encode an
> individual value but cannot assemble the Local Set (no 16-byte key, no total BER
> length, no BCC-16 checksum) and its `PrecisionTimeStamp` encoder doesn't accept a
> `datetime`. So the self-contained encoder in `misb_common.py` builds the packets,
> and `klvdata` is used only to *decode/verify* the result in `misb_check.py`.

## Requirements

No venv, no pip packages needed to generate the video:

1. **Python 3.10+** (the real one, not the Microsoft Store alias).
   <https://www.python.org/downloads/>, tick *"Add python.exe to PATH"*.
2. **FFmpeg** on the PATH:
   ```powershell
   winget install Gyan.FFmpeg
   ```
   (or from <https://www.gyan.dev/ffmpeg/builds/>, adding its `bin` folder to the PATH).

> The ST0601 KLV encoder is built into `misb_common.py`: you don't need `klvdata`
> nor the `constants.py` from the earlier attempts to generate the video.
> (`klvdata` is only needed by `misb_check.py` to verify the result.)

## Sample data

Sample DJI videos and their telemetry (including the `DJI_0047` clip used to test
this tool, plus a few others under `QGISFMV_Samples/DJI/`) are available here:

- **Google Drive:** <https://drive.google.com/file/d/10LA6zWLXn6VraOMvQ15MR7XZGAwLlTU9/view?usp=drive_link>

Download a video + its `telemetry.csv` and point `--video` / `--csv` at them.

## Usage

`--video` and `--csv` are required (the script has no hardcoded defaults).

```powershell
# Basic run. --out is optional (defaults to <video_name>_MISB.ts)
python misb_ffmpeg.py --video DJI_0047.mp4 --csv telemetry.csv

# Specifying the output explicitly
python misb_ffmpeg.py --video DJI_0047.mp4 --csv telemetry.csv --out MISB.ts

# Only generate the binary .klv stream (for debugging).
# Without --video you must give --out so it knows where to write the .klv.
python misb_ffmpeg.py --csv telemetry.csv --out MISB.ts --klv-only

# If your CSV doesn't mark the recorded segment (CUSTOM.isVideo column)
python misb_ffmpeg.py --video DJI_0047.mp4 --csv telemetry.csv --all-rows
```

If you don't pass `--out`, the result is named after the original video with the
`_MISB` suffix, next to it (e.g. `DJI_0047.mp4` → `DJI_0047_MISB.ts`).

### Checking the result

Inspect the streams (you should see `Data: klv (KLVA)` next to the video; the KLV
carries a per-sample PTS):

```powershell
ffprobe DJI_0047_MISB.ts
```

Decode and validate the KLV with [`klvdata`](https://github.com/paretech/klvdata)
through `misb_check.py` (requires `pip install klvdata`):

```powershell
python misb_check.py DJI_0047_MISB.ts                 # dump all decoded packets
python misb_check.py DJI_0047_MISB.ts --play          # print the values at the video's real rate
python misb_check.py DJI_0047_MISB.ts --play --speed 4 # accelerated playback x4
python misb_check.py DJI_0047_MISB.ts --structure     # ST0601 tag tree of the first packet
python misb_check.py DJI_0047_MISB.ts --all           # show every present tag
```

This is the equivalent of the klvdata example:
`ffmpeg -i video.ts -map 0:d -codec copy -f data - | python -c "...klvdata..."`

## Tuning

In **`misb_common.py`**:

- `HFOV_DEG` / `VFOV_DEG`: your DJI camera field of view (affects the footprint on the map).
- `ST0601_VERSION`: advertised Local Set version (Tag 65).

---

> _"From raw drone footage to geospatial intelligence — one KLV packet at a time."_

Made with passion by **Fran Raga** · June 2026.

If this saved you a few hours, give the repo a star and fly safe. Happy coding!
