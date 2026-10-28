"""Generate a headless 30-second mobile portrait video of the Jupiter occultation.

Renders frames in Stellarium without any text, labels, or markers,
then compiles them with ffmpeg into a 720x1280 portrait MP4.
"""

import os
import shutil
import subprocess
import sys
import time

CWD = os.path.abspath(".")
FRAMES_DIR = os.path.join(CWD, "frames").replace("\\", "/")
VIDEO_DIR = os.path.join(CWD, "video")
os.makedirs(VIDEO_DIR, exist_ok=True)

CONFIG_SRC = os.path.expandvars(r"%APPDATA%\Stellarium\config.ini")
CONFIG_DST = os.path.join(CWD, "render_config.ini")
SCRIPT_DST = os.path.expandvars(r"%APPDATA%\Stellarium\scripts\record_portrait_clean.ssc")

# 1. Clean frames folder
if os.path.exists("frames"):
    shutil.rmtree("frames")
os.makedirs("frames", exist_ok=True)

# 2. Prepare render_config.ini
with open(CONFIG_SRC, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
in_video = False
in_scripts = False
in_main = False
found_script_flag = False
found_screenshot_dir = False

for line in lines:
    stripped = line.strip()
    if stripped == "[video]":
        in_video = True
        in_scripts = in_main = False
    elif stripped == "[scripts]":
        in_scripts = True
        in_video = in_main = False
    elif stripped == "[main]":
        in_main = True
        in_video = in_scripts = False
    elif stripped.startswith("["):
        in_video = in_scripts = in_main = False

    if in_video and stripped.startswith("fullscreen"):
        new_lines.append("fullscreen                             = false\n")
    elif in_video and stripped.startswith("screen_w"):
        new_lines.append("screen_w                               = 720\n")
    elif in_video and stripped.startswith("screen_h"):
        new_lines.append("screen_h                               = 1280\n")
    elif in_video and stripped.startswith("screen_x"):
        new_lines.append("screen_x                               = 100\n")
    elif in_video and stripped.startswith("screen_y"):
        new_lines.append("screen_y                               = 50\n")
    elif in_scripts and stripped.startswith("flag_script_allow_write_absolute_path"):
        new_lines.append("flag_script_allow_write_absolute_path  = true\n")
        found_script_flag = True
    elif in_main and stripped.startswith("screenshot_dir"):
        new_lines.append(f"screenshot_dir                         = {FRAMES_DIR}\n")
        found_screenshot_dir = True
    else:
        new_lines.append(line)

if not found_script_flag:
    for i, line in enumerate(new_lines):
        if line.strip() == "[scripts]":
            new_lines.insert(i + 1, "flag_script_allow_write_absolute_path  = true\n")
            break

if not found_screenshot_dir:
    for i, line in enumerate(new_lines):
        if line.strip() == "[main]":
            new_lines.insert(i + 1, f"screenshot_dir                         = {FRAMES_DIR}\n")
            break

with open(CONFIG_DST, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("1. Prepared render_config.ini (720x1280 portrait mode)")

# 3. Create clean recording script
# Pacing: 900 frames at 30 fps = 30 seconds
# Time range: 2026-11-02 20:55:00 UTC to 2026-11-02 21:38:00 UTC (43 minutes = 2580 s)
script_content = f"""// Headless clean portrait recorder
core.clear("natural");
core.setTimeRate(0);

// Disable all text, labels, GUI and markers
core.setSelectedObjectInfo("None");
core.setGuiVisible(false);
SolarSystem.setFlagLabels(false);
SolarSystem.setFlagHints(false);
SolarSystem.setFlagOrbits(false);
SolarSystem.setFlagTrails(false);
SolarSystem.setFlagMarkers(false);
SolarSystem.setFlagMoonScale(false);
StarMgr.setFlagLabels(false);
ConstellationMgr.setFlagLines(false);
ConstellationMgr.setFlagLabels(false);
ConstellationMgr.setFlagBoundaries(false);
GridLinesMgr.setFlagEquatorGrid(false);
GridLinesMgr.setFlagAzimuthalGrid(false);
GridLinesMgr.setFlagHorizonLine(false);
LandscapeMgr.setFlagCardinalPoints(false);
LandscapeMgr.setFlagAtmosphere(true);
LandscapeMgr.setFlagFog(false);
LandscapeMgr.setFlagLandscape(false);
LabelMgr.deleteAllLabels();

// Observer location (Bengaluru)
LandscapeMgr.setFlagLandscapeSetsLocation(false);
core.setObserverLocation(77.5946, 12.9716, 920, 0, "Bengaluru", "Earth");
core.wait(0.5);

// Set start date and target
core.setDate("2026-11-02T20:55:00", "utc");
core.selectObjectByName("Jupiter", false);
core.moveToSelectedObject(0);
StelMovementMgr.setFlagTracking(true);
StelMovementMgr.zoomTo(1.15, 0);
core.wait(1.5);

var shotDir = "{FRAMES_DIR}";
var startJd = core.jdFromDateString("2026-11-02T20:55:00", "utc");
var endJd   = core.jdFromDateString("2026-11-02T21:38:00", "utc");
var totalFrames = 900;
var stepJd = (endJd - startJd) / (totalFrames - 1);

for (var i = 0; i < totalFrames; i++) {{
    core.setJDay(startJd + i * stepJd);
    core.wait(0.035);
    var pad = ("000" + i).slice(-4);
    core.screenshot("frame_" + pad, false, shotDir, true);
    core.wait(0.015);
}}

core.wait(0.5);
core.quitStellarium();
"""

with open(SCRIPT_DST, "w", encoding="utf-8") as f:
    f.write(script_content)

# Also save copy in repo
with open(os.path.join(CWD, "stellarium", "record_portrait_clean.ssc"), "w", encoding="utf-8") as f:
    f.write(script_content)

print("2. Created record_portrait_clean.ssc (900 frames, 30 fps, 30s video)")

# 4. Launch Stellarium
cmd = [
    r"C:\Program Files\Stellarium\stellarium.exe",
    "--config-file", CONFIG_DST,
    "--startup-script", "record_portrait_clean.ssc"
]

print("3. Launching Stellarium headless rendering...")
t_start = time.time()
p = subprocess.Popen(cmd)
ret = p.wait()
t_elapsed = time.time() - t_start
print(f"Stellarium exited with code {ret} in {t_elapsed:.1f}s")

# 5. Check frames
frames = [f for f in os.listdir("frames") if f.endswith(".png")]
print(f"4. Captured {len(frames)} frames in {FRAMES_DIR}")
if len(frames) == 0:
    print("Error: No frames were captured.")
    sys.exit(1)

# 6. Encode with ffmpeg
mp4_out = os.path.join(VIDEO_DIR, "jupiter-occultation-portrait.mp4")
print(f"5. Encoding video with ffmpeg -> {mp4_out}")

# Find ffmpeg
ffmpeg_cmd = [
    "ffmpeg", "-y",
    "-framerate", "30",
    "-i", os.path.join(FRAMES_DIR, "frame_%04d.png"),
    "-c:v", "libx264",
    "-pix_fmt", "yuv420p",
    "-crf", "18",
    mp4_out
]

res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
if res.returncode != 0:
    print("ffmpeg error:", res.stderr)
    sys.exit(1)

print(f"6. Successfully created MP4: {mp4_out} ({os.path.getsize(mp4_out)/1024/1024:.2f} MB)")

# Also create high quality GIF preview (15 fps, 360x640)
gif_out = os.path.join(VIDEO_DIR, "jupiter-occultation-portrait.gif")
print(f"7. Creating GIF preview -> {gif_out}")
gif_cmd = [
    "ffmpeg", "-y",
    "-i", mp4_out,
    "-vf", "fps=15,scale=360:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3",
    gif_out
]
res_gif = subprocess.run(gif_cmd, capture_output=True, text=True)
if res_gif.returncode == 0:
    print(f"Created GIF: {gif_out} ({os.path.getsize(gif_out)/1024/1024:.2f} MB)")
else:
    print("Warning: GIF creation failed:", res_gif.stderr)

print("Done!")
