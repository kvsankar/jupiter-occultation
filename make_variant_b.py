"""Pipeline to build Variant B of the Jupiter Occultation video.

Variant B Features:
1. Kokoro-82M TTS voice narration (af_heart voice, as used in Prashna).
2. Dynamic Instagram-style subtitles at bottom for muted viewing.
3. Technical HUD (IST time & Alt/Az) re-aligned to the TOP to leave the bottom third clear.
4. Outro card with Bangalore Astronomical Society (BAS) logo, QR code, and https://bas.org.in.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone

import numpy as np
import soundfile as sf
from skyfield.api import Topos, load

# Global paths
CWD = os.path.dirname(os.path.abspath(__file__))
VIDEO_DIR = os.path.join(CWD, "video")
AUDIO_DIR = os.path.join(CWD, "audio")
ASSETS_DIR = os.path.join(CWD, "assets")
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

# Skyfield Ephemeris setup
ts = load.timescale()
eph = load("de440s.bsp")
earth = eph["earth"]
moon = eph["moon"]
jupiter = eph["jupiter barycenter"]
bengaluru_loc = earth + Topos(latitude_degrees=12.9716, longitude_degrees=77.5946, elevation_m=920.0)
utc = timezone.utc


def format_ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:01d}:{m:02d}:{s:05.2f}"


def get_ephem_for_timestamps(times_utc):
    obs_m = bengaluru_loc.at(times_utc).observe(moon).apparent()
    obs_j = bengaluru_loc.at(times_utc).observe(jupiter).apparent()
    alt_m, az_m, _ = obs_m.altaz()
    alt_j, az_j, _ = obs_j.altaz()
    return alt_j.degrees, az_j.degrees, alt_m.degrees, az_m.degrees


# Scene narration texts and phrase breakdowns for Instagram-style captioning
CAPTIONS = {
    "seg1": [
        (0.0, 1.4, "ON NOVEMBER 3RD..."),
        (1.4, 3.2, "JUPITER WILL VANISH BEHIND THE MOON")
    ],
    "seg2": [
        (0.0, 2.4, "Seen from Bengaluru, India..."),
        (2.4, 4.4, "An observer looks East before dawn"),
        (4.4, 7.0, "As we soar into space..."),
        (7.0, 9.6, "A laser sightline connects Earth to Jupiter"),
        (9.6, 12.6, "The Moon sweeps in, blocking the giant planet!")
    ],
    "seg3": [
        (0.0, 2.2, "In the constellation Leo..."),
        (2.2, 4.8, "Watch both bodies rise above the eastern horizon")
    ],
    "seg4": [
        (0.0, 2.8, "Through a telescope..."),
        (2.8, 5.8, "The waning crescent Moon steadily overtakes Jupiter"),
        (5.8, 10.0, "Hiding the planet and its moons for 35 minutes!")
    ],
    "seg5": [
        (0.0, 2.6, "At 2:28 AM, ingress begins..."),
        (2.6, 5.8, "By 2:31 AM, Jupiter is completely occulted"),
        (5.8, 9.2, "Mid-occultation arrives at 2:46 AM"),
        (9.2, 13.5, "At 3:01 AM, Jupiter dramatically re-emerges..."),
        (13.5, 17.5, "With full egress completed by 3:04 AM!")
    ],
    "seg6": [
        (0.0, 3.2, "Join the Bangalore Astronomical Society..."),
        (3.2, 5.5, "To observe this rare cosmic event!"),
        (5.5, 9.2, "Visit bas.org.in or scan the QR code to connect")
    ]
}


def build_audio_tracks():
    """Generates speech WAV files using Kokoro-82M ONNX model (as in Prashna)."""
    os.environ["ORT_DISABLE_TELEMETRY"] = "1"
    import onnxruntime as rt
    from kokoro_onnx.tokenizer import Tokenizer
    from kokoro_onnx.trim import trim as trim_audio

    model_path = os.path.join(CWD, "models", "onnx", "model.onnx")
    voice_path = os.path.join(CWD, "models", "voices", "af_heart.bin")

    if not os.path.exists(model_path) or not os.path.exists(voice_path):
        raise FileNotFoundError(f"Kokoro model or voice not found at {model_path}")

    rt.disable_telemetry_events()
    sess = rt.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    inputs = {i.name: i.type for i in sess.get_inputs()}
    tok = Tokenizer()
    speed_type = np.int32 if "int" in inputs.get("speed", "") else np.float32
    style_table = np.fromfile(voice_path, dtype=np.float32).reshape(-1, 1, 256)

    lines = [
        ("seg1", "On November third, Jupiter will vanish behind the Moon."),
        ("seg2", "Seen from Bengaluru, an observer looks east before dawn. As we rise into space, a straight sightline connects Earth to Jupiter. The Moon sweeps into alignment, blocking the giant planet from view."),
        ("seg3", "In the constellation Leo, watch both bodies rise above the eastern horizon."),
        ("seg4", "Through a telescope, the waning crescent Moon steadily overtakes Jupiter, hiding the planet and its four Galilean moons for thirty-five minutes."),
        ("seg5", "At 2:28 AM, ingress begins. By 2:31 AM, Jupiter is completely hidden. After maximum depth at 2:46 AM, Jupiter dramatically re-emerges at 3:01 AM, ending full egress by 3:04 AM."),
        ("seg6", "Join the Bangalore Astronomical Society to observe this rare event. Visit bas dot org dot in, or scan the QR code to connect with us.")
    ]

    for name, text in lines:
        wav_file = os.path.join(AUDIO_DIR, f"{name}.wav")
        if not os.path.exists(wav_file):
            ph = tok.phonemize(text, "en-us")
            ph = ph.replace("bˈæŋɡəlˌɔːɹ", "bˈɛŋɡəlˌuːɹuː")  # Bengaluru
            tokens = tok.tokenize(ph)
            feeds = {
                "input_ids": np.array([[0, *tokens, 0]], dtype=np.int64),
                "style": style_table[len(tokens)],
                "speed": np.array([1.0], dtype=speed_type),
            }
            audio = sess.run(None, feeds)[0].reshape(-1)
            audio, _ = trim_audio(audio)
            sf.write(wav_file, audio, 24000, subtype="PCM_16")
            print(f"  Generated speech {name}: {len(audio)/24000:.2f}s")


def mux_audio_video(in_video, in_audio, out_muxed, duration=None):
    """Muxes video and audio tracks with ffmpeg, converting audio to AAC 192k."""
    cmd = [
        "ffmpeg", "-y",
        "-i", in_video,
        "-i", in_audio,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
    ]
    if duration:
        cmd.extend(["-t", str(duration)])
    cmd.append(out_muxed)
    subprocess.run(cmd, check=True)


# ==============================================================================
# SEGMENT BUILDERS FOR VARIANT B
# ==============================================================================

def build_variant_b_seg1(out_mp4, duration=3.2):
    """Hook card with Instagram-style bottom caption."""
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

    # Generate ASS with Instagram caption at bottom
    ass_path = os.path.join(CWD, "seg1_b.ass")
    header = """[Script Info]
Title: Variant B Hook Captions
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 720
PlayResY: 1280

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: InstaCaption, Segoe UI, 36, &H00FFFFFF, &H000000FF, &H80000000, &HD0060A14, 1, 0, 0, 0, 100, 100, 0, 0, 3, 4, 0, 2, 40, 40, 100, 1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for t_s, t_e, text in CAPTIONS["seg1"]:
        events.append(f"Dialogue: 0,{format_ass_time(t_s)},{format_ass_time(t_e)},InstaCaption,,0,0,0,,{{\\c&HFFD27F&}}{text}")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")

    ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")
    raw_video = os.path.join(VIDEO_DIR, "raw_seg1_b.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", png_path,
        "-t", str(duration),
        "-vf", f"ass='{ass_escaped}',fade=t=in:st=0:d=0.3,fade=t=out:st={duration-0.4}:d=0.4",
        "-r", "30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        raw_video
    ]
    subprocess.run(cmd, check=True)

    # Mux audio
    mux_audio_video(raw_video, os.path.join(AUDIO_DIR, "seg1.wav"), out_mp4, duration=duration)


def build_variant_b_seg2(out_mp4, duration=12.6, fps=30):
    """Three.js flight with Instagram-style captions at bottom."""
    frames_dir = os.path.join(CWD, "frames_threejs")
    total_frames = int(duration * fps)

    # Re-render frames if count differs
    existing = [f for f in os.listdir(frames_dir) if f.endswith(".jpg")] if os.path.exists(frames_dir) else []
    if len(existing) != total_frames:
        if os.path.exists(frames_dir):
            shutil.rmtree(frames_dir)
        os.makedirs(frames_dir, exist_ok=True)
        print(f"Rendering {total_frames} Three.js frames for Variant B...")
        from playwright.sync_api import sync_playwright

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
                if i % 45 == 0:
                    print(f"  Three.js progress: {i}/{total_frames} frames ({prog*100:.0f}%)")

            browser.close()

    # Subtitles for Three.js
    ass_path = os.path.join(CWD, "seg2_b.ass")
    header = """[Script Info]
Title: Variant B Three.js Captions
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 720
PlayResY: 1280

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: InstaCaption, Segoe UI, 34, &H00FFFFFF, &H000000FF, &H80000000, &HD0060A14, 1, 0, 0, 0, 100, 100, 0, 0, 3, 4, 0, 2, 40, 40, 95, 1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for t_s, t_e, text in CAPTIONS["seg2"]:
        events.append(f"Dialogue: 0,{format_ass_time(t_s)},{format_ass_time(t_e)},InstaCaption,,0,0,0,,{{\\c&HFFD27F&}}{text}")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")

    ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")
    raw_video = os.path.join(VIDEO_DIR, "raw_seg2_b.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", os.path.join(frames_dir, "frame_%04d.jpg"),
        "-vf", f"ass='{ass_escaped}',fade=t=in:st=0:d=0.4,fade=t=out:st={duration-0.5}:d=0.5",
        "-r", "30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        raw_video
    ]
    subprocess.run(cmd, check=True)

    mux_audio_video(raw_video, os.path.join(AUDIO_DIR, "seg2.wav"), out_mp4, duration=duration)


def build_variant_b_seg3(out_mp4, duration=4.8):
    """Wide sky view with TOP HUD and Instagram captions at bottom."""
    frames_dir = os.path.join(CWD, "frames_widesky")

    # Ephemeris for 120 wide sky frames
    t_start = datetime(2026, 11, 2, 20, 15, 0, tzinfo=utc)
    t_end = datetime(2026, 11, 2, 21, 45, 0, tzinfo=utc)
    dt = (t_end - t_start) / 119
    times_utc = ts.utc([t_start + i * dt for i in range(120)])
    alt_j, az_j, alt_m, az_m = get_ephem_for_timestamps(times_utc)

    fps = 25  # 120 frames / 25 fps = 4.8s
    frame_dur = 1.0 / fps

    ass_path = os.path.join(CWD, "seg3_b.ass")
    header = """[Script Info]
Title: Variant B Wide Sky Overlay
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 720
PlayResY: 1280

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TopHUD, Segoe UI, 26, &H00FFFFFF, &H000000FF, &H80000000, &HD00A0E18, 0, 0, 0, 0, 100, 100, 0, 0, 3, 3, 0, 8, 30, 30, 100, 1
Style: InstaCaption, Segoe UI, 34, &H00FFFFFF, &H000000FF, &H80000000, &HD0060A14, 1, 0, 0, 0, 100, 100, 0, 0, 3, 4, 0, 2, 40, 40, 100, 1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for i in range(120):
        t_s = format_ass_time(i * frame_dur)
        t_e = format_ass_time((i + 1) * frame_dur)
        t_ist = (t_start + i * dt) + timedelta(hours=5, minutes=30)
        ist_str = t_ist.strftime("%H:%M:%S")

        line1 = f"{{\\c&HEEEEEE&\\b1\\fs30}}Bengaluru, India   {{\\c&H7799CC&}}|   {{\\c&HFFD27F&}}IST: {ist_str}"
        line2 = f"{{\\fs24\\c&HD0D0D0&\\b0}}Jupiter: Alt {alt_j[i]:.1f}°, Az {az_j[i]:.1f}°   {{\\c&H7799CC&}}•   {{\\c&HD0D0D0&}}Moon: Alt {alt_m[i]:.1f}°, Az {az_m[i]:.1f}°"
        hud = f"{line1}\\N{line2}"
        events.append(f"Dialogue: 0,{t_s},{t_e},TopHUD,,0,0,0,,{hud}")

    for t_s, t_e, text in CAPTIONS["seg3"]:
        events.append(f"Dialogue: 1,{format_ass_time(t_s)},{format_ass_time(t_e)},InstaCaption,,0,0,0,,{{\\c&HFFD27F&}}{text}")

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")

    ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")
    raw_video = os.path.join(VIDEO_DIR, "raw_seg3_b.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", "25",
        "-i", os.path.join(frames_dir, "frame_%04d.png"),
        "-vf", f"ass='{ass_escaped}',fade=t=in:st=0:d=0.3,fade=t=out:st={duration-0.4}:d=0.4",
        "-r", "30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        raw_video
    ]
    subprocess.run(cmd, check=True)

    mux_audio_video(raw_video, os.path.join(AUDIO_DIR, "seg3.wav"), out_mp4, duration=duration)


def build_variant_b_seg4(out_mp4, duration=10.0):
    """Telescopic view with TOP HUD and Instagram captions at bottom."""
    frames_dir = os.path.join(CWD, "frames_telescopic")
    # Use 300 frames (sampled from 900) for a crisp 10.0s sequence at 30 fps
    step = 900 / 300.0
    t_start = datetime(2026, 11, 2, 20, 55, 0, tzinfo=utc)
    t_end = datetime(2026, 11, 2, 21, 38, 0, tzinfo=utc)
    dt_total = t_end - t_start

    fps = 30
    frame_dur = 1.0 / fps

    times_list = [t_start + (i * step / 899.0) * dt_total for i in range(300)]
    times_utc = ts.utc(times_list)
    alt_j, az_j, alt_m, az_m = get_ephem_for_timestamps(times_utc)

    # Subtitles
    ass_path = os.path.join(CWD, "seg4_b.ass")
    header = """[Script Info]
Title: Variant B Telescopic Transit
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 720
PlayResY: 1280

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TopHUD, Segoe UI, 26, &H00FFFFFF, &H000000FF, &H80000000, &HD00A0E18, 0, 0, 0, 0, 100, 100, 0, 0, 3, 3, 0, 8, 30, 30, 100, 1
Style: InstaCaption, Segoe UI, 34, &H00FFFFFF, &H000000FF, &H80000000, &HD0060A14, 1, 0, 0, 0, 100, 100, 0, 0, 3, 4, 0, 2, 40, 40, 100, 1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for i in range(300):
        t_s = format_ass_time(i * frame_dur)
        t_e = format_ass_time((i + 1) * frame_dur)
        t_ist = times_list[i] + timedelta(hours=5, minutes=30)
        ist_str = t_ist.strftime("%H:%M:%S")

        line1 = f"{{\\c&HEEEEEE&\\b1\\fs30}}Bengaluru, India   {{\\c&H7799CC&}}|   {{\\c&HFFD27F&}}IST: {ist_str}"
        line2 = f"{{\\fs24\\c&HD0D0D0&\\b0}}Jupiter: Alt {alt_j[i]:.1f}°, Az {az_j[i]:.1f}°   {{\\c&H7799CC&}}•   {{\\c&HD0D0D0&}}Moon: Alt {alt_m[i]:.1f}°, Az {az_m[i]:.1f}°"
        hud = f"{line1}\\N{line2}"
        events.append(f"Dialogue: 0,{t_s},{t_e},TopHUD,,0,0,0,,{hud}")

    for t_s, t_e, text in CAPTIONS["seg4"]:
        events.append(f"Dialogue: 1,{format_ass_time(t_s)},{format_ass_time(t_e)},InstaCaption,,0,0,0,,{{\\c&HFFD27F&}}{text}")

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")

    # Make temporary directory of 300 frames
    seg4_frames_dir = os.path.join(CWD, "frames_seg4_b")
    if os.path.exists(seg4_frames_dir):
        shutil.rmtree(seg4_frames_dir)
    os.makedirs(seg4_frames_dir, exist_ok=True)
    for i in range(300):
        src_idx = int(round(i * step))
        src_idx = min(src_idx, 899)
        shutil.copyfile(
            os.path.join(frames_dir, f"frame_{src_idx:04d}.png"),
            os.path.join(seg4_frames_dir, f"frame_{i:04d}.png")
        )

    ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")
    raw_video = os.path.join(VIDEO_DIR, "raw_seg4_b.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", "30",
        "-i", os.path.join(seg4_frames_dir, "frame_%04d.png"),
        "-vf", f"ass='{ass_escaped}',fade=t=in:st=0:d=0.3,fade=t=out:st={duration-0.4}:d=0.4",
        "-r", "30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        raw_video
    ]
    subprocess.run(cmd, check=True)

    mux_audio_video(raw_video, os.path.join(AUDIO_DIR, "seg4.wav"), out_mp4, duration=duration)


def build_variant_b_seg5(out_mp4, duration=17.5):
    """Zoomed close-up with TOP contact callouts and Instagram captions at bottom."""
    frames_expanded_dir = os.path.join(CWD, "frames_zoomed_expanded")
    total_frames = len([f for f in os.listdir(frames_expanded_dir) if f.endswith(".png")])
    fps = 24
    frame_dur = 1.0 / fps

    ass_path = os.path.join(CWD, "seg5_b.ass")
    header = """[Script Info]
Title: Variant B Zoomed Contacts
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 720
PlayResY: 1280

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CalloutTop, Segoe UI, 34, &H00FFFFFF, &H000000FF, &H80000000, &HD00A0E18, 1, 0, 0, 0, 100, 100, 0, 0, 3, 3, 0, 8, 30, 30, 120, 1
Style: InstaCaption, Segoe UI, 34, &H00FFFFFF, &H000000FF, &H80000000, &HD0060A14, 1, 0, 0, 0, 100, 100, 0, 0, 3, 4, 0, 2, 40, 40, 100, 1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    # Milestones timings in seconds
    milestones_timing = [
        (0.0, 1.8, "ZOOMED CLOSE-UP (FOV 0.20°)", "High-exposure Jovian disk & Galilean moons"),
        (1.8, 3.8, "CONTACT I: INGRESS BEGINS", "02:28:56 IST  |  First touch at bright limb"),
        (3.8, 6.2, "CONTACT II: FULL INGRESS", "02:31:31 IST  |  Jupiter fully disappears"),
        (7.5, 10.5, "MID-OCCULTATION: MAXIMUM DEPTH", "02:46:13 IST  |  Separation: 14.0 arcmin"),
        (12.5, 15.0, "CONTACT III: EGRESS BEGINS", "03:01:27 IST  |  Emerges from dark limb"),
        (15.0, 17.5, "CONTACT IV: FULL EGRESS", "03:04:12 IST  |  Occultation ends"),
    ]
    events = []
    for t_s, t_e, title, desc in milestones_timing:
        txt = f"{{\\c&HFFD27F&\\fs36\\b1}}{title}\\N{{\\c&HFFFFFF&\\fs26\\b0}}{desc}"
        events.append(f"Dialogue: 0,{format_ass_time(t_s)},{format_ass_time(t_e)},CalloutTop,,0,0,0,,{txt}")

    for t_s, t_e, text in CAPTIONS["seg5"]:
        events.append(f"Dialogue: 1,{format_ass_time(t_s)},{format_ass_time(t_e)},InstaCaption,,0,0,0,,{{\\c&HFFD27F&}}{text}")

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")

    ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")
    raw_video = os.path.join(VIDEO_DIR, "raw_seg5_b.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", "24",
        "-i", os.path.join(frames_expanded_dir, "frame_%04d.png"),
        "-vf", f"ass='{ass_escaped}',fade=t=in:st=0:d=0.3,fade=t=out:st={duration-0.5}:d=0.5",
        "-r", "30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        raw_video
    ]
    subprocess.run(cmd, check=True)

    mux_audio_video(raw_video, os.path.join(AUDIO_DIR, "seg5.wav"), out_mp4, duration=duration)


def build_variant_b_seg6(out_mp4, duration=9.2):
    """BAS Outro card with logo, QR code, and Instagram bottom captions."""
    png_path = os.path.join(VIDEO_DIR, "summary_card_variant_b.png")

    ass_path = os.path.join(CWD, "seg6_b.ass")
    header = """[Script Info]
Title: Variant B Outro Captions
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 720
PlayResY: 1280

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: InstaCaption, Segoe UI, 34, &H00FFFFFF, &H000000FF, &H80000000, &HD0060A14, 1, 0, 0, 0, 100, 100, 0, 0, 3, 4, 0, 2, 40, 40, 95, 1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for t_s, t_e, text in CAPTIONS["seg6"]:
        events.append(f"Dialogue: 0,{format_ass_time(t_s)},{format_ass_time(t_e)},InstaCaption,,0,0,0,,{{\\c&HFFD27F&}}{text}")

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")

    ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")
    raw_video = os.path.join(VIDEO_DIR, "raw_seg6_b.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", png_path,
        "-t", str(duration),
        "-vf", f"ass='{ass_escaped}',fade=t=in:st=0:d=0.4,fade=t=out:st={duration-0.6}:d=0.6",
        "-r", "30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        raw_video
    ]
    subprocess.run(cmd, check=True)

    mux_audio_video(raw_video, os.path.join(AUDIO_DIR, "seg6.wav"), out_mp4, duration=duration)


def main():
    print("================================================================================")
    print(" BUILDING VARIANT B: TTS AUDIO, DYNAMIC SUBTITLES, BAS LOGO & QR CODE")
    print("================================================================================")

    # Step 1: Ensure Kokoro TTS Audio tracks are generated
    print("\nStep 1: Generating/Checking Kokoro-82M TTS Audio Tracks...")
    build_audio_tracks()

    # Step 2: Build individual segments with top-aligned HUD and bottom captions
    seg1_mp4 = os.path.join(VIDEO_DIR, "seg1_variant_b.mp4")
    seg2_mp4 = os.path.join(VIDEO_DIR, "seg2_variant_b.mp4")
    seg3_mp4 = os.path.join(VIDEO_DIR, "seg3_variant_b.mp4")
    seg4_mp4 = os.path.join(VIDEO_DIR, "seg4_variant_b.mp4")
    seg5_mp4 = os.path.join(VIDEO_DIR, "seg5_variant_b.mp4")
    seg6_mp4 = os.path.join(VIDEO_DIR, "seg6_variant_b.mp4")

    print("\nStep 2: Building Segment 1 (Hook Card + Audio + Subtitles)...")
    build_variant_b_seg1(seg1_mp4, duration=3.2)

    print("\nStep 3: Building Segment 2 (3D Flight + Audio + Subtitles)...")
    build_variant_b_seg2(seg2_mp4, duration=12.6, fps=30)

    print("\nStep 4: Building Segment 3 (Wide Sky + Top HUD + Audio + Subtitles)...")
    build_variant_b_seg3(seg3_mp4, duration=4.8)

    print("\nStep 5: Building Segment 4 (Telescopic Transit + Top HUD + Audio + Subtitles)...")
    build_variant_b_seg4(seg4_mp4, duration=10.0)

    print("\nStep 6: Building Segment 5 (Zoomed Contacts + Top Callouts + Audio + Subtitles)...")
    build_variant_b_seg5(seg5_mp4, duration=17.5)

    print("\nStep 7: Building Segment 6 (BAS Logo + QR Code + Timetable + Audio + Subtitles)...")
    build_variant_b_seg6(seg6_mp4, duration=9.2)

    # Step 8: Concatenate all 6 audio-video segments into Master Variant B Video
    print("\nStep 8: Concatenating all segments into Master Variant B Video...")
    concat_list = os.path.join(CWD, "concat_variant_b.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        f.write(f"file '{seg1_mp4.replace('\\', '/')}'\n")
        f.write(f"file '{seg2_mp4.replace('\\', '/')}'\n")
        f.write(f"file '{seg3_mp4.replace('\\', '/')}'\n")
        f.write(f"file '{seg4_mp4.replace('\\', '/')}'\n")
        f.write(f"file '{seg5_mp4.replace('\\', '/')}'\n")
        f.write(f"file '{seg6_mp4.replace('\\', '/')}'\n")

    master_b_mp4 = os.path.join(VIDEO_DIR, "jupiter-occultation-portrait-variant-b.mp4")
    concat_cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_list,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        master_b_mp4
    ]
    subprocess.run(concat_cmd, check=True)
    print(f"\n Master Variant B Video generated: {master_b_mp4} ({os.path.getsize(master_b_mp4)/1024/1024:.2f} MB)")

    # Step 9: Generate animated GIF preview for Variant B
    print("\nStep 9: Generating animated GIF preview for Variant B...")
    master_b_gif = os.path.join(VIDEO_DIR, "jupiter-occultation-portrait-variant-b.gif")
    gif_cmd = [
        "ffmpeg", "-y",
        "-i", master_b_mp4,
        "-vf", "fps=10,scale=360:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3",
        master_b_gif
    ]
    subprocess.run(gif_cmd, check=True)
    print(f" Variant B GIF preview generated: {master_b_gif} ({os.path.getsize(master_b_gif)/1024/1024:.2f} MB)")
    print("\nALL VARIANT B STEPS COMPLETED!")


if __name__ == "__main__":
    main()
