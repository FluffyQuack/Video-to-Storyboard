"""
ExtractKeyframes.py

Extract frames from a video and write a timestamp/scene listing.

Two modes:
  keyframe  - extract every encoded keyframe (I-frame) as a PNG
  diff      - extract every frame that differs enough from the previous one
              to likely be a new scene (ffmpeg scene-detection)

For each detected cut, three frames are extracted: the first frame of the
cut, the middle frame, and the last frame (just before the next cut), named
with _FIRST / _MIDDLE / _LAST suffixes:

      video_0001_FIRST.png
      video_0001_MIDDLE.png
      video_0001_LAST.png

Output:
  A folder next to the video, named after the video (without extension),
  containing the extracted PNGs and a `timestamps.txt` file like:

      0-2.5s: video_0001_FIRST.png
      2.5-3s: video_0002_FIRST.png

Requires ffmpeg + ffprobe on PATH.

Usage:
    python ExtractKeyframes.py path/to/video.mp4 [--mode keyframe|diff] [--threshold 0.3]
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import date
from shutil import which

# Fallback locations to search for ffmpeg/ffprobe if they aren't on PATH.
# Override with the FFMPEG_DIR environment variable.
FFMPEG_DIRS = [
    os.environ.get("FFMPEG_DIR", ""),
    r"H:\apps\Video\ffmpeg\bin",
]


def resolve_tool(name):
    """Return a usable path to ffmpeg/ffprobe, checking PATH then fallbacks."""
    found = which(name)
    if found:
        return found
    for d in FFMPEG_DIRS:
        if not d:
            continue
        candidate = os.path.join(d, name + (".exe" if os.name == "nt" else ""))
        if os.path.isfile(candidate):
            return candidate
    sys.exit(f"ERROR: '{name}' was not found on PATH or in {FFMPEG_DIRS}. "
             f"Install ffmpeg or set FFMPEG_DIR.")


FFMPEG = None
FFPROBE = None


def get_duration(video):
    """
    Return the duration of the video *stream* in seconds (float).

    The container duration can be longer than the video stream (e.g. when the
    audio track outlasts the video), and seeking past the last video frame
    yields nothing — so prefer the stream duration and only fall back to the
    container duration.
    """
    for args in (["-select_streams", "v:0", "-show_entries", "stream=duration"],
                 ["-show_entries", "format=duration"]):
        cmd = [
            FFPROBE, "-v", "error",
            *args,
            "-of", "default=noprint_wrappers=1:nokey=1",
            video,
        ]
        out = subprocess.run(cmd, capture_output=True, text=True)
        try:
            return float(out.stdout.strip())
        except ValueError:
            continue
    return None


def detect_cut_times(video, mode, threshold):
    """
    Run ffmpeg to find the timestamps of the selected boundary frames.

    Nothing is saved (ffmpeg decodes to null); returns the list of
    scene-boundary timestamps in seconds.
    """
    if mode == "keyframe":
        # pict_type 'I' == keyframe. Always keep frame 0 too.
        select = r"eq(pict_type\,I)"
    else:
        # Scene change score above threshold, plus the very first frame
        # (whose scene score is undefined / 0).
        select = rf"gt(scene\,{threshold})+eq(n\,0)"

    vf = f"select='{select}',showinfo"
    cmd = [
        FFMPEG, "-hide_banner", "-y",
        "-i", video,
        "-vf", vf,
        "-vsync", "vfr",
        "-f", "null", "-",
    ]

    print(f"Running ffmpeg ({mode} mode, detecting cuts)...")
    proc = subprocess.run(cmd, capture_output=True, text=True)

    # showinfo prints to stderr; parse the pts_time for each matched frame.
    times = [float(m) for m in re.findall(r"pts_time:([0-9.]+)", proc.stderr)]

    if not times:
        sys.stderr.write(proc.stderr)
        sys.exit("ERROR: ffmpeg matched no frames. See output above.")

    return times


def get_fps(video):
    """Return the video's average frame rate (float), defaulting to 30."""
    cmd = [
        FFPROBE, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=avg_frame_rate",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True)
    txt = out.stdout.strip().splitlines()[0] if out.stdout.strip() else ""
    m = re.match(r"^(\d+)/(\d+)$", txt)
    if m and int(m.group(2)) != 0:
        return int(m.group(1)) / int(m.group(2))
    try:
        return float(txt)
    except ValueError:
        return 30.0


def extract_at_times(video, outdir, jobs, frame_dur=0.0):
    """
    Extract exactly one frame per (filename, timestamp) pair in jobs.
    Uses input seeking (-ss before -i), which is fast and frame-accurate on
    modern ffmpeg. Returns the list of saved PNG paths, in order.

    ffmpeg outputs the first frame whose pts is at/after the seek target, so
    when frame_dur > 0 each seek is biased back by half a frame to land in
    the gap *before* the intended frame — otherwise a seek time that rounds
    up past the frame's pts would yield the frame after it.

    If a seek lands past the last video frame (which yields no output), the
    timestamp is also stepped back by frame_dur a few times before giving up.
    """
    files = []
    for name, t in jobs:
        out = os.path.join(outdir, name)
        attempts = 4 if frame_dur > 0 else 1
        proc = None
        for attempt in range(attempts):
            seek = max(0.0, t - (attempt + 0.5) * frame_dur)
            cmd = [
                FFMPEG, "-hide_banner", "-y",
                "-ss", f"{seek:.3f}",
                "-i", video,
                "-frames:v", "1",
                out,
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if os.path.isfile(out) and os.path.getsize(out) > 0:
                if attempt:
                    print(f"NOTE: no frame at {t:.3f}s; used {seek:.3f}s for {name}.")
                break
        else:
            sys.stderr.write(proc.stderr)
            sys.exit(f"ERROR: ffmpeg failed to grab a frame at {t:.3f}s.")
        files.append(out)
    return files


def extract_audio(video, outdir):
    """Extract the video's audio track to a .wav file in outdir."""
    base = os.path.splitext(os.path.basename(video))[0]
    out = os.path.join(outdir, f"{base}.wav")
    cmd = [
        FFMPEG, "-hide_banner", "-y",
        "-i", video,
        "-vn",                  # drop video
        "-acodec", "pcm_s16le",  # standard 16-bit PCM WAV
        out,
    ]
    print("Extracting audio...")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.isfile(out):
        print(f"Wrote {out}")
        return out
    # No audio stream is not fatal — just warn.
    print("WARNING: no audio extracted (the video may have no audio track).")
    return None


def round_half(t):
    """Round to the nearest half second."""
    return round(t * 2) / 2.0


def fmt(t):
    """Format a half-second value: 3.0 -> '3', 2.5 -> '2.5'."""
    t = round_half(t)
    if t == int(t):
        return str(int(t))
    return str(t)


def write_timestamps(outdir, files, times, duration):
    """Write timestamps.txt mapping each scene span to its frame filename."""
    path = os.path.join(outdir, "timestamps.txt")
    end_of_video = duration if duration else (times[-1] if times else 0)

    with open(path, "w", encoding="utf-8") as f:
        for i, (frame, start) in enumerate(zip(files, times)):
            end = times[i + 1] if i + 1 < len(times) else end_of_video
            name = os.path.basename(frame)
            f.write(f"{fmt(start)}-{fmt(end)}s: {name}\n")

    print(f"Wrote {path}")
    return path


def main():
    parser = argparse.ArgumentParser(description="Extract keyframes / scene frames from a video.")
    parser.add_argument("video", help="Path to the input video.")
    parser.add_argument("--mode", choices=["keyframe", "diff"], default="keyframe",
                        help="keyframe: extract every I-frame. diff: extract scene-change frames.")
    parser.add_argument("--threshold", type=float, default=0.3,
                        help="Scene-change sensitivity for diff mode (0-1, default 0.3).")
    parser.add_argument("--audio", dest="audio", action="store_true", default=True,
                        help="Extract the audio track to a .wav file (default).")
    parser.add_argument("--no-audio", dest="audio", action="store_false",
                        help="Skip audio extraction.")
    args = parser.parse_args()

    global FFMPEG, FFPROBE
    FFMPEG = resolve_tool("ffmpeg")
    FFPROBE = resolve_tool("ffprobe")

    if not os.path.isfile(args.video):
        sys.exit(f"ERROR: video not found: {args.video}")

    base = os.path.splitext(os.path.basename(args.video))[0]
    # Prefix the output folder with today's date (YYYY-MM-DD).
    folder_name = f"{date.today().isoformat()}-{base}"
    outdir = os.path.join(os.path.dirname(os.path.abspath(args.video)), folder_name)
    os.makedirs(outdir, exist_ok=True)
    print(f"Output folder: {outdir}")

    duration = get_duration(args.video)

    # Detect scene boundaries (no files written), then grab the first, middle
    # and last frame of each scene span.
    times = detect_cut_times(args.video, args.mode, args.threshold)
    frame_dur = 1.0 / get_fps(args.video)
    end_of_video = duration if duration else times[-1]

    jobs = []
    for i, start in enumerate(times):
        end = times[i + 1] if i + 1 < len(times) else end_of_video
        middle = (start + end) / 2.0
        last = max(start, end - frame_dur)
        for suffix, t in (("FIRST", start), ("MIDDLE", middle), ("LAST", last)):
            jobs.append((f"{base}_{i + 1:04d}_{suffix}.png", t))
    files = extract_at_times(args.video, outdir, jobs, frame_dur=frame_dur)

    print(f"Extracted {len(files)} frames ({len(times)} cuts x 3).")
    first_files = files[0::3]
    write_timestamps(outdir, first_files, times, duration)
    if args.audio:
        extract_audio(args.video, outdir)


if __name__ == "__main__":
    main()
