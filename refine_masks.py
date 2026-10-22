"""MyoFAIber mask refinement viewer for macOS and Windows.

Refine MyoFAIber ``*_pred`` label maps in Napari for fine-tuning (FT) datasets.

Usage:
  uv run python refine_masks.py            # empty viewer — drag & drop
  uv run python refine_masks.py --dialog   # optional file picker
  uv run python refine_masks.py --demo     # load sample files from repo root

Drop either the image or the ``*_pred`` mask. The file beside it opens too.
A 4-channel TIFF is shown as the stain composite (Ch1 magenta, Ch2 green,
Ch3 blue, Ch4 red). Keys ``0``–``7`` select that class and start the brush.
``Ctrl+S`` (macOS ``⌘S``) writes ``*_refined.tif`` next to the original
``*_pred``, which is left unchanged.
"""
import argparse
import glob
import importlib.util
import os
import sys
import weakref
from contextlib import nullcontext
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname


def _fix_windows_qt_plugin_path():
    """Point Qt at PyQt5's own ``platforms`` plugins before Qt loads.

    Fixes the classic Windows error::

        This application failed to start because no Qt platform plugin could
        be initialized. ... Could not find the Qt platform plugin "windows"
        in ""

    Root cause is usually a conflicting Qt on the system (a base conda env, an
    OpenCV/`cv2` wheel, or another Qt app on ``PATH``) whose plugin variables
    hijack plugin discovery so ``qwindows.dll`` is never found. We clear those
    stale variables and repoint them at the PyQt5 install we actually run with.
    """
    spec = importlib.util.find_spec("PyQt5")
    if spec is None or not spec.submodule_search_locations:
        return  # PyQt5 not importable here; nothing we can do.

    pyqt5_dir = spec.submodule_search_locations[0]
    # PyQt5 ships plugins under Qt5/plugins (5.15.x) or Qt/plugins (older).
    candidates = [
        os.path.join(pyqt5_dir, "Qt5", "plugins"),
        os.path.join(pyqt5_dir, "Qt", "plugins"),
    ]
    plugins_dir = next((p for p in candidates if os.path.isdir(p)), None)
    if plugins_dir is None:
        return

    platforms_dir = os.path.join(plugins_dir, "platforms")
    if not glob.glob(os.path.join(platforms_dir, "qwindows*")):
        print(
            "Warning: qwindows plugin not found under "
            f"{platforms_dir}. Try: uv sync --reinstall-package pyqt5-qt5"
        )

    # A wrong value here (e.g. from conda) is the usual culprit — overwrite it.
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = platforms_dir
    os.environ["QT_PLUGIN_PATH"] = plugins_dir
    # Ensure the Qt DLLs next to the plugins are resolvable.
    qt_bin = os.path.join(os.path.dirname(plugins_dir), "bin")
    if os.path.isdir(qt_bin):
        os.environ["PATH"] = qt_bin + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(qt_bin)
            except OSError:
                pass
    print(f"Windows Qt plugin path: {platforms_dir}")


# Must run before Qt/napari/vispy load.
# On Windows, OpenGL backend affects napari/vispy. If you see
# "self._finalCall" / "NoneType object is not callable", try another backend:
#   set QT_OPENGL=desktop   (NVIDIA/AMD GPU, local desktop)
#   set QT_OPENGL=angle     (Intel iGPU, some laptops)
#   set QT_OPENGL=software  (slowest; last resort / remote desktop)
if sys.platform == "win32":
    _fix_windows_qt_plugin_path()
    os.environ.setdefault("QT_OPENGL", "desktop")
    print(f"Windows OpenGL backend: QT_OPENGL={os.environ['QT_OPENGL']}")

from PIL import Image
import numpy as np
from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import QFileDialog, QLabel, QPushButton, QVBoxLayout, QWidget
import napari
from napari.layers import Image as ImageLayer
from napari.layers import Labels
from napari.layers._source import layer_source
from napari.utils.colormaps import DirectLabelColormap

# Class IDs match the MyoFAIber WebUI / FT target.
# 3 and 6 are lightened so they stay distinct while painting.
CLASS_COLORS = {
    None: [0.0, 0.0, 0.0, 0.0],  # unmapped labels
    0: [0.0, 0.0, 0.0, 0.0],  # Uncertain (transparent; eraser paints 0)
    1: [0.898, 0.867, 0.698, 1.0],  # beige — Background
    2: [0.482, 0.557, 0.059, 1.0],  # olive green — Type IIB
    3: [0.980, 0.980, 0.700, 1.0],  # pale yellow — Type I (#FAFAB2)
    4: [0.690, 0.047, 0.247, 1.0],  # pink — Membrane
    5: [0.361, 0.718, 0.871, 1.0],  # blue — Type IIA
    6: [0.980, 0.700, 0.980, 1.0],  # bright magenta — Type IIX (#FAB2FA)
    7: [0.525, 0.565, 0.604, 1.0],  # gray — Vessel
}

CLASS_NAMES = (
    (0, "Uncertain"),
    (1, "Background"),
    (2, "Type IIB"),
    (3, "Type I"),
    (4, "Membrane"),
    (5, "Type IIA"),
    (6, "Type IIX"),
    (7, "Vessel"),
)

CLASS_NAME = dict(CLASS_NAMES)

DEMO_PAIRS = [
    ("TG_Sol_rgb.png", "TG_Sol_pred.tiff"),
    ("WT_Sol_rgb.png", "WT_Sol_pred.tiff"),
    ("WT_TA_rgb.png", "WT_TA_pred.tiff"),
]

SAVE_SHORTCUT = "⌘S" if sys.platform == "darwin" else "Ctrl+S"

# Guard against re-entry when we replace Image → Labels / RGB.
_APPLYING_COLORMAP = False
_CLAMPING_LABEL = False
_LOADED_PATHS: set[str] = set()
_GUARDED_LAYERS: weakref.WeakSet = weakref.WeakSet()
_PANEL = None


def make_class_colormap():
    """Build a DirectLabelColormap (required by napari>=0.7)."""
    return DirectLabelColormap(color_dict=CLASS_COLORS)


def class_hex(class_id):
    """``#RRGGBB`` for a class, using the same rounding as the README badges."""
    red, green, blue = CLASS_COLORS[class_id][:3]
    return "#{:02X}{:02X}{:02X}".format(
        int(round(red * 255)),
        int(round(green * 255)),
        int(round(blue * 255)),
    )


def apply_class_colormap(layer: Labels) -> None:
    """Force DIRECT color mode with CLASS_COLORS on a Labels layer."""
    layer.colormap = make_class_colormap()
    print(
        f"Applied CLASS_COLORS to Labels '{layer.name}' "
        f"(color_mode={layer._color_mode})"
    )


def local_path(path):
    """Absolute filesystem path for a Napari source path or ``file://`` URL."""
    if not path:
        return None
    path = str(path)
    if path.startswith("file:"):
        parsed = urlparse(path)
        path = url2pathname(unquote(parsed.path))
    return os.path.abspath(path)


def layer_path(layer):
    """Filesystem path stored on a layer, if Napari recorded one."""
    source = getattr(layer, "source", None)
    path = local_path(getattr(source, "path", None))
    if path:
        return path
    return local_path(layer.metadata.get("mask_path"))


def remember_path(path):
    path = local_path(path)
    if path:
        _LOADED_PATHS.add(path)
    return path


def already_loaded(path):
    path = local_path(path)
    return bool(path) and path in _LOADED_PATHS


def looks_like_pred_mask(layer: ImageLayer) -> bool:
    """Detect MyoFAIber ``*_pred`` masks opened as Image layers."""
    path = layer_path(layer)
    name = path or (layer.name or "")
    if is_pred_file(name):
        return True

    data = np.asarray(layer.data)
    # A 4-channel confocal stack is an image, even when it has few gray levels.
    if four_channel_stack(data) is not None:
        return False
    if data.ndim == 3 and data.shape[-1] == 3:
        return False
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


def four_channel_stack(data):
    """Return a ``(4, H, W)`` view, or None when this is not a 4-channel image."""
    data = np.squeeze(np.asarray(data))
    if data.ndim != 3:
        return None
    if data.shape[0] == 4 and data.shape[1] > 4 and data.shape[2] > 4:
        return data
    if data.shape[-1] == 4 and data.shape[0] > 4 and data.shape[1] > 4:
        return np.moveaxis(data, -1, 0)
    return None


def composite_rgb(stack):
    """Ch1 magenta, Ch2 green, Ch3 blue, Ch4 red. Each channel is min-max scaled."""
    channels = []
    for index in range(4):
        channel = np.asarray(stack[index], dtype=np.float32)
        low = float(channel.min())
        high = float(channel.max())
        if high > low:
            channel = (channel - low) / (high - low) * 255.0
        else:
            channel = np.zeros_like(channel)
        channels.append(channel)

    rgb = np.zeros(channels[0].shape + (3,), dtype=np.float32)
    rgb[..., 0] = channels[3] + channels[0]  # Red = Ch4 + Ch1
    rgb[..., 1] = channels[1]  # Green = Ch2
    rgb[..., 2] = channels[2] + channels[0]  # Blue = Ch3 + Ch1
    return np.clip(rgb, 0, 255).astype(np.uint8)


def convert_image_to_class_labels(viewer, image_layer: ImageLayer) -> Labels | None:
    """Replace a dropped Image mask with a Labels layer using CLASS_COLORS."""
    global _APPLYING_COLORMAP

    if image_layer not in viewer.layers:
        return None

    name = image_layer.name
    data = as_label_array(image_layer.data)
    path = layer_path(image_layer)
    idx = viewer.layers.index(image_layer)

    _APPLYING_COLORMAP = True
    try:
        viewer.layers.remove(image_layer)
        context = layer_source(path=path) if path else nullcontext()
        with context:
            layer = viewer.add_labels(
                data,
                name=name,
                colormap=make_class_colormap(),
            )
        if path:
            layer.metadata["mask_path"] = path
        viewer.layers.move(viewer.layers.index(layer), min(idx, len(viewer.layers) - 1))
        apply_class_colormap(layer)
        print(
            f"Converted Image → Labels '{name}': "
            f"unique={np.unique(data).tolist()}"
        )
        return layer
    finally:
        _APPLYING_COLORMAP = False


def replace_with_rgb(viewer, image_layer: ImageLayer):
    """Replace a 4-channel image with the stain RGB composite."""
    global _APPLYING_COLORMAP

    if image_layer not in viewer.layers:
        return None
    stack = four_channel_stack(image_layer.data)
    if stack is None:
        return None

    rgb = composite_rgb(stack)
    name = image_layer.name
    path = layer_path(image_layer)
    idx = viewer.layers.index(image_layer)

    _APPLYING_COLORMAP = True
    try:
        viewer.layers.remove(image_layer)
        context = layer_source(path=path) if path else nullcontext()
        with context:
            layer = viewer.add_image(rgb, name=name, rgb=True)
        viewer.layers.move(viewer.layers.index(layer), min(idx, len(viewer.layers) - 1))
    finally:
        _APPLYING_COLORMAP = False

    print(
        f"Composited 4-channel '{name}' → RGB "
        "(Ch1 magenta, Ch2 green, Ch3 blue, Ch4 red)"
    )
    return layer


def spatial_shape(arr):
    """Return (H, W) for 2D / HWC / CHW arrays."""
    arr = np.squeeze(np.asarray(arr))
    if arr.ndim == 2:
        return tuple(int(v) for v in arr.shape)
    if arr.ndim == 3:
        if arr.shape[-1] <= 4:
            return tuple(int(v) for v in arr.shape[:2])
        if arr.shape[0] <= 4:
            return tuple(int(v) for v in arr.shape[1:])
        return tuple(int(v) for v in arr.shape[-2:])
    raise ValueError(f"Unsupported array shape: {arr.shape}")


def strip_image_suffix(name):
    """Strip common image suffixes without mangling '.tiff' via '.tif'."""
    lower = name.lower()
    for suffix in ("_rgb.png", "_rgb.tiff", "_rgb.tif", ".tiff", ".tif", ".png", ".jpg", ".jpeg"):
        if lower.endswith(suffix):
            return name[: len(name) - len(suffix)]
    return os.path.splitext(name)[0]


def is_pred_file(path):
    """True if path looks like a MyoFAIber ``*_pred`` mask."""
    stem = os.path.splitext(os.path.basename(str(path)))[0].lower()
    return stem.endswith("_pred") or stem.endswith("pred")


def find_mask_path(img_path):
    """Resolve the MyoFAIber ``*_pred`` mask next to an image."""
    img_path = local_path(img_path)
    directory = os.path.dirname(img_path)
    base_name = strip_image_suffix(os.path.basename(img_path))
    candidates = [
        f"{base_name}_pred.tiff",
        f"{base_name}_pred.tif",
        f"{base_name}_pred.png",
        f"{base_name}pred.tiff",
        f"{base_name}pred.tif",
    ]
    for name in candidates:
        path = os.path.join(directory, name)
        if os.path.exists(path):
            return path, name
    return None, candidates[0]


def find_image_path(mask_path):
    """Resolve the image next to a ``*_pred`` mask. Prefer an existing ``*_rgb``."""
    mask_path = local_path(mask_path)
    directory = os.path.dirname(mask_path)
    stem = os.path.splitext(os.path.basename(mask_path))[0]
    lower = stem.lower()
    if lower.endswith("_pred"):
        base = stem[: -len("_pred")]
    elif lower.endswith("pred"):
        base = stem[: -len("pred")]
    else:
        base = stem

    candidates = []
    for ext in (".png", ".tif", ".tiff", ".jpg", ".jpeg"):
        candidates.append(f"{base}_rgb{ext}")
    for ext in (".tif", ".tiff", ".png", ".jpg", ".jpeg"):
        candidates.append(f"{base}{ext}")
    for name in candidates:
        path = os.path.join(directory, name)
        if os.path.exists(path) and not is_pred_file(path):
            return path
    return None


def refined_path_for(mask_path):
    """``WT_Sol_pred.tiff`` → ``WT_Sol_refined.tif``. A refined file maps to itself."""
    mask_path = local_path(mask_path)
    directory = os.path.dirname(mask_path)
    stem = os.path.splitext(os.path.basename(mask_path))[0]
    lower = stem.lower()
    if lower.endswith("_refined"):
        base = stem
    elif lower.endswith("_pred"):
        base = stem[: -len("_pred")] + "_refined"
    elif lower.endswith("pred"):
        base = stem[: -len("pred")] + "_refined"
    else:
        base = stem + "_refined"
    return os.path.join(directory, base + ".tif")


def sibling_path(path):
    """The image for a mask, or the mask for an image. None if it is not on disk."""
    if is_pred_file(path):
        return find_image_path(path)
    mask_path, _name = find_mask_path(path)
    return mask_path


def warn_shape_mismatch(viewer, path_a, path_b):
    """Print when an opened pair does not share H × W."""
    wanted = {local_path(path_a), local_path(path_b)}
    shapes = []
    for layer in viewer.layers:
        path = layer_path(layer)
        if path in wanted:
            try:
                shapes.append((os.path.basename(path), spatial_shape(layer.data)))
            except ValueError as exc:
                print(exc)
                return
    if len(shapes) >= 2 and shapes[0][1] != shapes[1][1]:
        print(f"shape mismatch! {shapes[0]} vs {shapes[1]}")


def open_file(viewer, path):
    """Open ``path`` once. Napari records the source path on the new layer."""
    path = local_path(path)
    if not path or already_loaded(path):
        return []
    remember_path(path)
    try:
        layers = list(viewer.open(path, stack=False))
    except Exception as exc:
        _LOADED_PATHS.discard(path)
        print(f"Could not open {path}: {exc}")
        return []
    if not layers:
        _LOADED_PATHS.discard(path)
        print(f"Could not open {path}")
    return layers


def open_sibling(viewer, path):
    """Open the image next to a mask, or the mask next to an image."""
    path = local_path(path)
    if not path or not os.path.exists(path):
        return
    other = sibling_path(path)
    if not other:
        stem = os.path.splitext(os.path.basename(path))[0].lower()
        if stem.endswith("_refined"):
            return
        kind = "image" if is_pred_file(path) else "*_pred mask"
        print(f"No sibling {kind} next to {path}")
        return
    other = local_path(other)
    if already_loaded(other):
        warn_shape_mismatch(viewer, path, other)
        return
    print(f"Opening sibling: {other}")
    remember_path(other)
    try:
        viewer.open(other, stack=False)
    except Exception as exc:
        _LOADED_PATHS.discard(other)
        print(f"Could not open {other}: {exc}")
        return
    warn_shape_mismatch(viewer, path, other)


def on_layer_inserted(event, viewer):
    """Color labels, composite 4-channel images, and open the sibling file."""
    global _APPLYING_COLORMAP
    if _APPLYING_COLORMAP:
        return

    layer = event.value
    path = layer_path(layer)
    if path:
        remember_path(path)

    if isinstance(layer, Labels):
        QTimer.singleShot(0, lambda lyr=layer: apply_class_colormap(lyr))
        if path:
            QTimer.singleShot(0, lambda p=path: open_sibling(viewer, p))
        return

    if not isinstance(layer, ImageLayer):
        return

    if looks_like_pred_mask(layer):
        def _convert(lyr=layer, p=path):
            convert_image_to_class_labels(viewer, lyr)
            if p:
                open_sibling(viewer, p)

        QTimer.singleShot(0, _convert)
        return

    if four_channel_stack(layer.data) is not None:
        def _composite(lyr=layer, p=path):
            replace_with_rgb(viewer, lyr)
            if p:
                open_sibling(viewer, p)

        QTimer.singleShot(0, _composite)
        return

    if path and not is_pred_file(path):
        QTimer.singleShot(0, lambda p=path: open_sibling(viewer, p))


def clamp_selected_label(layer):
    """Keep the brush on classes 0–7. ``M`` and ``=`` cannot invent class 8."""
    global _CLAMPING_LABEL
    if _CLAMPING_LABEL:
        return
    value = int(layer.selected_label)
    if 0 <= value <= 7:
        return
    clamped = min(7, max(0, value))
    _CLAMPING_LABEL = True
    try:
        layer.selected_label = clamped
    finally:
        _CLAMPING_LABEL = False
    print(f"Label {value} is outside 0–7; using {clamped} ({CLASS_NAME[clamped]}).")


def attach_label_guard(layer):
    if not isinstance(layer, Labels) or layer in _GUARDED_LAYERS:
        return
    _GUARDED_LAYERS.add(layer)

    def _on_selected(_event, lyr=layer):
        clamp_selected_label(lyr)
        if _PANEL is not None:
            _PANEL.refresh()

    layer.events.selected_label.connect(_on_selected)


def watch_new_layer(event, _viewer):
    attach_label_guard(event.value)
    if _PANEL is not None:
        _PANEL.refresh()


def active_labels(viewer):
    """The labels layer being edited: the active one, or the topmost labels layer."""
    active = viewer.layers.selection.active
    if isinstance(active, Labels):
        return active
    for layer in reversed(list(viewer.layers)):
        if isinstance(layer, Labels):
            return layer
    return None


def select_class(viewer, class_id):
    """Select a FT class and switch the mask layer into the paint brush."""
    class_id = int(class_id)
    layer = active_labels(viewer)
    if layer is None:
        message = "Open a *_pred mask first."
        viewer.status = message
        print(message)
        return
    if viewer.layers.selection.active is not layer:
        viewer.layers.selection.active = layer
    layer.mode = "paint"
    layer.selected_label = class_id
    message = f"Paint {class_id} {CLASS_NAME[class_id]}"
    viewer.status = message
    print(message)
    if _PANEL is not None:
        _PANEL.refresh()


def write_uint8_tiff(path, array):
    """Write a 2D uint8 label map. Prefer tifffile so the values stay class IDs."""
    array = np.ascontiguousarray(array, dtype=np.uint8)
    try:
        import tifffile
    except ImportError:
        tifffile = None
    if tifffile is not None:
        tifffile.imwrite(path, array)
        return
    Image.fromarray(array, mode="L").save(path)


def save_active_labels(viewer):
    """Write the active mask as uint8 ``*_refined.tif`` beside the original ``*_pred``."""
    layer = active_labels(viewer)
    if layer is None:
        message = "No mask layer to save."
        viewer.status = message
        print(message)
        return

    source = layer_path(layer)
    if source:
        dest = refined_path_for(source)
        if os.path.abspath(dest) == os.path.abspath(source) and is_pred_file(source):
            message = f"Refusing to overwrite the original prediction: {source}"
            viewer.status = message
            print(message)
            return
    else:
        dest, _selected = QFileDialog.getSaveFileName(
            viewer.window._qt_window,
            "Save refined mask",
            "refined.tif",
            "TIFF (*.tif *.tiff)",
        )
        if not dest:
            print("Save cancelled.")
            return

    array = as_label_array(layer.data)
    unique = np.unique(array)
    if unique.size and (int(unique.min()) < 0 or int(unique.max()) > 255):
        message = (
            f"Cannot save '{layer.name}': label values must fit in uint8, "
            f"got {int(unique.min())}–{int(unique.max())}."
        )
        viewer.status = message
        print(message)
        return
    if unique.size and int(unique.max()) > 7:
        print(
            f"Warning: '{layer.name}' has labels outside 0–7: "
            f"{unique.astype(int).tolist()}"
        )

    write_uint8_tiff(dest, array.astype(np.uint8))
    message = f"Saved {dest}"
    viewer.status = message
    print(f"{message} (uint8, unique={unique.astype(int).tolist()})")


def _is_bare_digit(binding):
    text = str(binding)
    return len(text) == 1 and text in "0123456789"


def release_number_keys_for_classes():
    """Give bare digit keys to class selection.

    Napari uses ``1``–``7`` for layer modes and ``M`` for a new label id.
    Those bindings are removed in this process only. The user's Napari
    settings file is not modified. ``P`` / ``E`` / ``L`` / ``F`` / ``Z`` stay.
    """
    from napari.settings import get_settings
    from napari.utils.action_manager import action_manager

    shortcuts = get_settings().shortcuts.shortcuts
    for name, bindings in list(shortcuts.items()):
        if name not in action_manager._actions:
            continue
        drop_all = name == "napari:new_label"
        kept = [] if drop_all else [kb for kb in bindings if not _is_bare_digit(kb)]
        if drop_all or len(kept) != len(list(bindings)):
            action_manager.unbind_shortcut(name)
            for binding in kept:
                action_manager.bind_shortcut(name, str(binding))


def install_class_keys(viewer):
    """``0``–``7`` select that class. ``Ctrl+S`` / ``⌘S`` saves ``*_refined.tif``."""

    def _select(viewer, class_id):
        select_class(viewer, class_id)

    for class_id in range(8):
        viewer.bind_key(
            str(class_id),
            lambda viewer, class_id=class_id: _select(viewer, class_id),
            overwrite=True,
        )
    viewer.bind_key("Control-S", save_active_labels, overwrite=True)


class ClassPanel(QWidget):
    """One button per FT class. Clicking selects it and starts the brush."""

    def __init__(self, viewer):
        super().__init__()
        self.viewer = viewer
        self.buttons = {}
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        hint = QLabel(
            "Press 0–7 or click a class, then paint.\n"
            f"{SAVE_SHORTCUT} saves *_refined.tif.\n"
            "The original *_pred is kept.\n"
            "E paints 0 Uncertain."
        )
        hint.setWordWrap(True)
        hint.setFocusPolicy(Qt.NoFocus)
        layout.addWidget(hint)
        for class_id, name in CLASS_NAMES:
            button = QPushButton(f"{class_id}  {name}")
            button.setFocusPolicy(Qt.NoFocus)
            button.setMinimumHeight(28)
            button.clicked.connect(
                lambda _checked=False, class_id=class_id: select_class(viewer, class_id)
            )
            self.buttons[class_id] = button
            layout.addWidget(button)
        layout.addStretch(1)
        self.setLayout(layout)
        self.refresh()

    def refresh(self):
        layer = active_labels(self.viewer)
        current = int(layer.selected_label) if layer is not None else None
        for class_id, button in self.buttons.items():
            button.setStyleSheet(_button_style(class_id, class_id == current))


def _button_style(class_id, active):
    red, green, blue, alpha = CLASS_COLORS[class_id]
    if alpha == 0:
        background = "#3a3a3a"
        foreground = "#ffffff"
    else:
        background = class_hex(class_id)
        luminance = 0.299 * red + 0.587 * green + 0.114 * blue
        foreground = "#111111" if luminance > 0.62 else "#ffffff"
    border = "2px solid #ffffff" if active else "1px solid #555555"
    weight = "700" if active else "500"
    return (
        "QPushButton {"
        f" background-color: {background};"
        f" color: {foreground};"
        f" border: {border};"
        " border-radius: 4px;"
        " text-align: left;"
        " padding: 4px 8px;"
        f" font-weight: {weight};"
        "}"
    )


def install_class_panel(viewer):
    global _PANEL
    _PANEL = ClassPanel(viewer)
    viewer.window.add_dock_widget(_PANEL, name="Classes", area="right")
    viewer.layers.selection.events.active.connect(lambda _event: _PANEL.refresh())


def install_hooks(viewer):
    """Color labels, pair files, and keep the brush on classes 0–7."""
    viewer.layers.events.inserted.connect(
        lambda event: on_layer_inserted(event, viewer)
    )
    viewer.layers.events.inserted.connect(
        lambda event: watch_new_layer(event, viewer)
    )
    print(
        "Ready.\n"
        "  Drop an image or a *_pred mask — the file beside it opens too.\n"
        "  A 4-channel TIFF is shown as magenta / green / blue / red.\n"
        "  Press 0–7 (or use the Classes panel) and paint.\n"
        f"  {SAVE_SHORTCUT} saves *_refined.tif next to the original *_pred.\n"
        "  P paint, E erase (paints 0 Uncertain), L pick, F fill, Z pan, [ ] brush."
    )


def print_label_guide():
    print("--- LABEL GUIDE ---")
    for class_id, name in CLASS_NAMES:
        print(f"  {class_id}: {name} ({class_hex(class_id) if class_id else 'transparent'})")
    print("Eraser (E) paints 0 Uncertain. Background is 1.")


def run_demo(viewer):
    """Open sample images from the repo root. Sibling ``*_pred`` files follow."""
    print(f"Demo mode (napari {napari.__version__})")
    opened = False
    for img_path, mask_path in DEMO_PAIRS:
        if os.path.exists(img_path):
            open_file(viewer, img_path)
            opened = True
        elif os.path.exists(mask_path):
            open_file(viewer, mask_path)
            opened = True
        else:
            print(f"Skipping missing pair: {img_path}, {mask_path}")
    if not opened:
        print("No demo files in the current directory.")
    print_label_guide()


def run_file_picker(viewer):
    """Open a file dialog. Each file's sibling is opened by the layer hook."""
    print("Opening file dialog...")
    files, _selected_filter = QFileDialog.getOpenFileNames(
        None,
        "Select Raw Images, RGB Composites, or MyoFAIber *_pred Masks",
        "",
        "Images (*.tif *.tiff *.png *.jpg)",
    )
    if not files:
        print("No files selected — drag-and-drop into the viewer instead.")
        return
    for path in files:
        if already_loaded(path):
            continue
        open_file(viewer, path)


def main():
    parser = argparse.ArgumentParser(
        description="Refine MyoFAIber *_pred masks in Napari for FT datasets."
    )
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
    release_number_keys_for_classes()
    install_class_keys(viewer)
    install_class_panel(viewer)
    install_hooks(viewer)

    if args.demo:
        run_demo(viewer)
    elif args.dialog:
        run_file_picker(viewer)
    else:
        print("Drag a confocal image or a MyoFAIber '*_pred' mask into the viewer.")

    napari.run()


if __name__ == "__main__":
    main()
