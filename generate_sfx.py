"""
generate_sfx.py
================
Generates all SFX for the Teen Story Pipeline using ffmpeg lavfi filters.
No internet, no downloads, no CDN errors — everything built locally.

Run once before your first story:
    python generate_sfx.py

Sounds generated:
  romantic/   notification_ding, sparkle, heartbeat_soft, piano_hit, aww_crowd
  heartbreak/ glass_shatter, deep_thud, sad_piano, cry_sob
  tension/    suspense_sting, heartbeat_fast, dramatic_hit, clock_tick
  awkward/    crickets, wrong_buzzer, trombone_sad
  crying/     sob, sniff, piano_cry
  shock/      female_gasp, stinger        (supplements existing folder)
  sadness/    violin_sting               (supplements existing folder)
  hype/       whoosh                     (supplements existing folder)
"""

import os
import subprocess
import sys

BASE = "assets/sfx"


def _run(dest: str, *ffargs) -> bool:
    """Run ffmpeg with any number of args + fixed output options."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    cmd = ["ffmpeg", "-y"] + list(ffargs) + ["-ar", "44100", "-ac", "1", dest]
    r   = subprocess.run(cmd, capture_output=True, text=True)
    ok  = r.returncode == 0 and os.path.exists(dest) and os.path.getsize(dest) > 200
    if not ok:
        sys.stderr.write(f"  [ffmpeg] {os.path.basename(dest)}: {r.stderr[-180:].strip()}\n")
    return ok


def _p(folder: str, name: str) -> str:
    return os.path.join(BASE, folder, name)


def _skip(path: str) -> bool:
    return os.path.exists(path) and os.path.getsize(path) > 500


# ── All SFX ────────────────────────────────────────────────────────────────

SOUNDS = []   # filled by _define_all(), used by main()


def _define_all():
    s = []   # list of (label, dest, *ffargs)

    # ── ROMANTIC ─────────────────────────────────────────────────────────

    s.append(("notification ding", _p("romantic","notification_ding.mp3"),
        "-f","lavfi","-i","sine=f=1200:d=0.55",
        "-af","afade=t=in:ss=0:d=0.01,afade=t=out:st=0.18:d=0.37,volume=0.85",
    ))

    s.append(("sparkle chime", _p("romantic","sparkle.mp3"),
        "-f","lavfi","-i","sine=f=523:d=0.55",
        "-f","lavfi","-i","sine=f=659:d=0.55",
        "-f","lavfi","-i","sine=f=784:d=0.55",
        "-filter_complex",
        "[0]afade=t=out:st=0.35:d=0.2[a];"
        "[1]adelay=130|130,afade=t=out:st=0.35:d=0.2[b];"
        "[2]adelay=260|260,afade=t=out:st=0.35:d=0.2[c];"
        "[a][b][c]amix=inputs=3:normalize=0,volume=0.75",
    ))

    s.append(("soft heartbeat", _p("romantic","heartbeat_soft.mp3"),
        "-f","lavfi","-i","sine=f=65:d=0.9",
        "-af",
        "aeval=val(0)*if(between(t\\,0.0\\,0.08)\\,pow(sin(t/0.08*3.14)\\,2)\\,0)"
        "+val(0)*if(between(t\\,0.15\\,0.22)\\,pow(sin((t-0.15)/0.07*3.14)\\,2)*0.6\\,0)"
        "+val(0)*if(between(t\\,0.55\\,0.63)\\,pow(sin((t-0.55)/0.08*3.14)\\,2)\\,0)"
        "+val(0)*if(between(t\\,0.70\\,0.77)\\,pow(sin((t-0.70)/0.07*3.14)\\,2)*0.6\\,0),"
        "volume=0.8",
    ))

    s.append(("warm piano hit", _p("romantic","piano_hit.mp3"),
        "-f","lavfi","-i","sine=f=440:d=1.2",
        "-f","lavfi","-i","sine=f=880:d=1.2",
        "-f","lavfi","-i","sine=f=1320:d=1.2",
        "-filter_complex",
        "[0]volume=1.0[a];[1]volume=0.3[b];[2]volume=0.12[c];"
        "[a][b][c]amix=inputs=3:normalize=0,"
        "afade=t=in:ss=0:d=0.005,afade=t=out:st=0.4:d=0.8,volume=0.75",
    ))

    s.append(("crowd aww", _p("romantic","aww_crowd.mp3"),
        "-f","lavfi","-i","anoisesrc=c=pink:d=1.0:a=0.4",
        "-af",
        "bandpass=f=350:width_type=o:w=2,"
        "afade=t=in:ss=0:d=0.3,afade=t=out:st=0.7:d=0.3,volume=0.6",
    ))

    # ── HEARTBREAK ───────────────────────────────────────────────────────

    s.append(("glass shatter", _p("heartbreak","glass_shatter.mp3"),
        "-f","lavfi","-i","anoisesrc=c=white:d=0.9:a=0.9",
        "-af","highpass=f=2500,afade=t=in:ss=0:d=0.005,afade=t=out:st=0.12:d=0.78,volume=0.85",
    ))

    s.append(("deep thud", _p("heartbreak","deep_thud.mp3"),
        "-f","lavfi","-i","sine=f=55:d=0.6",
        "-af","afade=t=in:ss=0:d=0.01,afade=t=out:st=0.05:d=0.55,volume=1.2",
    ))

    s.append(("sad piano (A minor)", _p("heartbreak","sad_piano.mp3"),
        "-f","lavfi","-i","sine=f=220:d=1.5",
        "-f","lavfi","-i","sine=f=262:d=1.5",
        "-f","lavfi","-i","sine=f=330:d=1.5",
        "-filter_complex",
        "[0]volume=1.0[a];[1]volume=0.5[b];[2]volume=0.3[c];"
        "[a][b][c]amix=inputs=3:normalize=0,"
        "afade=t=in:ss=0:d=0.01,afade=t=out:st=0.6:d=0.9,volume=0.7",
    ))

    s.append(("subtle sob", _p("heartbreak","cry_sob.mp3"),
        "-f","lavfi","-i","anoisesrc=c=pink:d=1.1:a=0.35",
        "-af",
        "bandpass=f=500:width_type=o:w=1.5,tremolo=f=6:d=0.7,"
        "afade=t=in:ss=0:d=0.15,afade=t=out:st=0.75:d=0.35,volume=0.5",
    ))

    # ── TENSION ──────────────────────────────────────────────────────────

    s.append(("suspense sting", _p("tension","suspense_sting.mp3"),
        "-f","lavfi","-i","sine=f=82:d=1.0",
        "-af","aeval=val(0)*pow(t/1.0\\,0.5),afade=t=out:st=0.8:d=0.2,volume=0.9",
    ))

    s.append(("fast heartbeat", _p("tension","heartbeat_fast.mp3"),
        "-f","lavfi","-i","sine=f=70:d=1.2",
        "-af",
        "aeval=val(0)*("
        "if(between(t\\,0.00\\,0.07)\\,pow(sin(t/0.07*3.14)\\,2)\\,0)+"
        "if(between(t\\,0.12\\,0.18)\\,pow(sin((t-0.12)/0.06*3.14)\\,2)*0.6\\,0)+"
        "if(between(t\\,0.30\\,0.37)\\,pow(sin((t-0.30)/0.07*3.14)\\,2)\\,0)+"
        "if(between(t\\,0.42\\,0.48)\\,pow(sin((t-0.42)/0.06*3.14)\\,2)*0.6\\,0)+"
        "if(between(t\\,0.60\\,0.67)\\,pow(sin((t-0.60)/0.07*3.14)\\,2)\\,0)+"
        "if(between(t\\,0.72\\,0.78)\\,pow(sin((t-0.72)/0.06*3.14)\\,2)*0.6\\,0)),"
        "volume=1.0",
    ))

    s.append(("cinematic hit", _p("tension","dramatic_hit.mp3"),
        "-f","lavfi","-i","anoisesrc=c=brown:d=0.7:a=0.8",
        "-af","lowpass=f=300,afade=t=in:ss=0:d=0.02,afade=t=out:st=0.2:d=0.5,volume=1.1",
    ))

    s.append(("clock ticking", _p("tension","clock_tick.mp3"),
        "-f","lavfi","-i","sine=f=2000:d=1.6",
        "-af",
        "aeval=val(0)*("
        "if(between(t\\,0.00\\,0.04)\\,1\\,0)+"
        "if(between(t\\,0.40\\,0.44)\\,1\\,0)+"
        "if(between(t\\,0.80\\,0.84)\\,1\\,0)+"
        "if(between(t\\,1.20\\,1.24)\\,1\\,0)),"
        "volume=0.7",
    ))

    # ── AWKWARD ──────────────────────────────────────────────────────────

    s.append(("crickets", _p("awkward","crickets.mp3"),
        "-f","lavfi","-i","anoisesrc=c=white:d=2.0:a=0.3",
        "-af","highpass=f=4000,lowpass=f=8000,tremolo=f=18:d=0.9,volume=0.55",
    ))

    s.append(("wrong buzzer", _p("awkward","wrong_buzzer.mp3"),
        "-f","lavfi","-i","sine=f=180:d=0.6",
        "-af","afade=t=in:ss=0:d=0.01,afade=t=out:st=0.5:d=0.1,volume=0.9",
    ))

    s.append(("sad trombone", _p("awkward","trombone_sad.mp3"),
        "-f","lavfi","-i","sine=f=233:d=0.22",
        "-f","lavfi","-i","sine=f=196:d=0.22",
        "-f","lavfi","-i","sine=f=156:d=0.22",
        "-f","lavfi","-i","sine=f=131:d=0.44",
        "-filter_complex",
        "[0]afade=t=out:st=0.18:d=0.04[a];"
        "[1]adelay=220|220,afade=t=out:st=0.18:d=0.04[b];"
        "[2]adelay=440|440,afade=t=out:st=0.18:d=0.04[c];"
        "[3]adelay=660|660,afade=t=out:st=0.35:d=0.09[d];"
        "[a][b][c][d]amix=inputs=4:normalize=0,volume=0.8",
    ))

    # ── CRYING ───────────────────────────────────────────────────────────

    s.append(("cry/sob", _p("crying","sob.mp3"),
        "-f","lavfi","-i","anoisesrc=c=pink:d=1.3:a=0.45",
        "-af",
        "bandpass=f=450:width_type=o:w=2,tremolo=f=5:d=0.8,"
        "afade=t=in:ss=0:d=0.2,afade=t=out:st=0.9:d=0.4,volume=0.55",
    ))

    s.append(("sniff", _p("crying","sniff.mp3"),
        "-f","lavfi","-i","anoisesrc=c=pink:d=0.35:a=0.6",
        "-af",
        "bandpass=f=600:width_type=o:w=3,"
        "afade=t=in:ss=0:d=0.03,afade=t=out:st=0.1:d=0.25,volume=0.65",
    ))

    s.append(("tearful piano chord", _p("crying","piano_cry.mp3"),
        "-f","lavfi","-i","sine=f=147:d=1.8",
        "-f","lavfi","-i","sine=f=175:d=1.8",
        "-f","lavfi","-i","sine=f=220:d=1.8",
        "-filter_complex",
        "[0]volume=1.0[a];[1]volume=0.55[b];[2]volume=0.35[c];"
        "[a][b][c]amix=inputs=3:normalize=0,"
        "afade=t=in:ss=0:d=0.01,afade=t=out:st=0.7:d=1.1,volume=0.7",
    ))

    # ── SHOCK (supplement) ────────────────────────────────────────────────

    s.append(("gasp", _p("shock","female_gasp.mp3"),
        "-f","lavfi","-i","anoisesrc=c=pink:d=0.5:a=0.7",
        "-af",
        "bandpass=f=700:width_type=o:w=2.5,"
        "afade=t=in:ss=0:d=0.02,afade=t=out:st=0.15:d=0.35,volume=0.7",
    ))

    s.append(("shock stinger", _p("shock","stinger.mp3"),
        "-f","lavfi","-i","sine=f=900:d=0.4",
        "-af","afade=t=in:ss=0:d=0.01,afade=t=out:st=0.1:d=0.3,volume=0.8",
    ))

    # ── SADNESS (supplement) ─────────────────────────────────────────────

    s.append(("violin moan", _p("sadness","violin_sting.mp3"),
        "-f","lavfi","-i","sine=f=165:d=1.4",
        "-af",
        "vibrato=f=5.5:d=0.6,"
        "afade=t=in:ss=0:d=0.08,afade=t=out:st=0.9:d=0.5,volume=0.75",
    ))

    # ── HYPE (supplement) ────────────────────────────────────────────────

    s.append(("rising whoosh", _p("hype","whoosh.mp3"),
        "-f","lavfi","-i","anoisesrc=c=white:d=0.7:a=0.5",
        "-af","highpass=f=1000,afade=t=in:ss=0:d=0.05,afade=t=out:st=0.5:d=0.2,volume=0.7",
    ))

    return s


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 58)
    print("  Teen Story Pipeline — SFX Generator")
    print("  Building sounds with ffmpeg (no internet needed)")
    print("=" * 58)

    sounds  = _define_all()
    ok = skip = fail = 0
    rows = []

    for label, dest, *ffargs in sounds:
        if _skip(dest):
            skip += 1
            kb = os.path.getsize(dest) // 1024
            rows.append(("~", label, dest, kb))
            continue

        success = _run(dest, *ffargs)
        if success:
            ok += 1
            kb = os.path.getsize(dest) // 1024
            rows.append(("✓", label, dest, kb))
        else:
            fail += 1
            rows.append(("✗", label, dest, 0))

    # Print results
    for icon, label, dest, kb in rows:
        size_str = f"{kb:>4} KB" if kb else "  FAIL"
        print(f"  {icon}  {label:<36} {size_str}  {os.path.basename(dest)}")

    print("\n" + "=" * 58)
    print(f"  ✓ Generated : {ok}")
    print(f"  ~ Skipped   : {skip}  (already existed)")
    if fail:
        print(f"  ✗ Failed    : {fail}  — check ffmpeg is installed")
    print("=" * 58)

    if fail == 0:
        print(f"\n  All SFX ready in: assets/sfx/")
        print(f"  Run your story:   python main_story.py --gameplay video.mp4 --concept \"...\"\n")
    else:
        print(f"\n  {fail} file(s) failed. The pipeline will still run —")
        print(f"  sfx_engine.py falls back to nearby emotion folders automatically.\n")


if __name__ == "__main__":
    main()
