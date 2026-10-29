"""Generate complete multi-segment video of the 2026 Jupiter occultation for Instagram / YouTube.

Segments:
1. Title Card: Intro with event name, date, and location.
2. Wide Sky Overview: Eastern sky view from Bengaluru showing Leo, Moon & Jupiter rising.
3. Telescopic View: 1.15 FOV showing waning crescent Moon gliding across Jupiter with live HUD (IST time + running Alt/Az).
4. Zoomed-in Close-up: High-magnification view (0.22 FOV) focused on Jupiter and Galilean moons,
   pausing at key contact times (Contact I, II, Mid, III, IV) with timeanddate.com-style callout banners.
"""

from datetime import datetime, timedelta
import os
import shutil
import subprocess
import sys
import time

import numpy as np
from skyfield.api import load, wgs84, utc

CWD = os.path.abspath(".")
VIDEO_DIR = os.path.join(CWD, "video")
os.makedirs(VIDEO_DIR, exist_ok=True)

CONFIG_SRC = os.path.expandvars(r"%APPDATA%\Stellarium\config.ini")
CONFIG_DST = os.path.join(CWD, "render_config.ini")

STELLARIUM_EXE = r"C:\Program Files\Stellarium\stellarium.exe"

# Load ephemeris
eph = load("de440s.bsp")
ts = load.timescale()
earth = eph["earth"]
moon = eph["moon"]
jupiter = eph["jupiter barycenter"]
bengaluru_loc = earth + wgs84.latlon(12.9716, 77.5946, elevation_m=920.0)


def prepare_config(frames_dir_abs):
    with open(CONFIG_SRC, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    in_video = in_scripts = in_main = False
    found_script_flag = found_screenshot_dir = False
    frames_path = frames_dir_abs.replace("\\", "/")

    for line in lines:
        s = line.strip()
        if s == "[video]":
            in_video = True
            in_scripts = in_main = False
        elif s == "[scripts]":
            in_scripts = True
            in_video = in_main = False
        elif s == "[main]":
            in_main = True
            in_video = in_scripts = False
        elif s.startswith("["):
            in_video = in_scripts = in_main = False

        if in_video and s.startswith("fullscreen"):
            new_lines.append("fullscreen                             = false\n")
        elif in_video and s.startswith("screen_w"):
            new_lines.append("screen_w                               = 720\n")
        elif in_video and s.startswith("screen_h"):
            new_lines.append("screen_h                               = 1280\n")
        elif in_video and s.startswith("screen_x"):
            new_lines.append("screen_x                               = 100\n")
        elif in_video and s.startswith("screen_y"):
            new_lines.append("screen_y                               = 50\n")
        elif in_scripts and s.startswith("flag_script_allow_write_absolute_path"):
            new_lines.append("flag_script_allow_write_absolute_path  = true\n")
            found_script_flag = True
        elif in_main and s.startswith("screenshot_dir"):
            new_lines.append(f"screenshot_dir                         = {frames_path}\n")
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
                new_lines.insert(i + 1, f"screenshot_dir                         = {frames_path}\n")
                break

    with open(CONFIG_DST, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def run_stellarium_script(script_name, script_content, frames_dir):
    os.makedirs(frames_dir, exist_ok=True)
    prepare_config(os.path.abspath(frames_dir))

    script_path = os.path.expandvars(rf"%APPDATA%\Stellarium\scripts\{script_name}")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_content)

    # Save copy to repo
    with open(os.path.join(CWD, "stellarium", script_name), "w", encoding="utf-8") as f:
        f.write(script_content)

    cmd = [STELLARIUM_EXE, "--config-file", CONFIG_DST, "--startup-script", script_name]
    p = subprocess.Popen(cmd)
    ret = p.wait()
    return ret


def get_ephem_for_timestamps(times_utc):
    obs_m = bengaluru_loc.at(times_utc).observe(moon).apparent()
    obs_j = bengaluru_loc.at(times_utc).observe(jupiter).apparent()
    alt_m, az_m, _ = obs_m.altaz()
    alt_j, az_j, _ = obs_j.altaz()
    return alt_j.degrees, az_j.degrees, alt_m.degrees, az_m.degrees


def format_ass_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:01d}:{m:02d}:{s:05.2f}"


def create_ass_subtitles(ass_path, frame_entries, fps=30):
    """frame_entries: list of dicts with:
    'time_sec', 'ist_str', 'alt_j', 'az_j', 'alt_m', 'az_m', 'callout_title', 'callout_desc'
    """
    header = """[Script Info]
Title: Jupiter Occultation Overlay
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 720
PlayResY: 1280

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: BottomHUD, Segoe UI, 32, &H00FFFFFF, &H000000FF, &H80000000, &HD00A0E18, 0, 0, 0, 0, 100, 100, 0, 0, 3, 3, 0, 2, 20, 20, 100, 1
Style: CalloutBox, Segoe UI, 40, &H00FFFFFF, &H000000FF, &H80000000, &HD00A0E18, 1, 0, 0, 0, 100, 100, 0, 0, 3, 3, 0, 8, 30, 30, 140, 1
Style: TitleCard, Segoe UI, 48, &H00FFFFFF, &H000000FF, &H80000000, &H00000000, 1, 0, 0, 0, 100, 100, 0, 0, 1, 2, 2, 5, 40, 40, 40, 1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    n = len(frame_entries)
    frame_dur = 1.0 / fps

    for i, e in enumerate(frame_entries):
        t_start = format_ass_time(i * frame_dur)
        t_end = format_ass_time((i + 1) * frame_dur)

        line1 = f"{{\\c&HEEEEEE&\\b1\\fs34}}Bengaluru, India   {{\\c&H7799CC&}}|   {{\\c&HFFD27F&}}IST: {e['ist_str']}"
        line2 = f"{{\\fs27\\c&HD0D0D0&\\b0}}Jupiter: Alt {e['alt_j']:.1f}°, Az {e['az_j']:.1f}°   {{\\c&H7799CC&}}•   {{\\c&HD0D0D0&}}Moon: Alt {e['alt_m']:.1f}°, Az {e['az_m']:.1f}°"
        hud_text = f"{line1}\\N{line2}"

        events.append(f"Dialogue: 0,{t_start},{t_end},BottomHUD,,0,0,0,,{hud_text}")

        if e.get("callout_title"):
            c_text = f"{{\\c&HFFD27F&\\fs40\\b1}}{e['callout_title']}\\N{{\\c&HFFFFFF&\\fs29\\b0}}{e['callout_desc']}"
            events.append(f"Dialogue: 1,{t_start},{t_end},CalloutBox,,0,0,0,,{c_text}")

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")


def build_hook_card(out_mp4, duration=2.5):
    """Renders hook_card.html with Playwright and creates a 2.5s MP4 with fade."""
    from playwright.sync_api import sync_playwright
    png_path = os.path.join(VIDEO_DIR, "hook_card.png")
    html_path = os.path.abspath("hook_card.html").replace("\\", "/")
    url = f"file:///{html_path}"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 720, "height": 1280})
        page.goto(url)
        page.wait_for_timeout(300)
        page.screenshot(path=png_path)
        browser.close()

    fade_out_st = max(0.5, duration - 0.5)
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", png_path,
        "-t", str(duration),
        "-vf", f"fade=t=in:st=0:d=0.4,fade=t=out:st={fade_out_st}:d=0.5",
        "-r", "30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        out_mp4
    ]
    subprocess.run(cmd, check=True)


def build_threejs_geometry_segment(out_mp4, duration=12.0, fps=30):
    """Renders the Three.js 3D alignment flight from threejs_geometry.html."""
    from playwright.sync_api import sync_playwright
    frames_dir = os.path.join(CWD, "frames_threejs")
    os.makedirs(frames_dir, exist_ok=True)
    total_frames = int(duration * fps)

    existing = [f for f in os.listdir(frames_dir) if f.endswith(".jpg")]
    if len(existing) != total_frames:
        if os.path.exists(frames_dir):
            shutil.rmtree(frames_dir)
        os.makedirs(frames_dir, exist_ok=True)
        print(f"Rendering {total_frames} Three.js frames via headless Chrome...")
        html_path = os.path.abspath("threejs_geometry.html").replace("\\", "/")
        url = f"file:///{html_path}"

        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 720, "height": 1280})
            page.goto(url)
            page.wait_for_timeout(400)

            for i in range(total_frames):
                prog = i / float(total_frames - 1)
                page.evaluate(f"window.renderFrameAt({prog:.4f})")
                frame_file = os.path.join(frames_dir, f"frame_{i:04d}.jpg")
                page.screenshot(path=frame_file, type="jpeg", quality=90)
                if i % 30 == 0:
                    print(f"  Three.js progress: {i}/{total_frames} frames ({prog*100:.0f}%)")

            browser.close()
    else:
        print(f"Using existing {len(existing)} Three.js frames...")

    fade_out_st = max(0.5, duration - 0.5)
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", os.path.join(frames_dir, "frame_%04d.jpg"),
        "-vf", f"fade=t=in:st=0:d=0.4,fade=t=out:st={fade_out_st}:d=0.5",
        "-r", "30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        out_mp4
    ]
    subprocess.run(cmd, check=True)


def build_summary_card(out_mp4, duration=4.5):
    """Renders summary_card.html with Playwright and creates a 4.5s MP4 with fade."""
    from playwright.sync_api import sync_playwright
    png_path = os.path.join(VIDEO_DIR, "summary_card.png")
    html_path = os.path.abspath("summary_card.html").replace("\\", "/")
    url = f"file:///{html_path}"

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 720, "height": 1280})
        page.goto(url)
        page.wait_for_timeout(300)
        page.screenshot(path=png_path)
        browser.close()

    fade_out_st = max(0.5, duration - 0.6)
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", png_path,
        "-t", str(duration),
        "-vf", f"fade=t=in:st=0:d=0.5,fade=t=out:st={fade_out_st}:d=0.6",
        "-r", "30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        out_mp4
    ]
    subprocess.run(cmd, check=True)


def build_wide_sky_segment(out_mp4):
    """Renders 120 frames of wide eastern sky in Leo from Bengaluru, then encodes with subtitle."""
    frames_dir = os.path.join(CWD, "frames_widesky")
    os.makedirs(frames_dir, exist_ok=True)
    existing_frames = [f for f in os.listdir(frames_dir) if f.endswith(".png")]

    if len(existing_frames) < 120:
        # 120 frames from 20:15 UTC (01:45 IST) to 21:45 UTC (03:15 IST)
        script_content = f"""// Wide sky overview from Bengaluru
core.clear("natural");
core.setTimeRate(0);
core.setSelectedObjectInfo("None");
core.setGuiVisible(false);

LandscapeMgr.setFlagLandscapeSetsLocation(false);
LandscapeMgr.setCurrentLandscapeID("zero");
LandscapeMgr.setFlagLandscape(true);
core.setObserverLocation(77.5946, 12.9716, 920, 0, "Bengaluru", "Earth");
core.wait(0.5);

LandscapeMgr.setFlagAtmosphere(true);
LandscapeMgr.setFlagFog(false);
LandscapeMgr.setFlagCardinalPoints(true);
ConstellationMgr.setFlagLines(true);
ConstellationMgr.setFlagLabels(true);
ConstellationMgr.setFlagBoundaries(false);
SolarSystem.setFlagPlanets(true);
SolarSystem.setFlagLabels(true);
SolarSystem.setFlagHints(true);
SolarSystem.setFlagMoonScale(true);
SolarSystem.setMoonScale(2.5); // Slightly larger so Moon is prominent in wide shot
GridLinesMgr.setFlagHorizonLine(true);
LabelMgr.deleteAllLabels();

core.setDate("2026-11-02T20:15:00", "utc");
// Look East (Az 85, Alt 25)
core.moveToAltAzi(25, 85, 0);
StelMovementMgr.zoomTo(65, 0);
core.wait(2.0);

var shotDir = "{frames_dir.replace('\\', '/')}";
var startJd = core.jdFromDateString("2026-11-02T20:15:00", "utc");
var endJd   = core.jdFromDateString("2026-11-02T21:45:00", "utc");
var totalFrames = 120;
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
        print("Rendering Wide Sky segment in Stellarium (120 frames)...")
        run_stellarium_script("record_widesky.ssc", script_content, frames_dir)
    else:
        print("Using existing 120 frames for Wide Sky segment...")

    # Compute ephemeris for wide sky frames
    t_start = datetime(2026, 11, 2, 20, 15, 0, tzinfo=utc)
    t_end = datetime(2026, 11, 2, 21, 45, 0, tzinfo=utc)
    dt = (t_end - t_start) / 119
    times_utc = ts.utc([t_start + i * dt for i in range(120)])
    alt_j, az_j, alt_m, az_m = get_ephem_for_timestamps(times_utc)

    frame_entries = []
    for i in range(120):
        t_ist = (t_start + i * dt) + timedelta(hours=5, minutes=30)
        e = {
            "ist_str": t_ist.strftime("%H:%M:%S"),
            "alt_j": alt_j[i],
            "az_j": az_j[i],
            "alt_m": alt_m[i],
            "az_m": az_m[i],
            "callout_title": "WIDE-FIELD VIEW  |  EASTERN SKY (LEO)" if i < 36 else None,
            "callout_desc": "Moon & Jupiter rising before dawn" if i < 36 else None,
        }
        frame_entries.append(e)

    ass_path = os.path.join(CWD, "widesky.ass")
    create_ass_subtitles(ass_path, frame_entries, fps=24)

    # Compile with ffmpeg
    ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", "24",
        "-i", os.path.join(frames_dir, "frame_%04d.png"),
        "-vf", f"ass='{ass_escaped}',fade=t=in:st=0:d=0.5",
        "-r", "30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        out_mp4
    ]
    subprocess.run(cmd, check=True)


def build_telescopic_segment(out_mp4):
    """Encodes the 900 telescopic frames with running HUD."""
    frames_dir = os.path.join(CWD, "frames_telescopic")
    # 900 frames covering 20:55:00 to 21:38:00 UTC (43 mins = 2580 s)
    t_start = datetime(2026, 11, 2, 20, 55, 0, tzinfo=utc)
    t_end = datetime(2026, 11, 2, 21, 38, 0, tzinfo=utc)
    dt = (t_end - t_start) / 899

    # Generate ephemeris for all 900 frames
    times_utc = ts.utc([t_start + i * dt for i in range(900)])
    alt_j, az_j, alt_m, az_m = get_ephem_for_timestamps(times_utc)

    frame_entries = []
    for i in range(900):
        t_ist = (t_start + i * dt) + timedelta(hours=5, minutes=30)
        e = {
            "ist_str": t_ist.strftime("%H:%M:%S"),
            "alt_j": alt_j[i],
            "az_j": az_j[i],
            "alt_m": alt_m[i],
            "az_m": az_m[i],
            "callout_title": "TELESCOPIC VIEW (FOV 1.15°)" if i < 60 else None,
            "callout_desc": "Continuous transit across Jupiter" if i < 60 else None,
        }
        frame_entries.append(e)

    ass_path = os.path.join(CWD, "telescopic.ass")
    # Play 900 frames at 60 fps -> 15.0 seconds
    create_ass_subtitles(ass_path, frame_entries, fps=60)

    ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", "60",
        "-i", os.path.join(frames_dir, "frame_%04d.png"),
        "-vf", f"ass='{ass_escaped}',fade=t=in:st=0:d=0.5",
        "-r", "30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        out_mp4
    ]
    subprocess.run(cmd, check=True)


def build_zoomed_contacts_segment(out_mp4):
    """Renders zoomed-in view of Jupiter (FOV 0.20), pausing at contacts with callouts."""
    frames_dir = os.path.join(CWD, "frames_zoomed_raw")
    os.makedirs(frames_dir, exist_ok=True)
    existing_raw = [f for f in os.listdir(frames_dir) if f.endswith(".png")]

    if len(existing_raw) < 240:
        # 240 raw frames covering 20:56:00 to 21:36:00 UTC (40 mins = 2400 s)
        script_content = f"""// Zoomed close-up on Jupiter
core.clear("natural");
core.setTimeRate(0);
core.setSelectedObjectInfo("None");
core.setGuiVisible(false);

LandscapeMgr.setFlagLandscapeSetsLocation(false);
core.setObserverLocation(77.5946, 12.9716, 920, 0, "Bengaluru", "Earth");
core.wait(0.5);

LandscapeMgr.setFlagAtmosphere(true);
LandscapeMgr.setFlagFog(false);
LandscapeMgr.setFlagLandscape(false);
LandscapeMgr.setFlagCardinalPoints(false);
SolarSystem.setFlagPlanets(true);
SolarSystem.setFlagLabels(false);
SolarSystem.setFlagHints(false);
SolarSystem.setFlagOrbits(false);
SolarSystem.setFlagTrails(false);
SolarSystem.setFlagMarkers(false);
SolarSystem.setFlagMoonScale(false);
StarMgr.setFlagLabels(false);
ConstellationMgr.setFlagLines(false);
ConstellationMgr.setFlagLabels(false);
GridLinesMgr.setFlagEquatorGrid(false);
GridLinesMgr.setFlagAzimuthalGrid(false);
GridLinesMgr.setFlagHorizonLine(false);
LabelMgr.deleteAllLabels();

core.setDate("2026-11-02T20:56:00", "utc");
core.selectObjectByName("Jupiter", false);
core.moveToSelectedObject(0);
StelMovementMgr.setFlagTracking(true);
StelMovementMgr.zoomTo(0.20, 0); // High magnification
core.wait(2.0);

var shotDir = "{frames_dir.replace('\\', '/')}";
var startJd = core.jdFromDateString("2026-11-02T20:56:00", "utc");
var endJd   = core.jdFromDateString("2026-11-02T21:36:00", "utc");
var totalFrames = 240;
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
        print("Rendering Zoomed Close-up segment in Stellarium (240 frames)...")
        run_stellarium_script("record_zoomed.ssc", script_content, frames_dir)
    else:
        print("Using existing 240 frames for Zoomed Close-up segment...")

    # Now create expanded frames directory with contact pauses
    frames_expanded_dir = os.path.join(CWD, "frames_zoomed_expanded")
    if os.path.exists(frames_expanded_dir):
        shutil.rmtree(frames_expanded_dir)
    os.makedirs(frames_expanded_dir, exist_ok=True)

    t_start = datetime(2026, 11, 2, 20, 56, 0, tzinfo=utc)
    t_end = datetime(2026, 11, 2, 21, 36, 0, tzinfo=utc)
    total_sec = 2400.0

    # Key milestones in seconds from t_start:
    # C1: 20:58:56 -> 176 s (frame ~ 176/2400 * 239 = 17.5 -> frame 18)
    # C2: 21:01:31 -> 331 s (frame ~ 331/2400 * 239 = 33.0 -> frame 33)
    # Mid: 21:16:13 -> 1213 s (frame ~ 1213/2400 * 239 = 120.8 -> frame 121)
    # C3: 21:31:27 -> 2127 s (frame ~ 2127/2400 * 239 = 211.9 -> frame 212)
    # C4: 21:34:12 -> 2292 s (frame ~ 2292/2400 * 239 = 228.2 -> frame 228)
    milestones = {
        18: ("CONTACT I: INGRESS BEGINS", "02:28:56 IST  |  First touch at bright limb"),
        33: ("CONTACT II: FULL INGRESS", "02:31:31 IST  |  Jupiter fully disappears"),
        121: ("MID-OCCULTATION: MAXIMUM DEPTH", "02:46:13 IST  |  Separation: 14.0 arcmin"),
        212: ("CONTACT III: EGRESS BEGINS", "03:01:27 IST  |  Emerges from dark limb"),
        228: ("CONTACT IV: FULL EGRESS", "03:04:12 IST  |  Occultation ends"),
    }

    PAUSE_FRAMES = 36  # 1.5 seconds at 24 fps

    expanded_entries = []
    out_idx = 0

    # Pre-calculate ephemeris for raw 240 frames
    times_utc = ts.utc([t_start + timedelta(seconds=i * (total_sec / 239.0)) for i in range(240)])
    alt_j, az_j, alt_m, az_m = get_ephem_for_timestamps(times_utc)

    for i in range(240):
        src_png = os.path.join(frames_dir, f"frame_{i:04d}.png")
        t_ist = (t_start + timedelta(seconds=i * (total_sec / 239.0))) + timedelta(hours=5, minutes=30)

        # Normal frame
        dst_png = os.path.join(frames_expanded_dir, f"frame_{out_idx:04d}.png")
        shutil.copyfile(src_png, dst_png)

        callout = milestones.get(i)
        entry = {
            "ist_str": t_ist.strftime("%H:%M:%S"),
            "alt_j": alt_j[i],
            "az_j": az_j[i],
            "alt_m": alt_m[i],
            "az_m": az_m[i],
            "callout_title": callout[0] if callout else ("ZOOMED CLOSE-UP (FOV 0.20°)" if i < 20 else None),
            "callout_desc": callout[1] if callout else ("High-exposure Jovian disk & moons" if i < 20 else None),
        }
        expanded_entries.append(entry)
        out_idx += 1

        # If milestone, repeat frame for pause
        if callout:
            for _ in range(PAUSE_FRAMES):
                dst_pause = os.path.join(frames_expanded_dir, f"frame_{out_idx:04d}.png")
                shutil.copyfile(src_png, dst_pause)
                expanded_entries.append(entry)
                out_idx += 1

    ass_path = os.path.join(CWD, "zoomed_contacts.ass")
    create_ass_subtitles(ass_path, expanded_entries, fps=24)

    ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", "24",
        "-i", os.path.join(frames_expanded_dir, "frame_%04d.png"),
        "-vf", f"ass='{ass_escaped}',fade=t=in:st=0:d=0.5,fade=t=out:st=16.0:d=0.8",
        "-r", "30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        out_mp4
    ]
    subprocess.run(cmd, check=True)


def main():
    print("================================================================================")
    print(" BUILDING COMPLETE MULTI-SEGMENT OCCULTATION VIDEO")
    print("================================================================================")

    seg1_mp4 = os.path.join(VIDEO_DIR, "seg1_hook.mp4")
    seg2_mp4 = os.path.join(VIDEO_DIR, "seg2_threejs_geometry.mp4")
    seg3_mp4 = os.path.join(VIDEO_DIR, "seg3_widesky.mp4")
    seg4_mp4 = os.path.join(VIDEO_DIR, "seg4_telescopic.mp4")
    seg5_mp4 = os.path.join(VIDEO_DIR, "seg5_zoomed_contacts.mp4")
    seg6_mp4 = os.path.join(VIDEO_DIR, "seg6_summary.mp4")

    print("\nStep 1: Building Opening Hook Teaser Card...")
    build_hook_card(seg1_mp4, duration=2.5)

    print("\nStep 2: Building Cinematic 3D Three.js Alignment Flight...")
    build_threejs_geometry_segment(seg2_mp4, duration=12.0, fps=30)

    print("\nStep 3: Building Wide Sky Overview Segment...")
    build_wide_sky_segment(seg3_mp4)

    print("\nStep 4: Building Telescopic Segment with Running HUD...")
    build_telescopic_segment(seg4_mp4)

    print("\nStep 5: Building Zoomed Close-up Segment with Contact Pauses...")
    build_zoomed_contacts_segment(seg5_mp4)

    print("\nStep 6: Building Bengaluru Contact Timings Summary Card...")
    build_summary_card(seg6_mp4, duration=4.5)

    # Step 7: Concatenate all 6 segments
    print("\nStep 7: Concatenating all 6 segments into master video...")
    concat_list = os.path.join(CWD, "concat_list.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        f.write(f"file '{seg1_mp4.replace('\\', '/')}'\n")
        f.write(f"file '{seg2_mp4.replace('\\', '/')}'\n")
        f.write(f"file '{seg3_mp4.replace('\\', '/')}'\n")
        f.write(f"file '{seg4_mp4.replace('\\', '/')}'\n")
        f.write(f"file '{seg5_mp4.replace('\\', '/')}'\n")
        f.write(f"file '{seg6_mp4.replace('\\', '/')}'\n")

    master_mp4 = os.path.join(VIDEO_DIR, "jupiter-occultation-bengaluru-complete.mp4")
    concat_cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_list,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        master_mp4
    ]
    subprocess.run(concat_cmd, check=True)
    print(f"\n Master video successfully generated: {master_mp4} ({os.path.getsize(master_mp4)/1024/1024:.2f} MB)")

    # Also update jupiter-occultation-portrait.mp4 to be the complete video
    shutil.copyfile(master_mp4, os.path.join(VIDEO_DIR, "jupiter-occultation-portrait.mp4"))

    # Generate high quality GIF preview of the complete video
    print("\nStep 8: Generating animated GIF preview...")
    master_gif = os.path.join(VIDEO_DIR, "jupiter-occultation-portrait.gif")
    gif_cmd = [
        "ffmpeg", "-y",
        "-i", master_mp4,
        "-vf", "fps=10,scale=360:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3",
        master_gif
    ]
    subprocess.run(gif_cmd, check=True)
    print(f" GIF preview generated: {master_gif} ({os.path.getsize(master_gif)/1024/1024:.2f} MB)")
    print("\nALL STEPS COMPLETED!")


if __name__ == "__main__":
    main()
