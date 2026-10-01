# Story Pipeline Generator

A Python-based automated video-content pipeline for generating vertical
short-form videos from a gameplay/background video and an AI-generated
script.

The project contains **two related pipelines**:

-   `main.py` --- short Roblox-rant style videos, typically around
    30--35 seconds.
-   `main_story.py` --- serialized story videos split into multiple
    chapters/parts, typically around 9 minutes total.

Both pipelines reuse the same downstream video-processing modules for
voiceover, gameplay, subtitles, memes, sound effects, video assembly,
uniquification, validation, and captions.

------------------------------------------------------------------------

## Features

### Short-video pipeline

`main.py` performs the following stages:

1.  Generate a script from a concept.
2.  Generate an ElevenLabs voiceover, or use mock audio for testing.
3.  Extract/synchronize gameplay footage to the audio duration.
4.  Generate subtitles and detect emotions.
5.  Insert context-aware meme images.
6.  Insert context-aware sound effects.
7.  Assemble the final 1080×1920 vertical video.
8.  Apply an optional FFmpeg-based uniquification pass.
9.  Validate the generated video and write pipeline logs.
10. Generate captions for publishing.

### Serialized-story pipeline

`main_story.py` extends the same architecture to generate a complete
story:

1.  Generate a story outline.
2.  Split the story into approximately 10--13 chapters.
3.  Generate a script for each chapter.
4.  Generate a voiceover for every chapter.
5.  Extract gameplay clips for every chapter.
6.  Generate subtitles and emotion information.
7.  Add `Part X of Y` context to publishing captions.
8.  Inject memes and SFX at synchronized timestamps.
9.  Assemble each chapter into an individual vertical video.
10. Optionally uniquify the exported videos.
11. Validate the generated parts.
12. Produce captions and pipeline logs.

The default story configuration targets approximately **9 minutes** of
total story content, with individual parts around **42--50 seconds**.

------------------------------------------------------------------------

## Project Structure

``` text
story_pipeline_generator/
│
├── main.py                    # Short-video pipeline entry point
├── main_story.py              # Serialized-story pipeline entry point
│
├── config.json                # Short-video configuration
├── config_story.json          # Serialized-story configuration
├── requirements.txt           # Python dependencies
│
├── modules/
│   ├── script_generator.py    # Short-script generation
│   ├── story_generator.py     # Multi-chapter story generation
│   ├── voiceover_generator.py # ElevenLabs/mock voiceover
│   ├── gameplay_randomizer.py # Gameplay extraction and variation
│   ├── subtitle_generator.py  # Subtitle timing and emotion detection
│   ├── emotion_detector.py    # Emotion analysis
│   ├── meme_engine.py         # Context-aware meme overlays
│   ├── sfx_engine.py          # Context-aware sound effects
│   ├── video_assembler.py     # Video/audio/subtitle compositing
│   ├── video_uniquifier.py    # FFmpeg post-processing
│   ├── validator.py           # Output validation
│   ├── caption_generator.py   # Social-media caption generation
│   ├── organizer.py            # Output organization
│   └── output_logger.py        # Logs and summaries
│
├── assets/
│   ├── memes/                 # Meme images grouped by emotion/category
│   └── sfx/                   # Sound effects grouped by category
│
├── audio/                     # Generated voiceovers
├── gameplay/                  # Extracted gameplay clips
├── scripts/                   # Generated scripts
├── exports/                   # Assembled videos and final outputs
├── logs/                      # Pipeline logs
│
├── generate_sfx.py             # Generate/fill SFX assets using FFmpeg
├── download_sfx.py             # Download SFX assets
├── fix_imagemagick.py          # Windows ImageMagick compatibility helper
└── README_SFX.txt              # Additional SFX instructions
```

------------------------------------------------------------------------

## Requirements

### Python

Use a modern Python 3 version.

Install the Python dependencies with:

``` bash
pip install -r requirements.txt
```

### FFmpeg

FFmpeg must be available from the command line because several parts of
the pipeline call it directly.

Verify:

``` bash
ffmpeg -version
```

If the command is not recognized, install FFmpeg and add its `bin`
directory to your system `PATH`.

### ImageMagick

MoviePy subtitle rendering may require ImageMagick, especially on
Windows.

After installing ImageMagick, run:

``` bash
python fix_imagemagick.py
```

Then verify that ImageMagick is accessible.

### AI / API services

Depending on the configuration, the project can use:

-   OpenAI for script/caption generation fallback.
-   Ollama for the configured story-generation model.
-   ElevenLabs for voice generation.

The story generator imports the `ollama` Python package directly. If
your installation does not already provide it, install it with:

``` bash
pip install ollama
```

You also need a working Ollama setup/model if you want to use the Ollama
generation path.

------------------------------------------------------------------------

## API Keys

### ElevenLabs

Set:

``` text
ELEVENLABS_API_KEY=your_key_here
```

On Windows PowerShell:

``` powershell
$env:ELEVENLABS_API_KEY="your_key_here"
```

If the key is not available, the pipeline automatically falls back to
mock/silent WAV audio unless you explicitly provide another
implementation.

### OpenAI

Set:

``` text
OPENAI_API_KEY=your_key_here
```

On Windows PowerShell:

``` powershell
$env:OPENAI_API_KEY="your_key_here"
```

OpenAI is used as a fallback by several generation components when an
OpenAI key is available.

### Pixabay / SFX downloader

`download_sfx.py` supports `PIXABAY_API_KEY`.

Do **not** commit API keys directly into the repository. The supplied
archive contains a credential embedded in `download_sfx.py`; it should
be treated as exposed and **rotated/revoked before using the repository
publicly**.

Prefer an environment variable:

``` powershell
$env:PIXABAY_API_KEY="your_key_here"
```

and keep secrets out of source control.

------------------------------------------------------------------------

## Configuration

### Short videos

`config.json` controls the short-video pipeline.

Important settings include:

``` json
{
  "pipeline": {
    "num_variations": 5
  },
  "clip": {
    "min_length_seconds": 30,
    "max_length_seconds": 35
  },
  "output": {
    "resolution_width": 1080,
    "resolution_height": 1920,
    "fps": 60
  }
}
```

The default output format is vertical **1080×1920 at 60 FPS**.

### Story videos

`config_story.json` controls the serialized-story pipeline.

The default configuration targets:

-   9 minutes of total story content
-   10--13 chapters
-   approximately 100--130 words per chapter
-   approximately 42--50 seconds per chapter
-   1080×1920 output
-   60 FPS

You can modify these values without changing the Python code.

------------------------------------------------------------------------

## Usage

### 1. Short Roblox-rant video

Run:

``` bash
python main.py --gameplay path/to/gameplay.mp4 --concept "your video concept"
```

Example:

``` bash
python main.py --gameplay gameplay.mp4 --concept "my friend betrayed me during the worst day of my life"
```

### Useful options

The short pipeline supports:

``` bash
python main.py --help
```

Important options include:

``` text
--gameplay       Background gameplay/footage video
--concept        Script concept
--config         Configuration file
--mock-audio     Use generated silent WAV instead of ElevenLabs
--skip-uniquify  Skip the FFmpeg uniquification stage
```

------------------------------------------------------------------------

## Serialized Story Mode

Run:

``` bash
python main_story.py \
  --gameplay gameplay.mp4 \
  --concept "a girl discovers that her best friend has been hiding a huge secret"
```

On Windows PowerShell, the same command can be written on one line:

``` powershell
python main_story.py --gameplay gameplay.mp4 --concept "a girl discovers that her best friend has been hiding a huge secret"
```

The pipeline generates multiple parts and stores them in the configured
export directory.

For example:

``` text
exports/
├── part01_....mp4
├── part02_....mp4
├── part03_....mp4
├── ...
├── captions_....txt
└── final/
    ├── ...
```

### Testing without ElevenLabs

Use:

``` bash
python main_story.py --gameplay gameplay.mp4 --concept "test story" --mock-audio
```

This generates silent WAV files whose duration is estimated from the
script word count.

### Faster testing

Skip the optional FFmpeg uniquification pass:

``` bash
python main_story.py --gameplay gameplay.mp4 --concept "test story" --skip-uniquify
```

You can combine both:

``` bash
python main_story.py --gameplay gameplay.mp4 --concept "test story" --mock-audio --skip-uniquify
```

------------------------------------------------------------------------

## Processing Pipeline

The architecture can be summarized as:

``` text
                    ┌───────────────────┐
                    │  Concept / Prompt │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │ Script Generation │
                    │ Ollama / OpenAI   │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │    Voiceover      │
                    │ ElevenLabs / Mock │
                    └─────────┬─────────┘
                              │
              ┌───────────────┴────────────────┐
              ▼                                ▼
    ┌──────────────────┐             ┌──────────────────┐
    │ Gameplay Extract │             │ Subtitle/Emotion │
    └─────────┬────────┘             └─────────┬────────┘
              │                                │
              └───────────────┬────────────────┘
                              ▼
                 ┌─────────────────────────┐
                 │ Meme + SFX Injection    │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │     Video Assembly      │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │ Optional Uniquification │
                 │        FFmpeg            │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │       Validation        │
                 └────────────┬────────────┘
                              │
                              ▼
                     Upload-ready video
```

------------------------------------------------------------------------

## Assets

### Memes

Meme images are organized by emotional category:

``` text
assets/memes/
├── cringe/
├── hype/
├── rage/
├── sadness/
└── shock/
```

The meme engine selects assets based on detected emotional/contextual
triggers.

### Sound effects

SFX are organized by category:

``` text
assets/sfx/
├── awkward/
├── cringe/
├── crying/
├── heartbreak/
├── hype/
├── rage/
├── romantic/
├── sadness/
├── shock/
└── tension/
```

The SFX engine synchronizes selected effects with detected emotional
moments.

To inspect the dedicated SFX setup instructions, see:

``` text
README_SFX.txt
```

------------------------------------------------------------------------

## Output

Generated files are separated by processing stage:

``` text
scripts/     # Generated scripts
audio/       # Voiceovers
gameplay/    # Extracted clips
exports/     # Assembled videos
logs/        # Pipeline logs
```

The final serialized-story videos are placed under:

``` text
exports/final/
```

when uniquification is enabled.

------------------------------------------------------------------------

## Logging

The application writes logs both to the console and to files under
`logs/`.

Examples include:

``` text
logs/pipeline.log
logs/story_pipeline.log
```

CSV-style output logging is also configured through the
`output.log_file` setting in the JSON configuration.

------------------------------------------------------------------------

## Validation

Before the pipeline finishes, generated videos are checked for
conditions such as:

-   video duration
-   audio availability
-   script/word-count constraints
-   output validity

The validation stage reports which generated versions or story parts
require regeneration.

------------------------------------------------------------------------

## Troubleshooting

### `ffmpeg is not recognized`

Install FFmpeg and add it to `PATH`.

Check:

``` bash
ffmpeg -version
```

### MoviePy / ImageMagick errors

Run:

``` bash
python fix_imagemagick.py
```

Make sure ImageMagick is installed and accessible.

### No ElevenLabs API key

For testing, use:

``` bash
--mock-audio
```

Otherwise set:

``` text
ELEVENLABS_API_KEY
```

### Story generation fails

Check that:

1.  Ollama is installed/running if you are using the Ollama path.
2.  The configured model is available.
3.  `OPENAI_API_KEY` is configured if you expect the OpenAI fallback to
    work.
4.  The selected model name in `config_story.json` is correct for your
    Ollama installation.

### Output videos are too long

The voiceover module measures the actual generated audio duration and
can apply FFmpeg time-stretching when the configured maximum duration is
exceeded.

Adjust these values in the appropriate configuration:

``` json
"voiceover": {
  "max_duration_seconds": 50,
  "max_speed_override": 1.06
}
```

Avoid setting aggressive speed values if natural speech quality is
important.

------------------------------------------------------------------------

## Development Notes

The pipeline is intentionally modular. Most stages communicate through
Python dictionaries representing scripts/chapters.

For the story pipeline, `story_generator.py` produces chapter
dictionaries compatible with the existing modules, allowing the story
mode to reuse the same:

-   voiceover generator
-   gameplay extractor
-   subtitle generator
-   meme engine
-   SFX engine
-   video assembler
-   uniquifier
-   validator
-   caption generator

This makes it possible to modify story generation without rewriting the
video-processing pipeline.

------------------------------------------------------------------------

## Recommended Development Workflow

For development and debugging:

1.  Start with `--mock-audio`.
2.  Use `--skip-uniquify` to reduce processing time.
3.  Test with one gameplay video and one concept.
4.  Inspect `logs/`.
5.  Check the generated intermediate files in `scripts/`, `audio/`, and
    `gameplay/`.
6.  Once the pipeline works, enable real ElevenLabs audio.
7.  Finally enable the uniquification stage.

Example:

``` bash
python main_story.py \
  --gameplay gameplay.mp4 \
  --concept "a secret changes everything" \
  --mock-audio \
  --skip-uniquify
```

------------------------------------------------------------------------

## Security

Never commit the following to Git:

``` text
OPENAI_API_KEY
ELEVENLABS_API_KEY
PIXABAY_API_KEY
```

Use environment variables or a local `.env` file and add `.env` to
`.gitignore`.

Also review the existing `download_sfx.py` before publishing this
repository because the supplied archive contains an embedded API
credential.

------------------------------------------------------------------------

## License

No explicit license file was included in the supplied project archive.

If this project will be distributed publicly, add an appropriate
`LICENSE` file and verify the licensing/usage rights of all included
gameplay, meme, music, voice, and sound-effect assets.
