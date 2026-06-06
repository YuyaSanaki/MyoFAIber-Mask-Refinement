import os
import sys

# Must run before Qt/napari/vispy load. ANGLE maps GL to D3D and often fixes
# GL_INVALID_ENUM on Windows (Intel iGPU, remote desktop). Override with
# QT_OPENGL=software or QT_OPENGL=desktop if needed.
if sys.platform == "win32":
    os.environ.setdefault("QT_OPENGL", "angle")

from PIL import Image
import numpy as np
from qtpy.QtWidgets import QFileDialog
import napari

# Custom color map (Shifted by +1 to make Label 0 transparent)
CUSTOM_COLORS = {
    1: [100/255, 200/255, 210/255, 1.0],  # Uncertain
    2: [230/255, 230/255, 230/255, 1.0],  # Background
    3: [210/255, 130/255, 210/255, 1.0],  # TypeIIB
    4: [130/255, 190/255, 130/255, 1.0],  # TypeI
    5: [70/255, 130/255, 180/255, 1.0],   # Membrane
    6: [230/255, 115/255, 115/255, 1.0],  # TypeIIA
    7: [50/255, 50/255, 50/255, 1.0],     # TypeIIX
    8: [220/255, 190/255, 80/255, 1.0],    # Vessel
}


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


def load_image_and_mask(viewer, img_path):
    """Load image + corresponding mask safely."""
    img_name = os.path.basename(img_path)
    img = np.array(Image.open(img_path))

    add_multichannel_image(viewer, img, img_name)

    base_name = img_name.replace("_rgb.png", "").replace(".tif", "")
    mask_name = f"{base_name}_Simple Segmentation.tiff"
    mask_path = os.path.join(os.path.dirname(img_path), mask_name)

    if not os.path.exists(mask_path):
        print(f"Warning: Mask not found at {mask_path}")
        return

    mask = np.array(Image.open(mask_path))
    print("mask shape:", mask.shape, mask.dtype)

    if mask.ndim == 3:
        mask = mask.squeeze()

    if img.ndim == 3:
        img_shape_2d = img.shape[-2:]
    else:
        img_shape_2d = img.shape

    if mask.shape != img_shape_2d:
        print("shape mismatch!", img_shape_2d, mask.shape)
        return

    mask = mask.astype(np.int32)
    shifted_mask = mask + 1
    print("mask min/max:", shifted_mask.min(), shifted_mask.max())

    layer = viewer.add_labels(shifted_mask, name=mask_name)
    layer.color = CUSTOM_COLORS
    print(f"Loaded mask: {mask_name}")


def main():
    viewer = napari.Viewer()

    print("Opening file dialog...")
    files, _ = QFileDialog.getOpenFileNames(
        None,
        "Select Raw Images or RGB Composites",
        "",
        "Images (*.tif *.tiff *.png *.jpg)",
    )

    if files:
        for path in files:
            load_image_and_mask(viewer, path)
    else:
        print("No files selected.")

    napari.run()


if __name__ == "__main__":
    main()
