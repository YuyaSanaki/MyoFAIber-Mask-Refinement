# MyoFAIber Mask Refinement

Refine MyoFAIber `*_pred` segmentation masks in **Napari** for fine-tuning (FT) datasets, with a reproducible **uv** environment.

One script (`refine_masks.py`) works on both **macOS** and **Windows** (Windows OpenGL defaults are applied automatically).

## Workflow

1. Run MyoFAIber inference → get `*_pred` label maps.
2. `uv run python refine_masks.py`
3. Drag in **either** the image or the `*_pred` mask. The other file in the same folder opens automatically. A 4-channel TIFF is shown as Ch1 magenta / Ch2 green / Ch3 blue / Ch4 red.
4. Press `0`–`7` (or click the **Classes** panel) and paint.
5. Press `Ctrl+S` (`⌘S` on macOS). The original `*_pred` stays as a backup. A uint8 `*_refined.tif` is written beside it.

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

This opens an empty Napari window. **Drag-and-drop** either the confocal image or the MyoFAIber `*_pred` mask. The matching file next to it opens as well:

- image `TG_Sol.tif` or `TG_Sol_rgb.png` → `TG_Sol_pred.tiff` / `.tif` / `.png`
- mask `TG_Sol_pred.tiff` → `TG_Sol_rgb.png` if it exists, otherwise `TG_Sol.tif`

Napari normally opens `*_pred.tiff` as an Image (default grayscale colormap). This script converts those files to a **Labels** layer with the fixed `CLASS_COLORS` colormap. A raw 4-channel TIFF is replaced by the RGB composite used for refinement (Ch1 magenta, Ch2 green, Ch3 blue, Ch4 red), so you do not need ImageJ or `make_rgb.py` first.

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

Pixel values in `*_pred.tif` / refined masks are **class IDs** (same as Fine-tune Target and the [MyoFAIber](https://github.com/YuyaSanaki/MyoFAIber) WebUI). Napari paint colors are `CLASS_COLORS` in `refine_masks.py`. Type I and Type IIX are lightened so they stay distinct while painting.

| ID | Class | Fiber / structure | Stain → RGB composite | Napari paint color |
|:---|:---|:---|:---|:---|
| **0** | Uncertain | Fold, artifact, or unclear region | — | Transparent (eraser paints **0**) |
| **1** | Background | Non-fiber / interstitial space | — | <img alt="#E5DDB2" src="https://img.shields.io/badge/-%23E5DDB2?style=flat-square&labelColor=%23E5DDB2&color=%23E5DDB2" height="16"/> Beige (#E5DDB2) |
| **2** | Type IIB | Fast glycolytic fiber | <img alt="#FF00FF" src="https://img.shields.io/badge/-%23FF00FF?style=flat-square&labelColor=%23FF00FF&color=%23FF00FF" height="16"/> Ch1 → Magenta (#FF00FF) | <img alt="#7B8E0F" src="https://img.shields.io/badge/-%237B8E0F?style=flat-square&labelColor=%237B8E0F&color=%237B8E0F" height="16"/> Olive green (#7B8E0F) |
| **3** | Type I | Slow oxidative fiber | <img alt="#00FF00" src="https://img.shields.io/badge/-%2300FF00?style=flat-square&labelColor=%2300FF00&color=%2300FF00" height="16"/> Ch2 → Green (#00FF00) | <img alt="#FAFAB2" src="https://img.shields.io/badge/-%23FAFAB2?style=flat-square&labelColor=%23FAFAB2&color=%23FAFAB2" height="16"/> Pale yellow (#FAFAB2) |
| **4** | Membrane | Sarcolemma (e.g. WGA) | <img alt="#0000FF" src="https://img.shields.io/badge/-%230000FF?style=flat-square&labelColor=%230000FF&color=%230000FF" height="16"/> Ch3 → Blue (#0000FF) | <img alt="#B00C3F" src="https://img.shields.io/badge/-%23B00C3F?style=flat-square&labelColor=%23B00C3F&color=%23B00C3F" height="16"/> Pink (#B00C3F) |
| **5** | Type IIA | Fast oxidative fiber | <img alt="#FF0000" src="https://img.shields.io/badge/-%23FF0000?style=flat-square&labelColor=%23FF0000&color=%23FF0000" height="16"/> Ch4 → Red (#FF0000) | <img alt="#5CB7DE" src="https://img.shields.io/badge/-%235CB7DE?style=flat-square&labelColor=%235CB7DE&color=%235CB7DE" height="16"/> Blue (#5CB7DE) |
| **6** | Type IIX | Fiber type inferred from no type stain | No dedicated stain (inferred) | <img alt="#FAB2FA" src="https://img.shields.io/badge/-%23FAB2FA?style=flat-square&labelColor=%23FAB2FA&color=%23FAB2FA" height="16"/> Bright magenta (#FAB2FA) |
| **7** | Vessel | Blood vessel | — | <img alt="#86909A" src="https://img.shields.io/badge/-%2386909A?style=flat-square&labelColor=%2386909A&color=%2386909A" height="16"/> Gray (#86909A) |

RGB composite channels: **Ch1 Magenta · Ch2 Green · Ch3 Blue · Ch4 Red**.

Label values are used as-is (no `+1` shift). Eraser paints label **0** (transparent / Uncertain).

---

## Efficient Refinement Guide

### Pick a class, then paint
- **Classes panel** or **`0`–`7`**: select that class and start the brush. `0` is Uncertain, `1` is Background. These keys do **not** switch Napari tools.
- **`P`**: brush. **`E`**: eraser. The eraser paints **0 Uncertain**, not Background.
- **`L`**: eyedropper. **`F`**: fill. **`Z`**: pan (zoom with the scroll wheel).
- **`[` / `]`**: smaller / larger brush.
- **`V`**: hide or show the mask to check alignment. Opacity slider fades it while painting.

`M` does not create a new class. Labels stay in `0`–`7`.

### Saving for FT
Press **`Ctrl+S`** (**`⌘S`** on macOS).

`WT_Sol_pred.tiff` is left untouched. The refined mask is written next to it as uint8 `WT_Sol_refined.tif`. Press the shortcut again to overwrite that refined file.

---

## Image Preparation (Reference)

Dropping a 4-channel TIFF builds the same composite as `make_rgb.py`:

- **Magenta**: Channel 1 (added into red and blue)
- **Green**: Channel 2
- **Blue**: Channel 3
- **Red**: Channel 4

`ImageJmacro/setLUT.ijm` is an older palette and is not the refinement legend. To write the composite out as a PNG for the bundled sample names:
```bash
uv run python make_rgb.py
```
