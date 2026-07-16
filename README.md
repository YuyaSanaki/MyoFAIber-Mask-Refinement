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
| **1** | Background | Non-fiber / interstitial space | — | <span style="display:inline-block;width:1.1em;height:1.1em;border:1px solid #666;background:#B47DBD;vertical-align:middle;"></span> Purple (`#B47DBD`) |
| **2** | Type IIB | Fast glycolytic fiber | <span style="display:inline-block;width:1.1em;height:1.1em;border:1px solid #666;background:#FF00FF;vertical-align:middle;"></span> Ch1 → Magenta | <span style="display:inline-block;width:1.1em;height:1.1em;border:1px solid #666;background:#FEF71C;vertical-align:middle;"></span> Yellow (`#FEF71C`) |
| **3** | Type I | Slow oxidative fiber | <span style="display:inline-block;width:1.1em;height:1.1em;border:1px solid #666;background:#00FF00;vertical-align:middle;"></span> Ch2 → Green | <span style="display:inline-block;width:1.1em;height:1.1em;border:1px solid #666;background:#3C1B87;vertical-align:middle;"></span> Dark purple (`#3C1B87`) |
| **4** | Membrane | Sarcolemma (e.g. WGA) | <span style="display:inline-block;width:1.1em;height:1.1em;border:1px solid #666;background:#0000FF;vertical-align:middle;"></span> Ch3 → Blue | <span style="display:inline-block;width:1.1em;height:1.1em;border:1px solid #666;background:#86909A;vertical-align:middle;"></span> Gray (`#86909A`) |
| **5** | Type IIA | Fast oxidative fiber | <span style="display:inline-block;width:1.1em;height:1.1em;border:1px solid #666;background:#FF0000;vertical-align:middle;"></span> Ch4 → Red | <span style="display:inline-block;width:1.1em;height:1.1em;border:1px solid #666;background:#034E39;vertical-align:middle;"></span> Dark green (`#034E39`) |
| **6** | Type IIX | Fiber type inferred from no type stain | No dedicated stain (inferred) | <span style="display:inline-block;width:1.1em;height:1.1em;border:1px solid #666;background:#42D8A6;vertical-align:middle;"></span> Teal (`#42D8A6`) |
| **7** | Vessel | Blood vessel | — | <span style="display:inline-block;width:1.1em;height:1.1em;border:1px solid #666;background:#474258;vertical-align:middle;"></span> Slate (`#474258`) |

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
