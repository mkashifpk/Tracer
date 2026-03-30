# Tracer MVP Technical Specification

## 1. App Overview

### 1.1 Product Name
`Tracer - Turn bitmap images into SVGs`

### 1.2 Purpose
Tracer is an offline Windows-first desktop application for converting batches of black-and-white raster images into clean SVG vector files. The MVP focuses on `.png`, `.jpg`, and `.jpeg` input files containing dark foreground shapes on white or transparent backgrounds.

### 1.3 Primary Goal
Produce smooth, simplified, production-usable SVG outputs from simple monochrome bitmap artwork in bulk, with a non-technical UI and predictable export behavior.

### 1.4 Non-Goals for MVP
- Full-color vectorization
- Photo tracing
- Real-time collaborative or cloud features
- Web deployment
- Advanced node editing inside the app
- CAD-grade geometric cleanup

### 1.5 Supported Platforms
- Primary: Windows 10 and Windows 11
- Offline-only operation
- Single-user desktop workflow

### 1.6 Core Architecture
- Desktop UI: PySide6
- Processing pipeline: Python + OpenCV + Pillow + NumPy
- Tracing backend abstraction:
  - Default MVP backend: VTracer
  - Future optional backend: Potrace-compatible implementation if licensing permits


## 2. User Flow

### 2.1 Main User Journey
1. User launches Tracer.
2. User selects an input folder.
3. App scans supported images in the folder.
4. User selects an output folder.
5. App displays detected files and validation status.
6. User selects a sample file for preview.
7. User adjusts tracing controls.
8. App renders preview:
   - Original image
   - Binary/mask preview
   - SVG preview
9. User reviews output quality.
10. User starts batch export.
11. App processes files sequentially or with controlled parallelism.
12. App writes SVGs with the same base filename into the output folder.
13. App shows completion summary and any warnings/errors.

### 2.2 Alternate Flows
- User changes controls after preview: preview invalidates and re-renders.
- User chooses invert mode for white-on-black input.
- User skips invalid or unreadable files.
- User cancels a running batch.
- User re-runs batch with overwrite enabled.


## 3. UI Screens

## 3.1 Main Window

### Purpose
Single-window application for file selection, preview, controls, and batch execution.

### Layout
- Top toolbar/header
  - App name
  - Open input folder
  - Open output folder
  - Start batch
  - Cancel batch
- Left panel
  - Input folder path
  - Output folder path
  - File list with status
  - Summary counts
- Center panel
  - Preview tabs or split panes
  - Original preview
  - Processed mask preview
  - SVG preview
- Right panel
  - Preset selector
  - Basic controls
  - Advanced controls
- Bottom status bar
  - Current operation
  - Progress bar
  - Success/error counts

## 3.2 File List Panel

### Columns
- Filename
- Type (`PNG`, `JPG`, `JPEG`)
- Dimensions
- Alpha present (`Yes/No`)
- Validation status
- Output status

### Status Values
- Ready
- Unsupported
- Warning
- Queued
- Processing
- Exported
- Skipped
- Failed
- Cancelled

## 3.3 Preview Panel

### Views
- Original raster
- Threshold/mask preview
- SVG preview

### Interactions
- Zoom in/out
- Fit to view
- Pan
- Toggle transparent background checkerboard
- Toggle overlay comparison

## 3.4 Settings/Controls Panel

### Basic Section
- Threshold
- Invert colors
- Min artifact area
- Smoothing strength
- Path simplification tolerance

### Advanced Section
- Resize before trace
- Ignore transparent pixels
- Merge nearby shapes
- Fill-only output
- Stroke output
- Stroke width

## 3.5 Completion Summary Dialog

### Contents
- Total files found
- Total processed
- Total exported
- Total skipped
- Total failed
- Output folder shortcut
- Link/button to export log


## 4. Input Validation

## 4.1 Supported Formats
- `.png`
- `.jpg`
- `.jpeg`

## 4.2 Folder Validation
- Input folder must exist and be readable.
- Output folder must exist or be creatable.
- Input and output folders may be the same, but this is discouraged and should display a warning.

## 4.3 File Validation
- File extension must be supported.
- File must be readable by Pillow/OpenCV.
- Image dimensions must be greater than zero.
- Image must not exceed configured maximum processing dimensions or memory safety limits.
- File should contain detectable foreground after preprocessing; otherwise mark as warning or skip.

## 4.4 Content Validation Rules
- PNG:
  - Accept RGB, RGBA, grayscale, indexed color.
  - Transparency should be read if present.
- JPG/JPEG:
  - Accept grayscale or color.
  - No transparency support.

## 4.5 Black/White Suitability Checks
The MVP accepts files that are not strictly 1-bit images, but it is optimized for black-and-white source artwork.

Heuristic checks:
- Measure grayscale histogram spread.
- Detect whether image appears mostly bimodal.
- Detect likely foreground occupancy ratio.
- Warn, do not block, if input appears highly photographic or noisy.

## 4.6 Validation Outcomes
- `valid`: safe to process
- `valid_with_warning`: process allowed, but quality may vary
- `invalid`: skip during batch, show reason


## 5. Tracing Pipeline

## 5.1 Pipeline Goals
- Extract dark shapes from white or transparent backgrounds
- Reduce tiny artifacts
- Preserve intended silhouette
- Smooth edges
- Simplify paths
- Generate compact, valid SVG

## 5.2 Processing Stages

### Stage 1: Load Image
- Read image with Pillow for reliable format handling.
- Convert to NumPy array for processing.
- Record:
  - width/height
  - color mode
  - alpha presence
  - DPI metadata if available

### Stage 2: Transparency Handling
- If `ignore transparent pixels = true` and image has alpha:
  - Use alpha mask to exclude fully transparent pixels from foreground consideration.
  - Semi-transparent pixels may be treated as background in MVP unless thresholded by alpha > configurable fixed constant.
- If no alpha is present:
  - Continue with normal luminance processing.

### Stage 3: Resize Before Trace
- If enabled and source image exceeds user-specified trace size:
  - Resize using high-quality downsampling before tracing.
- Resize is intended to:
  - improve speed
  - reduce noise
  - normalize outputs
- Default MVP behavior:
  - disabled unless user enables it

### Stage 4: Grayscale Conversion
- If source is not already single-channel:
  - Convert to grayscale/luminance
- Recommended formula:
  - standard luminance conversion from RGB
- Output:
  - `grayscale_image`

### Stage 5: Thresholding for Black/White Separation
- Apply thresholding to separate foreground and background.
- Supported modes in MVP:
  - manual threshold
  - automatic threshold using Otsu as preview helper or auto preset

Rule:
- Pixels darker than threshold become foreground by default.
- Background is white or transparent.

Output:
- binary mask

### Stage 6: Optional Inversion
- If `invert colors = true`:
  - swap foreground/background interpretation
- This supports white-on-black artwork and inverted source scans.

### Stage 7: Despeckle / Remove Small Isolated Pixels
- Remove small connected components below `min artifact area`.
- Apply optional morphology:
  - opening to remove isolated dots
  - closing to fill tiny holes
- Use conservative defaults to avoid damaging thin features.

Output:
- cleaned binary mask

### Stage 8: Merge Nearby Shapes if Useful
- Optional step
- If enabled:
  - bridge tiny gaps between components using controlled dilation/closing
  - reconnect contours separated by 1-2 px noise gaps
- Must be bounded to avoid merging distinct artwork unintentionally.

### Stage 9: Contour Extraction
- Extract foreground regions/contours from the cleaned mask.
- Preserve outer boundaries and holes where supported by backend.
- Discard contours below area threshold.

### Stage 10: Contour Smoothing
- Smooth contour irregularities before or during vector fitting.
- Smoothing may be implemented through:
  - preprocessing morphology
  - contour simplification smoothing
  - tracing-engine curve fitting controls

### Stage 11: Path Simplification
- Reduce point count while preserving shape fidelity.
- Simplify jagged edges and excess vertices.
- Controlled by `path simplification tolerance`.

### Stage 12: SVG Generation
- Generate SVG paths from traced contours.
- Output should:
  - preserve source aspect ratio
  - define width/height and viewBox
  - encode vector paths with fill and optional stroke
  - use deterministic ordering when possible

## 5.3 Fill and Stroke Output Modes

### Fill-Only Output
- Default output mode for MVP
- Foreground shapes exported as filled paths
- Recommended default fill color: black
- No stroke unless explicitly enabled

### Optional Stroke Output
- When enabled:
  - add stroke attributes to exported paths
  - user can specify stroke width
- MVP limitation:
  - stroke is stylistic output on traced shapes, not centerline tracing

## 5.4 Preferred Implementation Split
- OpenCV handles:
  - grayscale
  - thresholding
  - morphology
  - connected components
  - contour extraction if needed for diagnostics
- VTracer handles:
  - curve fitting
  - vector path generation
  - spline/polygon mode selection


## 6. Tracing Controls

## 6.1 Threshold
- Type: integer slider/input
- Range: `0-255`
- Default: `128` or `Auto` preset using Otsu
- Meaning:
  - lower values include fewer dark pixels
  - higher values include more pixels as foreground

## 6.2 Invert Colors
- Type: checkbox
- Default: off
- Meaning:
  - treat light shapes on dark background as foreground

## 6.3 Min Artifact Area
- Type: integer slider/input
- Unit: pixels
- Default: `8-32 px` depending on image size preset
- Meaning:
  - remove connected components smaller than this area

## 6.4 Smoothing Strength
- Type: slider
- Range: normalized UI scale, for example `0-100`
- Default: medium
- Internal mapping:
  - influences morphology strength and/or tracing curve fitting parameters

## 6.5 Path Simplification Tolerance
- Type: float slider/input
- Range: implementation-defined, for example `0.1-10.0`
- Default: conservative
- Meaning:
  - higher values produce fewer nodes and smoother shapes
  - excessive values may distort geometry

## 6.6 Resize Before Trace
- Type: checkbox + numeric max dimension
- Default: off
- Meaning:
  - resize large images before processing to improve speed and stabilize curves

## 6.7 Ignore Transparent Pixels
- Type: checkbox
- Default: on for PNG, disabled/hidden for JPG
- Meaning:
  - transparent regions do not participate in foreground detection

## 6.8 Merge Nearby Shapes
- Type: checkbox + optional strength
- Default: off
- Meaning:
  - reconnect very small gaps between close shapes where useful

## 6.9 Fill-Only Output
- Type: checkbox
- Default: on

## 6.10 Stroke Output
- Type: checkbox
- Default: off
- Dependent control:
  - stroke width


## 7. Preview Behavior

## 7.1 Preview Scope
- Preview runs on the currently selected file only.
- Preview must not block the full UI for long operations.
- Preview should be debounced when sliders change rapidly.

## 7.2 Preview Pipeline
- User selects a file.
- App loads source image.
- App applies current control settings.
- App renders:
  - original image
  - processed mask
  - generated SVG

## 7.3 Preview Refresh Rules
- Re-render preview when:
  - selected file changes
  - any tracing control changes
  - preset changes
  - invert mode changes
  - resize toggle/value changes
- Use debounce around slider edits, e.g. `200-400 ms`.

## 7.4 Preview Fidelity
- Preview should use the same pipeline as export.
- If preview uses reduced resolution for responsiveness, the UI must indicate this.
- Preferred MVP behavior:
  - same settings, same tracing engine
  - optional lower rendering priority, not lower quality

## 7.5 Preview Failure Cases
- If preview generation fails:
  - keep original preview visible
  - show inline error panel for processed/SVG view
  - do not crash or clear user settings


## 8. Export Logic

## 8.1 Output Naming
- Each exported SVG uses the same base filename as the source image.

Examples:
- `logo.png` -> `logo.svg`
- `badge.jpg` -> `badge.svg`

## 8.2 Output Directory Rules
- Export to selected output folder.
- Preserve flat filename mapping in MVP.
- No nested folder mirroring in MVP unless input scan recursion is added later.

## 8.3 Overwrite Behavior
- User-selectable mode:
  - skip existing files
  - overwrite existing files
- Default: skip existing files with warning in summary

## 8.4 Write Safety
- Generate SVG content in memory first.
- Write to temporary file in output directory.
- Atomically rename temp file to final `.svg` if write succeeds.
- Avoid partial/corrupt exports on crash.

## 8.5 SVG Structure Requirements
- Valid XML/SVG document
- `viewBox` required
- width/height included
- path fill/stroke values included based on output settings
- UTF-8 encoding

## 8.6 Transparency Preservation
- PNG:
  - transparency affects shape detection when enabled
  - background transparency is preserved conceptually by exporting only foreground vectors
- JPG:
  - no transparency preservation is possible


## 9. Settings Panel

## 9.1 Settings Categories
- General
- Tracing
- Export
- Performance

## 9.2 General Settings
- Remember last input folder
- Remember last output folder
- Theme choice if added later
- Language reserved for future use

## 9.3 Tracing Settings
- Default preset
- Threshold mode
- Invert default
- Artifact removal default
- Smoothing default
- Simplification default
- Alpha handling default

## 9.4 Export Settings
- Fill-only on/off
- Stroke on/off
- Stroke width
- Overwrite mode
- Open output folder after completion

## 9.5 Performance Settings
- Max concurrent workers
- Preview debounce interval
- Preview max dimension
- Batch memory safety limit

## 9.6 Persistence
- Store settings in user-local config file using platform-appropriate app data directory.
- Settings must load at startup and save on change or clean exit.


## 10. Batch Job Behavior

## 10.1 Job Model
Each file becomes one job with:
- source path
- output path
- detected metadata
- current status
- warning/error state
- processing timestamps

## 10.2 Batch Lifecycle
1. Scan files
2. Validate files
3. Queue valid jobs
4. Start processing
5. Update progress and per-file state
6. Write outputs
7. Summarize results

## 10.3 Concurrency
- Use bounded worker count
- Default worker count:
  - `min(cpu_count - 1, 4)` or similar conservative limit
- Prevent UI thread from doing heavy image processing

## 10.4 Ordering
- Preserve file-list order in UI
- Processing order may be sequential or worker-scheduled
- Summary must remain deterministic

## 10.5 Cancellation
- User can cancel active batch.
- Behavior:
  - no new jobs start after cancel
  - active jobs finish current safe stage or stop at next checkpoint
  - completed exports remain
  - pending jobs marked cancelled

## 10.6 Retry
- Failed jobs can be re-run after settings changes.
- MVP may support:
  - rerun all failed
  - rerun selected file


## 11. Error Handling

## 11.1 Principles
- No crash on bad input file
- Errors isolated to job where possible
- User-visible messages should be clear and non-technical
- Detailed diagnostics should still be logged

## 11.2 Error Categories
- Input folder access error
- Output folder creation/write error
- Unsupported file format
- Image decode failure
- Validation failure
- Tracing backend failure
- SVG write failure
- Out-of-memory or oversized image protection
- Preview render failure

## 11.3 User-Facing Error Examples
- `File could not be read`
- `Image format is unsupported`
- `No foreground shape detected`
- `Output file already exists`
- `Export failed due to write permission`

## 11.4 Recovery Rules
- Skip invalid files and continue batch
- If one file fails, remaining files continue
- If output folder becomes unavailable, pause/stop batch and report blocking issue


## 12. Logging

## 12.1 Logging Goals
- Support troubleshooting
- Support QA comparison runs
- Support user bug reports

## 12.2 Log Destinations
- Rolling application log file
- Optional per-batch summary log

## 12.3 Recommended Log Content
- app startup/shutdown
- selected folders
- settings snapshot for batch
- per-file validation result
- per-file processing duration
- per-file export result
- warnings and stack traces for failures

## 12.4 Log Levels
- `INFO`
- `WARNING`
- `ERROR`
- `DEBUG` for developer builds

## 12.5 Privacy
- Logs are local only in MVP
- No network transmission


## 13. Performance Considerations

## 13.1 Processing Goals
- Stable output quality over raw throughput
- Reasonably fast batch processing for common logo/icon workloads
- Responsive UI during preview and batch execution

## 13.2 Key Performance Strategies
- Use worker threads/processes for batch tasks
- Keep UI thread limited to rendering and state updates
- Reuse loaded preview image when only control values change
- Cache intermediate preview artifacts when practical
- Avoid tracing full-resolution previews when unnecessary for UI responsiveness
- Bound image size and worker count to avoid memory spikes

## 13.3 Large Image Handling
- Warn on very large inputs
- Offer resize-before-trace
- Enforce maximum safe preview size

## 13.4 Quality vs Speed Presets
Recommended presets:
- Fast
- Balanced
- High Quality

Preset impact:
- morphology intensity
- tracing smoothness
- simplification tolerance
- resize behavior

## 13.5 Stability Requirements
- No unbounded queue growth
- No memory leaks across long batches
- Temporary files cleaned up after completion/failure


## 14. Packaging for Windows

## 14.1 Delivery Format
- Primary:
  - Windows installer (`.exe`)
- Secondary:
  - portable zipped build if needed later

## 14.2 Packaging Tooling
- Application build:
  - PySide6 deployment tooling and/or Nuitka
- Installer:
  - Inno Setup

## 14.3 Packaging Requirements
- App runs fully offline after installation
- Bundle Python runtime and native dependencies
- Include OpenCV, Pillow, NumPy, and tracing backend binaries
- Ensure SVG preview dependencies are bundled

## 14.4 Windows Integration
- Start menu shortcut
- Desktop shortcut optional
- App icon
- File associations are out of scope for MVP

## 14.5 Upgrade Behavior
- Clean in-place upgrade path preferred
- Preserve user settings and logs across updates

## 14.6 Code Signing
- Not strictly required for MVP development
- Recommended before public distribution to reduce Windows SmartScreen friction


## 15. Functional Requirements Summary

## 15.1 Required MVP Features
- Select input folder
- Select output folder
- Scan supported image files
- Validate files and show statuses
- Preview selected file before export
- Adjustable tracing controls
- Batch export to SVG
- Preserve base filenames
- Offline operation
- Windows-first packaged desktop app

## 15.2 Required Controls
- Threshold
- Invert colors
- Min artifact area
- Smoothing strength
- Path simplification tolerance
- Resize before trace
- Ignore transparent pixels
- Merge nearby shapes
- Fill-only output
- Stroke output


## 16. Suggested Internal Interfaces

## 16.1 Core Data Types
- `AppSettings`
- `TraceSettings`
- `ImageAsset`
- `ValidationResult`
- `PreviewResult`
- `BatchJob`
- `BatchSummary`

## 16.2 Service Interfaces
- `ImageLoader`
- `ImageValidator`
- `PreprocessService`
- `TracingEngine`
- `PreviewService`
- `BatchService`
- `ExportService`
- `LogService`

## 16.3 Tracing Engine Contract
Input:
- raster path or in-memory binary mask
- trace settings

Output:
- SVG string or structured vector result

Errors:
- engine unavailable
- invalid input
- tracing failure


## 17. Acceptance Criteria for MVP

### Functional
- User can process a folder of supported images and receive `.svg` outputs in the output folder.
- Each valid input file generates one SVG with matching base filename.
- Preview output matches export behavior for the same settings.
- Invalid files do not crash the app.
- Batch can be cancelled safely.

### Quality
- Small speckles are removable through controls.
- Edges are visibly smoother than the source bitmap.
- Path count and node count are reduced relative to naive contour dumping.
- White-on-black input can be traced correctly using invert mode.

### UX
- Non-technical user can complete first export without reading documentation.
- Processing progress is always visible.
- Errors are understandable and actionable.

### Deployment
- Windows build installs and runs without requiring Python to be preinstalled.
- App works with no network connection.


## 18. Recommended MVP Defaults

- Threshold mode: Auto or `128`
- Invert colors: Off
- Min artifact area: `12 px`
- Smoothing strength: Medium
- Path simplification tolerance: Conservative
- Resize before trace: Off
- Ignore transparent pixels: On for PNG
- Merge nearby shapes: Off
- Fill-only output: On
- Stroke output: Off
- Overwrite existing SVGs: Skip


## 19. Post-MVP Extensions

- Recursive folder scanning
- Multiple output presets
- Side-by-side multi-file compare
- Potrace backend option
- SVG optimization/minification
- Command-line mode
- Watch folder automation
- More advanced alpha thresholds
- Hole-preservation controls
- Diagnostic quality scoring
