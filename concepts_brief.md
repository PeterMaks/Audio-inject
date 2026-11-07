# Visual Documentation & Desktop Showcase in README

* **Author:** PeterMaks
* **Date:** 2026-11-07

## Overview

Update `README.md` to incorporate the Tauri v2 desktop application screenshots as a compact gallery, replacing the existing ASCII wireframe schematic. The showcase will feature `Lib.png` (populated library) and exclude the empty-state `Library.png`, providing direct visual reference for the application's core capabilities.

## Analysis

### Decided Baseline
* **Layout**: Compact gallery (side-by-side / 2-column format) to minimize vertical scroll impact while presenting high-density visual information.
* **Asset Selection**: Use `Lib.png` (showing populated state with 1,881 tracks, format badges, and artwork dimensions). Exclude `Library.png` (empty drop target) to avoid redundancy.
* **Schematic Replacement**: Remove the ASCII block layout diagram (lines 434–447) in favor of the screenshot gallery.

### Image Inventory for the Compact Gallery
1. `images/Lib.png`: Populated track library with 1,881 tracks, artwork resolution indicators, status tags, and pagination.
2. `images/Injector.png`: Waterfall injector showing the 6-provider signal chain (Chromaprint -> MusicBrainz -> Apple Music -> Deezer -> Spotify -> Songlink) and confidence slider.
3. `images/Inspector.png`: Track inspector view with slide-out Vorbis/ID3 tag drawer and acoustic fingerprint trigger.
4. `images/Converter.png`: WAV to FLAC conversion studio with compression sliders and auto-tagging options.
5. `images/Settings.png`: API credentials and engine parameters configuration.

### Remaining Edge Cases & Trade-Offs
* **Hero Placement**: Should `Lib.png` appear only within the Desktop Application section, or also at the very top of `README.md` (below the badge row) as a primary visual hook?
* **Table Column Symmetry**: With 5 images, a 2-column table will have an unbalanced final row (2 + 2 + 1) unless one image is promoted to a full-width header/hero or paired with an architectural summary.
* **Image Sizing on GitHub**: Raw 1920x1080 screenshots in a standard markdown table can render very small or awkwardly cropped depending on the GitHub viewport unless HTML `<img>` tags with explicit width attributes (e.g., `<img width="48%" />`) or standard percentage widths are used.

## Goals vs. Non-Goals

### In-Scope Goals
* Replace lines 434–447 in `README.md` with a balanced compact gallery.
* Display the 5 selected screenshots (`Lib.png`, `Injector.png`, `Inspector.png`, `Converter.png`, `Settings.png`) with clean, descriptive captions.
* Ensure markdown/HTML formatting renders cleanly across GitHub light and dark modes.

### Out-of-Scope Non-Goals
* Modifying application source code or UI styling.
* Regenerating screenshots.
* Altering CLI command reference or provider documentation.

## Alternatives Weighed

* **Raw Markdown Table (`| Image 1 | Image 2 |`)**:
  * *Trade-off*: Native markdown, but lacks sizing control on GitHub mobile and narrow viewports.
* **HTML Table with Controlled Widths (`<table width="100%">`)**:
  * *Trade-off*: Precise thumbnail sizing and side-by-side alignment, but slightly more verbose syntax.
* **Full-Width Hero + 2x2 Grid**: `Lib.png` displayed at full width as the primary desktop overview, followed by a 2x2 grid for the four secondary features (`Injector`, `Inspector`, `Converter`, `Settings`).
  * *Advantage*: Resolves the odd-numbered (5 images) asymmetry cleanly.

## Key Decisions & Staging for Next Steps

* Confirm hero placement (Hero + 2x2 grid vs. strict 5-image gallery).
* Confirm markdown vs. HTML table approach for image sizing.
