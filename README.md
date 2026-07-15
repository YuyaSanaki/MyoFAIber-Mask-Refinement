# Muscle Mask Refinement Workflow

Refine Ilastik-generated segmentation masks for muscle fiber analysis in **Napari**, with a reproducible **uv** environment.

One script (`refine_masks.py`) works on both **macOS** and **Windows** (Windows OpenGL defaults are applied automatically).

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

This opens an empty Napari window. **Drag-and-drop** your confocal image and/or Ilastik label mask into it.

Napari normally opens `*_Simple Segmentation.tiff` as an Image (default grayscale colormap). This script detects those drops and converts them to a **Labels** layer with the fixed `CLASS_COLORS` colormap.

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

## Color Legend (Fixed Labels)

Napari uses a fixed colormap (`CLASS_COLORS` in `refine_masks.py`):

| ID | Color | RGBA |
|:---|:---|:---|
| **0** | Background (transparent) | `0.0, 0.0, 0.0, 0.0` |
| **1** | Purple | `0.706, 0.490, 0.741, 1.0` |
| **2** | Yellow | `0.996, 0.969, 0.110, 1.0` |
| **3** | Dark purple | `0.235, 0.106, 0.529, 1.0` |
| **4** | Gray | `0.525, 0.565, 0.604, 1.0` |
| **5** | Dark green | `0.012, 0.306, 0.224, 1.0` |
| **6** | Teal | `0.259, 0.847, 0.651, 1.0` |
| **7** | Slate | `0.278, 0.259, 0.345, 1.0` |

Label values are used as-is (no `+1` shift). Eraser paints label **0** (transparent background).

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

### Saving your work
1. Right-click the mask layer name (e.g. `WT_Sol_Simple Segmentation.tiff`) in the layer list.
2. Select **Save Selected Layer(s)...**.
3. Save as a **new** file (e.g. `WT_Sol_Refined.tiff`) so the original Ilastik output stays as a backup.

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
