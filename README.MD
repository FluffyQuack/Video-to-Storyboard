# Storyboard Creator

Turn any video into a single storyboard image: detect every cut, grab a frame from
each one, and stack them vertically with their timestamps. Optionally extract the
video's audio alongside it.

## Requirements

- **Python  3** with [Pillow](https://pypi.org/project/Pillow/) (`pip install pillow`) (probably works with earlier Python versions too?)
- **ffmpeg** and **ffprobe** on your `PATH` (or set the `FFMPEG_DIR` environment
  variable to the folder containing them) (or edit run.bat to link to your ffmpeg binaries directory)

## Usage

```
run.bat "path\to\video.mp4" [keyframe|diff] [single|pairs] [audio|noaudio]
```

Only the first argument (the video) is required. The remaining arguments all have
sensible defaults.

| Arg | Meaning | Default |
| --- | --- | --- |
| 1 | Path to the input video | *(required)* |
| 2 | Cut-detection mode — `keyframe` (every encoded I-frame) or `diff` (scene-change detection) | `keyframe` |
| 3 | Layout — `single` (one frame per cut) or `pairs` (first + last frame side by side with an arrow) | `single` |
| 4 | `audio` (extract the audio track to a `.wav`) or `noaudio` | `audio` |

### Example

Run this:

```
run.bat "C:\videos\my_clip.mp4"
```

Or drag'n'drop a video onto the run.bat batch file.

## Recommended settings

**Leave the defaults as they are.** The default settings (`keyframe` mode, `single`
layout, `audio` on) are tuned to produce the best results for the Seedance 2
workflow below, and changing them is not recommended.

## Output

A folder is created next to the video, named `<YYYY-MM-DD>-<video name>`, containing:

- The extracted frame PNGs (`..._FIRST.png`, `..._MIDDLE.png`, `..._LAST.png` per cut)
- `timestamps.txt` — maps each cut's time span to its frame
- `<video name>.wav` — the extracted audio (unless `noaudio` was used)
- `storyboard.png` — the final stacked storyboard image

## Using this with Seedance 2

This workflow can be used to **remake an existing video with Seedance 2 while
staying somewhat faithful to the original.** The resulting video won't be identical
to the source, but many of the cuts will end up looking similar.

If you supply the extracted audio as the input audio for the Seedance 2 video, the
**timing will be exact too**. Of course, you'll also end up with the original audio,
if that's what you prefer.

The result is more likely to be accurate when used with a video with a low amount of
cuts. Five or less works really well, for instance.

### How to prompt Seedance 2

Re-use the same prompt (and input images) as the original video, but add the following
to it:

> Reference @Image1 as storyboard for the sequence of events. Keep compositions the same as the storyboard. Use the audio from @Audio1 as audio for the video.

Attach the generated `storyboard.png` as `@Image1` (or as a different image num #) and the extracted `.wav` as
`@Audio1`.
