# Muscle Mask Refinement Workflow

This repository contains tools to refine Ilastik-generated segmentation masks for muscle fiber analysis. It uses **Napari** for interactive pixel-level refinement and **uv** for reproducible environment management.

## 🚀 Getting Started

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

**macOS or Windows** — opens a file picker to load images and their Ilastik masks:
```bash
uv sync
uv run python refine_masks_viewer.py
```

**Demo mode** (loads hardcoded sample files in the repo root):
```bash
uv run python refine_masks.py
```

> **Note:** `pyqt5-qt5` publishes different wheels per platform (Windows uses
> `5.15.2`; Apple Silicon Mac uses `5.15.19`). After pulling, always run
> `uv sync` before launching the viewer.

---

## 🎨 Color Legend (Custom Labels)

The labels are pre-configured with the following mapping:

| ID | Label Name | Color | Description |
|:---|:---|:---|:---|
| **0** | **Uncertain** | 🟢 Soft Cyan | Muted Teal for ambiguous areas |
| **1** | **Background**| ⚪ Light Gray | Non-muscle/extracellular space |
| **2** | **Type IIB**  | 🌸 Soft Magenta| Orchid color for IIB fibers |
| **3** | **Type I**    | 🌿 Soft Green | Sage color for Type I fibers |
| **4** | **Membrane**  | 🔵 Steel Blue | Fiber boundaries/sarcolemma |
| **5** | **Type IIA**  | 🍎 Soft Red   | Salmon/Coral for IIA fibers |
| **6** | **Type IIX**  | ⚫ Soft Black | Charcoal for IIX fibers |
| **7** | **Vessel**    | 🟡 Soft Gold  | Ochre for blood vessels |

---

## ⚡ Efficient Refinement Guide

To work quickly at "pixel resolution," use these keyboard shortcuts:

### 🛠 Tools
- **`L` (Eyedropper)**: Click a color on the mask to quickly switch to that label class.
- **`P` (Paint)**: Switch to the brush tool.
- **`E` (Erase)**: Switch to the eraser tool (paints label 0).
- **`[` / `]`**: Decrease / Increase brush size.
- **`Z` / `Shift + Z`**: Pan and Zoom.

### 👁 Visualization
- **`V`**: Toggle mask visibility (on/off) to check the raw image alignment.
- **Opacity Slider**: Use the slider in the layer list (bottom left) to "see through" the mask while painting.
- **`Ctrl + F`**: Toggle full screen.

### 💾 Saving Your Work
1. **Right-click** the mask layer name (e.g., `WT_Sol_Simple Segmentation.tiff`) in the layer list.
2. Select **"Save Selected Layer(s)..."**.
3. **Important**: Save as a new file (e.g., `WT_Sol_Refined.tiff`) to keep your original Ilastik output as a backup.

---

## 🛠 Image Preparation (Reference)
The raw 4-channel confocal stacks were converted to RGB using:
- **Magenta**: Channel 1 (Red + Blue)
- **Green**: Channel 2
- **Blue**: Channel 3
- **Red**: Channel 4

If you need to regenerate these, run:
```bash
uv run python3 make_rgb.py
```
