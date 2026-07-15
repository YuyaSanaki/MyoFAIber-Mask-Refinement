"""Muscle mask refinement viewer for macOS and Windows.

Usage:
  uv run python refine_masks.py            # empty viewer — drag & drop labels/images
  uv run python refine_masks.py --dialog   # optional file picker
  uv run python refine_masks.py --demo     # load sample files from repo root

Drag-and-drop of Ilastik 'Simple Segmentation' TIFFs is converted to a Labels
layer with the fixed CLASS_COLORS colormap (napari opens them as Image by default).
"""
import argparse
import os
import sys

# Must run before Qt/napari/vispy load.
# On Windows, OpenGL backend affects napari/vispy. If you see
# "self._finalCall" / "NoneType object is not callable", try another backend:
#   set QT_OPENGL=desktop   (NVIDIA/AMD GPU, local desktop)
#   set QT_OPENGL=angle     (Intel iGPU, some laptops)
#   set QT_OPENGL=software  (slowest; last resort / remote desktop)
if sys.platform == "win32":
    os.environ.setdefault("QT_OPENGL", "desktop")
    print(f"Windows OpenGL backend: QT_OPENGL={os.environ['QT_OPENGL']}")

from PIL import Image
import numpy as np
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QFileDialog
import napari
from napari.layers import Image as ImageLayer
from napari.layers import Labels
from napari.utils.colormaps import DirectLabelColormap

CLASS_COLORS = {
    None: [0.0, 0.0, 0.0, 0.0],  # unmapped labels
    0: [0.0, 0.0, 0.0, 0.0],  # background
    1: [0.706, 0.490, 0.741, 1.0],  # purple
    2: [0.996, 0.969, 0.110, 1.0],  # yellow
    3: [0.235, 0.106, 0.529, 1.0],  # dark purple
    4: [0.525, 0.565, 0.604, 1.0],  # gray
    5: [0.012, 0.306, 0.224, 1.0],  # dark green
    6: [0.259, 0.847, 0.651, 1.0],  # teal
    7: [0.278, 0.259, 0.345, 1.0],  # slate
}

DEMO_PAIRS = [
    ("TG_Sol_rgb.png", "TG_Sol_Simple Segmentation.tiff"),
    ("WT_Sol_rgb.png", "WT_Sol_Simple Segmentation.tiff"),
    ("WT_TA_rgb.png", "WT_TA_Simple Segmentation.tiff"),
]

# Guard against re-entry when we replace Image → Labels
_APPLYING_COLORMAP = False


def make_class_colormap():
    """Build a DirectLabelColormap (required by napari>=0.7)."""
    return DirectLabelColormap(color_dict=CLASS_COLORS)


def apply_class_colormap(layer: Labels) -> None:
    """Force DIRECT color mode with CLASS_COLORS on a Labels layer."""
    layer.colormap = make_class_colormap()
    print(
        f"Applied CLASS_COLORS to Labels '{layer.name}' "
        f"(color_mode={layer._color_mode})"
    )


def looks_like_label_mask(layer: ImageLayer) -> bool:
    """Detect Ilastik segmentation masks opened as Image layers."""
    name = (layer.name or "").lower()
    if "simple segmentation" in name or "segmentation" in name:
        return True

    data = np.asarray(layer.data)
    if data.ndim not in (2, 3):
        return False
    if data.ndim == 3 and min(data.shape) > 4:
        return False

    flat = data.reshape(-1)
    # Integer-valued with a small set of class IDs
    if not np.issubdtype(flat.dtype, np.integer):
        if np.issubdtype(flat.dtype, np.floating) and np.all(flat == np.round(flat)):
            pass
        else:
            return False

    uniq = np.unique(flat)
    return 1 < uniq.size <= 32 and uniq.min() >= 0 and uniq.max() < 256


def as_label_array(data) -> np.ndarray:
    data = np.asarray(data)
    if data.ndim == 3:
        if 1 in data.shape:
            data = np.squeeze(data)
        if data.ndim == 3:
            data = data[..., 0] if data.shape[-1] <= 4 else data[0]
    return data.astype(np.uint32, copy=False)


def convert_image_to_class_labels(viewer, image_layer: ImageLayer) -> Labels | None:
    """Replace a dropped Image mask with a Labels layer using CLASS_COLORS."""
    global _APPLYING_COLORMAP

    # Layer may already have been removed/replaced
    if image_layer not in viewer.layers:
        return None

    name = image_layer.name
    data = as_label_array(image_layer.data)
    idx = viewer.layers.index(image_layer)

    _APPLYING_COLORMAP = True
    try:
        viewer.layers.remove(image_layer)
        layer = viewer.add_labels(
            data,
            name=name,
            colormap=make_class_colormap(),
        )
        viewer.layers.move(viewer.layers.index(layer), min(idx, len(viewer.layers) - 1))
        apply_class_colormap(layer)
        print(
            f"Converted Image → Labels '{name}': "
            f"unique={np.unique(data).tolist()}"
        )
        return layer
    finally:
        _APPLYING_COLORMAP = False


def on_layer_inserted(event, viewer):
    """Apply CLASS_COLORS to Labels / convert dropped segmentation Images."""
    global _APPLYING_COLORMAP
    if _APPLYING_COLORMAP:
        return

    layer = event.value
    if isinstance(layer, Labels):
        # Defer so napari finishes inserting/selecting first
        QTimer.singleShot(0, lambda lyr=layer: apply_class_colormap(lyr))
        return

    if isinstance(layer, ImageLayer) and looks_like_label_mask(layer):
        # Must defer: converting during insert breaks layer selection
        QTimer.singleShot(
            0, lambda lyr=layer: convert_image_to_class_labels(viewer, lyr)
        )


def install_colormap_hook(viewer):
    """Apply CLASS_COLORS to Labels layers added any way (incl. drag-and-drop)."""
    viewer.layers.events.inserted.connect(
        lambda event: on_layer_inserted(event, viewer)
    )
    print(
        "Ready: drag-and-drop label masks (e.g. '*_Simple Segmentation.tiff').\n"
        "They will be opened as Labels with CLASS_COLORS."
    )


def spatial_shape(arr):
    """Return (H, W) for 2D / HWC / CHW arrays."""
    if arr.ndim == 2:
        return arr.shape
    if arr.ndim == 3:
        if arr.shape[-1] <= 4:
            return arr.shape[:2]
        if arr.shape[0] <= 4:
            return arr.shape[1:]
        return arr.shape[-2:]
    raise ValueError(f"Unsupported array shape: {arr.shape}")


def strip_image_suffix(name):
    """Strip common image suffixes without mangling '.tiff' via '.tif'."""
    lower = name.lower()
    for suffix in ("_rgb.png", ".tiff", ".tif", ".png", ".jpg", ".jpeg"):
        if lower.endswith(suffix):
            return name[: len(name) - len(suffix)]
    return os.path.splitext(name)[0]


def is_segmentation_file(path):
    return "simple segmentation" in os.path.basename(path).lower()


def load_mask_array(mask_path):
    """Load a label mask as a 2D integer array (prefer tifffile over Pillow)."""
    try:
        import tifffile

        mask = tifffile.imread(mask_path)
    except Exception:
        mask = np.array(Image.open(mask_path))
    return as_label_array(mask)


def add_class_labels(viewer, mask, name):
    """Add a labels layer with the fixed class colormap applied."""
    mask = as_label_array(mask)
    layer = viewer.add_labels(mask, name=name, colormap=make_class_colormap())
    apply_class_colormap(layer)
    print(f"Labels '{name}': unique={np.unique(mask).tolist()}")
    return layer


def add_multichannel_image(viewer, img, img_name):
    """Handle 1ch / multi-channel images correctly in napari."""
    print("image shape:", img.shape, img.dtype)

    if img.ndim == 2:
        viewer.add_image(img, name=img_name)
    elif img.ndim == 3:
        if img.shape[0] <= 4:
            viewer.add_image(img, name=img_name, channel_axis=0)
        elif img.shape[-1] <= 4:
            viewer.add_image(img, name=img_name, channel_axis=-1)
        else:
            viewer.add_image(img, name=img_name)
    else:
        print("Unsupported image shape")


def find_mask_path(img_path):
    """Resolve the Ilastik Simple Segmentation mask next to an image."""
    directory = os.path.dirname(img_path)
    img_name = os.path.basename(img_path)
    base_name = strip_image_suffix(img_name)
    candidates = [
        f"{base_name}_Simple Segmentation.tiff",
        f"{base_name}_Simple Segmentation.tif",
        f"{base_name}_simple_segmentation.tiff",
        f"{base_name}_simple_segmentation.tif",
    ]
    for name in candidates:
        path = os.path.join(directory, name)
        if os.path.exists(path):
            return path, name
    return None, candidates[0]


def load_image_and_mask(viewer, img_path):
    """Load image + corresponding mask safely."""
    img_name = os.path.basename(img_path)

    if is_segmentation_file(img_path):
        mask = load_mask_array(img_path)
        add_class_labels(viewer, mask, img_name)
        return

    img = np.array(Image.open(img_path))
    add_multichannel_image(viewer, img, img_name)

    mask_path, mask_name = find_mask_path(img_path)
    if mask_path is None:
        print(f"Warning: Mask not found next to {img_path} (looked for {mask_name})")
        return

    mask = load_mask_array(mask_path)
    img_hw = spatial_shape(img)
    if mask.shape != img_hw:
        print("shape mismatch!", img_hw, mask.shape)
        return

    add_class_labels(viewer, mask, mask_name)


def run_demo(viewer):
    """Load hardcoded sample image/mask pairs from the repo root."""
    print(f"Demo mode (napari {napari.__version__})")
    for img_path, mask_path in DEMO_PAIRS:
        if os.path.exists(img_path) and os.path.exists(mask_path):
            img = np.array(Image.open(img_path))
            viewer.add_image(img, name=img_path)
            mask = load_mask_array(mask_path)
            add_class_labels(viewer, mask, mask_path)
        else:
            print(f"Skipping missing pair: {img_path}, {mask_path}")

    print("\n--- LABEL GUIDE ---")
    print(
        "0: Background, 1: purple, 2: yellow, 3: dark purple, "
        "4: gray, 5: dark green, 6: teal, 7: slate"
    )


def run_file_picker(viewer):
    """Open a file dialog and load selected images with their masks."""
    print("Opening file dialog...")
    files, _ = QFileDialog.getOpenFileNames(
        None,
        "Select Raw Images, RGB Composites, or Segmentation Masks",
        "",
        "Images (*.tif *.tiff *.png *.jpg)",
    )

    if files:
        for path in files:
            load_image_and_mask(viewer, path)
    else:
        print("No files selected — drag-and-drop into the viewer instead.")


def main():
    parser = argparse.ArgumentParser(description="Refine muscle segmentation masks in Napari.")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Load sample image/mask pairs from the repo root.",
    )
    parser.add_argument(
        "--dialog",
        action="store_true",
        help="Open a file picker on launch (otherwise drag-and-drop into the empty viewer).",
    )
    args = parser.parse_args()

    print(f"Platform: {sys.platform}")
    print(f"napari {napari.__version__}")
    viewer = napari.Viewer()
    install_colormap_hook(viewer)

    if args.demo:
        run_demo(viewer)
    elif args.dialog:
        run_file_picker(viewer)
    else:
        print("Drag confocal images and/or '*_Simple Segmentation.tiff' into the viewer.")

    napari.run()


if __name__ == "__main__":
    main()
