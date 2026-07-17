# MyoFAIber Mask Refinement

Refine MyoFAIber `*_pred` segmentation masks in **Napari** for fine-tuning (FT) datasets, with a reproducible **uv** environment.

One script (`refine_masks.py`) works on both **macOS** and **Windows** (Windows OpenGL defaults are applied automatically).

## Workflow

1. Run MyoFAIber inference → get `*_pred` label maps.
2. Open image + `_pred` here and correct boundaries / class IDs.
3. Save refined masks as FT training labels (keep the original `_pred` as backup).

## Getting Started

### 1. Prerequisites

- **Python 3.11–3.13** (3.12 recommended; see `.python-version`)
- **uv** package manager

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Launch the Refinement Viewer

```bash
uv sync
uv run python refine_masks.py
```

This opens an empty Napari window. **Drag-and-drop** your confocal image and/or MyoFAIber `*_pred` mask into it.

Napari normally opens `*_pred.tiff` as an Image (default grayscale colormap). This script detects those drops and converts them to a **Labels** layer with the fixed `CLASS_COLORS` colormap.

When you drop an image, the viewer also looks for a sibling mask:

- `{stem}_pred.tiff` / `{stem}_pred.tif` / `{stem}_pred.png`

Optional file picker:
```bash
uv run python refine_masks.py --dialog
```

**Demo mode** (loads sample files from the repo root):
```bash
uv run python refine_masks.py --demo
```

> **Note:** `pyqt5-qt5` publishes different wheels per platform (Windows uses
> `5.15.2`; Apple Silicon Mac uses `5.15.19`). After pulling, always run
> `uv sync` before launching the viewer.

### Windows: `Could not find the Qt platform plugin "windows"`

If launching fails immediately with:

```
qt.qpa.plugin: Could not find the Qt platform plugin "windows" in ""
This application failed to start because no Qt platform plugin could be
initialized. Reinstalling the application may fix this problem.
```

Qt can't find `qwindows.dll`. This is usually caused by a **conflicting Qt**
on your system (a base **conda** env, an **OpenCV/`cv2`** wheel, or another Qt
app on `PATH`) whose environment variables hijack plugin discovery.

`refine_masks.py` now auto-repoints Qt at PyQt5's own plugins on startup, so in
most cases just re-run it:

```powershell
uv sync
uv run python refine_masks.py
```

If it still fails, run from a **clean shell** (not an activated `conda`
environment) and clear stale variables, then retry:

```powershell
Remove-Item Env:QT_QPA_PLATFORM_PLUGIN_PATH -ErrorAction SilentlyContinue
Remove-Item Env:QT_PLUGIN_PATH -ErrorAction SilentlyContinue
uv run python refine_masks.py
```

As a last resort, reinstall the Windows Qt wheel:

```powershell
uv sync --reinstall-package pyqt5-qt5
```

### Windows: OpenGL / `self._finalCall` error

If napari crashes with something like:

```
File "...OpenGL\latebind.py", line 43, in __call__
    return self._finalCall( *args, **named )
TypeError: 'NoneType' object is not callable
```

that is a **graphics / OpenGL** problem, not a mask-loading bug. Try these in
PowerShell (one at a time):

```powershell
# 1. Desktop GPU (NVIDIA/AMD) — default in refine_masks.py
$env:QT_OPENGL="desktop"
uv run python refine_masks.py

# 2. Intel integrated GPU / some laptops
$env:QT_OPENGL="angle"
uv run python refine_masks.py

# 3. Software rendering (slow, but works when GPU/remote desktop fails)
$env:QT_OPENGL="software"
uv run python refine_masks.py
```

Also check:
- Run **locally** on the PC (not Remote Desktop / RDP) if possible
- Update your **GPU driver**
- Use **Python 3.12** (`uv python pin 3.12` then `uv sync`)

---

## Class Legend (same as MyoFAIber WebUI)

Pixel values in `*_pred.tif` / refined masks are **class IDs** (same as Fine-tune Target). Napari uses the fixed colormap `CLASS_COLORS` in `refine_masks.py` (kept in sync with [MyoFAIber](https://github.com/YuyaSanaki/MyoFAIber) WebUI).

| ID | Class | Fiber / structure | Stain → RGB composite | Napari paint color |
|:---|:---|:---|:---|:---|
| **0** | Uncertain | Fold, artifact, or unclear region | — | Transparent (eraser paints **0**) |
| **1** | Background | Non-fiber / interstitial space | — | <img alt="#B47DBD" src="https://img.shields.io/badge/-%23B47DBD?style=flat-square&labelColor=%23B47DBD&color=%23B47DBD" height="16"/> Purple (#B47DBD) |
| **2** | Type IIB | Fast glycolytic fiber | <img alt="#FF00FF" src="https://img.shields.io/badge/-%23FF00FF?style=flat-square&labelColor=%23FF00FF&color=%23FF00FF" height="16"/> Ch1 → Magenta (#FF00FF) | <img alt="#FEF71C" src="https://img.shields.io/badge/-%23FEF71C?style=flat-square&labelColor=%23FEF71C&color=%23FEF71C" height="16"/> Yellow (#FEF71C) |
| **3** | Type I | Slow oxidative fiber | <img alt="#00FF00" src="https://img.shields.io/badge/-%2300FF00?style=flat-square&labelColor=%2300FF00&color=%2300FF00" height="16"/> Ch2 → Green (#00FF00) | <img alt="#3C1B87" src="https://img.shields.io/badge/-%233C1B87?style=flat-square&labelColor=%233C1B87&color=%233C1B87" height="16"/> Dark purple (#3C1B87) |
| **4** | Membrane | Sarcolemma (e.g. WGA) | <img alt="#0000FF" src="https://img.shields.io/badge/-%230000FF?style=flat-square&labelColor=%230000FF&color=%230000FF" height="16"/> Ch3 → Blue (#0000FF) | <img alt="#86909A" src="https://img.shields.io/badge/-%2386909A?style=flat-square&labelColor=%2386909A&color=%2386909A" height="16"/> Gray (#86909A) |
| **5** | Type IIA | Fast oxidative fiber | <img alt="#FF0000" src="https://img.shields.io/badge/-%23FF0000?style=flat-square&labelColor=%23FF0000&color=%23FF0000" height="16"/> Ch4 → Red (#FF0000) | <img alt="#034E39" src="https://img.shields.io/badge/-%23034E39?style=flat-square&labelColor=%23034E39&color=%23034E39" height="16"/> Dark green (#034E39) |
| **6** | Type IIX | Fiber type inferred from no type stain | No dedicated stain (inferred) | <img alt="#42D8A6" src="https://img.shields.io/badge/-%2342D8A6?style=flat-square&labelColor=%2342D8A6&color=%2342D8A6" height="16"/> Teal (#42D8A6) |
| **7** | Vessel | Blood vessel | — | <img alt="#474258" src="https://img.shields.io/badge/-%23474258?style=flat-square&labelColor=%23474258&color=%23474258" height="16"/> Slate (#474258) |

RGB composite channels: **Ch1 Magenta · Ch2 Green · Ch3 Blue · Ch4 Red**.

Label values are used as-is (no `+1` shift). Eraser paints label **0** (transparent / Uncertain).

---

## Efficient Refinement Guide

### Tools
- **`L` (Eyedropper)**: Click a color on the mask to switch to that label class.
- **`P` (Paint)**: Switch to the brush tool.
- **`E` (Erase)**: Eraser (paints label 0).
- **`[` / `]`**: Decrease / increase brush size.
- **`Z` / `Shift + Z`**: Pan and zoom.

### Visualization
- **`V`**: Toggle mask visibility to check raw image alignment.
- **Opacity slider**: In the layer list, fade the mask while painting.
- **`Ctrl + F`**: Toggle full screen.

### Saving for FT
1. Right-click the mask layer name (e.g. `WT_Sol_pred.tiff`) in the layer list.
2. Select **Save Selected Layer(s)...**.
3. Save as a **new** file (e.g. `WT_Sol_refined.tiff`) so the original MyoFAIber `_pred` stays as a backup for comparison / re-export.

---

## Image Preparation (Reference)

Raw 4-channel confocal stacks were converted to RGB using:
- **Magenta**: Channel 1 (Red + Blue)
- **Green**: Channel 2
- **Blue**: Channel 3
- **Red**: Channel 4

To regenerate RGB composites:
```bash
uv run python make_rgb.py
```
