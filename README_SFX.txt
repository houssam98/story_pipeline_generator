SFX Setup — Story Pipeline
================================

Two scripts, run in order:

  STEP 1 — Download real recordings from Pixabay:
      python download_sfx.py

  STEP 2 — Fill any gaps with ffmpeg synthesis:
      python generate_sfx.py

Why two scripts?
  download_sfx.py  — tries to get real human-recorded sounds via Pixabay API
  generate_sfx.py  — builds synthetic versions for anything that didn't download

Running both is recommended. generate_sfx.py skips files that already exist,
so it only fills the gaps. End result: every SFX folder has at least one file.

Pixabay API key used: 54948387-5d1cb6d94f0805be8b51b37c6
  Rate limit: 100 requests / 60 seconds (download_sfx.py uses ~50 requests total)
  The key is embedded in download_sfx.py. Set env var PIXABAY_API_KEY to override.

SFX folders and what they're used for:
  assets/sfx/romantic/    piano_hit, sparkle, heartbeat_soft, notification_ding, aww_crowd
  assets/sfx/heartbreak/  glass_shatter, deep_thud, sad_piano, cry_sob
  assets/sfx/tension/     suspense_sting, heartbeat_fast, dramatic_hit, clock_tick
  assets/sfx/awkward/     crickets, wrong_buzzer, trombone_sad
  assets/sfx/crying/      sob, sniff, piano_cry
  assets/sfx/shock/       female_gasp, stinger  (+ existing: gasp, vine_boom, record_scratch)
  assets/sfx/sadness/     violin_sting          (+ existing: aww, sad_tromboe)
  assets/sfx/hype/        whoosh                (+ existing: air_horn, crowd_cheer)
  assets/sfx/rage/        (existing: buzzer, table_slam, angry_buzz — no new files needed)

Adding your own sounds:
  Drop any .mp3 file into the relevant folder. The engine picks randomly from all
  files in the folder, so more = more variety. generate_sfx.py only skips files
  that already exist (>500 bytes), so it won't overwrite your custom sounds.
