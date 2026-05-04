"""CATIA desktop automation helpers.

This module keeps CATIA-specific Windows COM and window-capture code isolated
from the image-analysis engine so the checker can still run from CLI/web modes.
"""

from __future__ import annotations

import ctypes
import time
from dataclasses import dataclass
from typing import Iterable

import cv2
import numpy as np

CAPTUREBLT = 0x40000000
DWMWA_EXTENDED_FRAME_BOUNDS = 9


class CatiaIntegrationError(RuntimeError):
    """Raised when CATIA automation or capture is unavailable."""


@dataclass(frozen=True)
class CatiaWindowCapture:
    """Captured CATIA window image encoded for the analyzer."""

    png_bytes: bytes
    window_title: str
    width: int
    height: int


_dpi_awareness_attempted = False


def ensure_process_dpi_aware():
    """Call once before any HWND is created (e.g. before tk.Tk).

    Without this, GetWindowRect can report logical sizes that do not match
    physical screen pixels on scaled displays, and BitBlt captures only the
    top-left portion of the window.
    """
    global _dpi_awareness_attempted
    if _dpi_awareness_attempted:
        return
    _dpi_awareness_attempted = True
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def _get_window_pixel_bounds(hwnd: int, win32gui) -> tuple[int, int, int, int]:
    """Physical outer bounds for BitBlt / PrintWindow (handles high-DPI scaling)."""
    rect = _RECT()
    try:
        hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd,
            DWMWA_EXTENDED_FRAME_BOUNDS,
            ctypes.byref(rect),
            ctypes.sizeof(rect),
        )
        if hr == 0 and rect.right > rect.left and rect.bottom > rect.top:
            return rect.left, rect.top, rect.right, rect.bottom
    except (AttributeError, OSError):
        pass
    return win32gui.GetWindowRect(hwnd)


def get_running_catia():
    """Return the active CATIA COM application object."""
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise CatiaIntegrationError(
            "CATIA integration requires pywin32. Install it with: pip install pywin32"
        ) from exc

    try:
        pythoncom.CoInitialize()
        return win32com.client.GetActiveObject("CATIA.Application")
    except Exception as exc:
        raise CatiaIntegrationError(
            "Could not connect to CATIA. Start CATIA, open a part/product, "
            "and run Draft Analysis before capturing."
        ) from exc


def get_catia_window_handle(catia_app=None) -> int:
    """Return CATIA's main window handle."""
    try:
        import win32gui
    except ImportError as exc:
        raise CatiaIntegrationError(
            "CATIA window lookup requires pywin32. Install it with: pip install pywin32"
        ) from exc

    catia = catia_app or get_running_catia()
    hwnd = _coerce_hwnd(getattr(catia, "HWND", 0))
    if _is_usable_window(hwnd, win32gui):
        return hwnd

    hwnd = _find_catia_window_by_title_or_class(catia, win32gui)
    if hwnd:
        return hwnd

    raise CatiaIntegrationError(
        "Could not find the CATIA desktop window. Keep CATIA open and visible, "
        "then click Analyze CATIA Window again. If CATIA is minimized, restore it first."
    )


def _coerce_hwnd(value) -> int:
    """Convert CATIA's HWND value to int when available."""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _is_usable_window(hwnd: int, win32gui) -> bool:
    """Return True when hwnd points to a visible, non-empty top-level window."""
    if hwnd <= 0 or not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
        return False

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    return (right - left) > 0 and (bottom - top) > 0


def _catia_search_terms(catia_app) -> Iterable[str]:
    """Build likely title fragments for the running CATIA session."""
    terms = {"catia", "cnext"}

    for attr in ("Caption", "Name", "FullName"):
        try:
            value = str(getattr(catia_app, attr, "") or "").strip()
        except Exception:
            value = ""
        if value:
            terms.add(value.lower())

    try:
        document_name = str(catia_app.ActiveDocument.Name or "").strip()
    except Exception:
        document_name = ""
    if document_name:
        terms.add(document_name.lower())
        terms.add(document_name.rsplit(".", 1)[0].lower())

    return terms


def _window_score(hwnd: int, terms: Iterable[str], win32gui) -> int:
    """Score a window by how CATIA-like its title/class is."""
    title = (win32gui.GetWindowText(hwnd) or "").lower()
    class_name = (win32gui.GetClassName(hwnd) or "").lower()
    combined = f"{title} {class_name}"

    score = 0
    if "catia" in combined:
        score += 20
    if "cnext" in combined:
        score += 15
    if "cat" in class_name:
        score += 8
    for term in terms:
        if len(term) >= 3 and term in combined:
            score += 4
    return score


def _find_catia_window_by_title_or_class(catia_app, win32gui) -> int:
    """Find CATIA when COM does not expose Application.HWND."""
    terms = tuple(_catia_search_terms(catia_app))
    candidates = []

    def callback(hwnd, _):
        if not _is_usable_window(hwnd, win32gui):
            return True
        if win32gui.GetParent(hwnd):
            return True

        score = _window_score(hwnd, terms, win32gui)
        if score > 0:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            area = (right - left) * (bottom - top)
            candidates.append((score, area, hwnd))
        return True

    win32gui.EnumWindows(callback, None)
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][2]

    foreground = win32gui.GetForegroundWindow()
    if _is_usable_window(foreground, win32gui) and _window_score(foreground, terms, win32gui) > 0:
        return foreground

    return 0


def list_visible_windows():
    """Return visible top-level windows for troubleshooting CATIA matching."""
    try:
        import win32gui
    except ImportError as exc:
        raise CatiaIntegrationError(
            "Window diagnostics require pywin32. Install it with: pip install pywin32"
        ) from exc

    windows = []

    def callback(hwnd, _):
        if not _is_usable_window(hwnd, win32gui) or win32gui.GetParent(hwnd):
            return True

        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        windows.append({
            "hwnd": hwnd,
            "title": win32gui.GetWindowText(hwnd) or "",
            "class_name": win32gui.GetClassName(hwnd) or "",
            "width": right - left,
            "height": bottom - top,
        })
        return True

    win32gui.EnumWindows(callback, None)
    return windows


def capture_active_catia_window() -> CatiaWindowCapture:
    """Capture the currently running CATIA main window as PNG bytes."""
    try:
        import win32con
        import win32gui
        import win32ui
    except ImportError as exc:
        raise CatiaIntegrationError(
            "CATIA window capture requires pywin32. Install it with: pip install pywin32"
        ) from exc

    catia = get_running_catia()
    hwnd = get_catia_window_handle(catia)

    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

    _bring_window_to_front(hwnd, win32con, win32gui)

    left, top, right, bottom = _get_window_pixel_bounds(hwnd, win32gui)
    width = right - left
    height = bottom - top
    if width <= 0 or height <= 0:
        raise CatiaIntegrationError("CATIA window has no capturable area.")

    image = _capture_visible_window_from_screen(left, top, width, height, win32con, win32gui, win32ui)
    if _is_probably_blank_catia_viewport(image):
        image = _capture_window_with_printwindow(hwnd, width, height, win32con, win32gui, win32ui)

    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise CatiaIntegrationError("Could not encode CATIA capture as PNG.")

    return CatiaWindowCapture(
        png_bytes=buffer.tobytes(),
        window_title=win32gui.GetWindowText(hwnd) or "CATIA",
        width=width,
        height=height,
    )


def _bring_window_to_front(hwnd, win32con, win32gui):
    """Make CATIA visible before screen capture."""
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    else:
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

    try:
        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass

    try:
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
        )
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_NOTOPMOST,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
        )
    except Exception:
        pass

    time.sleep(0.45)


def _capture_window_with_printwindow(hwnd, width, height, win32con, win32gui, win32ui):
    """Capture a window using PrintWindow."""
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    src_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    mem_dc = src_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(src_dc, width, height)
    mem_dc.SelectObject(bitmap)
    try:
        printed = ctypes.windll.user32.PrintWindow(hwnd, mem_dc.GetSafeHdc(), 2)
        if not printed:
            mem_dc.BitBlt((0, 0), (width, height), src_dc, (0, 0), win32con.SRCCOPY)

        return _bitmap_to_bgr(bitmap)
    finally:
        win32gui.DeleteObject(bitmap.GetHandle())
        mem_dc.DeleteDC()
        src_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)


def _capture_visible_window_from_screen(left, top, width, height, win32con, win32gui, win32ui):
    """Capture visible screen pixels for OpenGL viewports that PrintWindow misses."""
    screen_dc_handle = win32gui.GetDC(0)
    screen_dc = win32ui.CreateDCFromHandle(screen_dc_handle)
    mem_dc = screen_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(screen_dc, width, height)
    mem_dc.SelectObject(bitmap)

    try:
        mem_dc.BitBlt((0, 0), (width, height), screen_dc, (left, top), win32con.SRCCOPY | CAPTUREBLT)
        return _bitmap_to_bgr(bitmap)
    finally:
        win32gui.DeleteObject(bitmap.GetHandle())
        mem_dc.DeleteDC()
        screen_dc.DeleteDC()
        win32gui.ReleaseDC(0, screen_dc_handle)


def _bitmap_to_bgr(bitmap):
    """Convert a Win32 bitmap to an OpenCV BGR image."""
    bmpinfo = bitmap.GetInfo()
    bmpstr = bitmap.GetBitmapBits(True)
    image = np.frombuffer(bmpstr, dtype=np.uint8)
    image.shape = (bmpinfo["bmHeight"], bmpinfo["bmWidth"], 4)
    return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)


def _is_probably_blank_catia_viewport(image):
    """Detect PrintWindow captures where CATIA's OpenGL viewport is missing."""
    height, width = image.shape[:2]
    viewport = image[int(height * 0.18):int(height * 0.90), int(width * 0.06):int(width * 0.94)]
    if viewport.size == 0:
        return False

    hsv = cv2.cvtColor(viewport, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    saturated_ratio = np.count_nonzero((saturation > 45) & (value > 35)) / saturation.size
    return saturated_ratio < 0.03


def _crop_catia_graphics_viewport(image):
    """Crop a full CATIA window capture down to the graphics viewport."""
    height, width = image.shape[:2]
    if height < 300 or width < 300:
        return image

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]

    color_mask = ((saturation > 45) & (value > 35)).astype(np.uint8)
    row_ratio = color_mask.mean(axis=1)
    row_segments = _segments_over_threshold(row_ratio, threshold=0.18, min_length=max(80, height // 5))
    if not row_segments:
        return image

    top, bottom = max(row_segments, key=lambda segment: segment[1] - segment[0])

    col_ratio = color_mask[top:bottom].mean(axis=0)
    col_segments = _segments_over_threshold(col_ratio, threshold=0.12, min_length=max(120, width // 4))
    if col_segments:
        left, right = max(col_segments, key=lambda segment: segment[1] - segment[0])
    else:
        left, right = 0, width

    top = max(0, top - 3)
    bottom = min(height, bottom + 3)
    left = max(0, left - 3)
    right = min(width, right + 3)

    cropped = image[top:bottom, left:right]
    if cropped.shape[0] < height * 0.25 or cropped.shape[1] < width * 0.25:
        return image
    return cropped


def _segments_over_threshold(values, threshold, min_length):
    """Return contiguous index ranges where values stay above a threshold."""
    segments = []
    start = None
    for index, value in enumerate(values):
        if value >= threshold and start is None:
            start = index
        elif value < threshold and start is not None:
            if index - start >= min_length:
                segments.append((start, index))
            start = None

    if start is not None and len(values) - start >= min_length:
        segments.append((start, len(values)))

    return segments
