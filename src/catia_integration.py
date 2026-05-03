"""CATIA desktop automation helpers.

This module keeps CATIA-specific Windows COM and window-capture code isolated
from the image-analysis engine so the checker can still run from CLI/web modes.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import Iterable

import cv2
import numpy as np


class CatiaIntegrationError(RuntimeError):
    """Raised when CATIA automation or capture is unavailable."""


@dataclass(frozen=True)
class CatiaWindowCapture:
    """Captured CATIA window image encoded for the analyzer."""

    png_bytes: bytes
    window_title: str
    width: int
    height: int


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

    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        # Windows may block focus changes; capture can still succeed.
        pass

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top
    if width <= 0 or height <= 0:
        raise CatiaIntegrationError("CATIA window has no capturable area.")

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

        bmpinfo = bitmap.GetInfo()
        bmpstr = bitmap.GetBitmapBits(True)
        image = np.frombuffer(bmpstr, dtype=np.uint8)
        image.shape = (bmpinfo["bmHeight"], bmpinfo["bmWidth"], 4)
        bgr = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        ok, buffer = cv2.imencode(".png", bgr)
        if not ok:
            raise CatiaIntegrationError("Could not encode CATIA capture as PNG.")

        return CatiaWindowCapture(
            png_bytes=buffer.tobytes(),
            window_title=win32gui.GetWindowText(hwnd) or "CATIA",
            width=width,
            height=height,
        )
    finally:
        win32gui.DeleteObject(bitmap.GetHandle())
        mem_dc.DeleteDC()
        src_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)
