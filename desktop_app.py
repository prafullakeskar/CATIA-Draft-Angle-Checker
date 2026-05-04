import base64
import json
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2

from src.analyzer import DraftAnalyzer
from src.catia_integration import (
    CatiaIntegrationError,
    capture_active_catia_window,
    ensure_process_dpi_aware,
    list_visible_windows,
)
from src.report import Report


class DraftAngleDesktopApp(tk.Tk):
    def __init__(self):
        ensure_process_dpi_aware()
        super().__init__()
        self.title("Draft Angle Checker")
        self.geometry("980x760")
        self.minsize(820, 620)

        self.summary = None
        self.source_label = None
        self.overlay_photo = None
        self.overlay_png = None
        self.overlay_image = None

        self._build_ui()

    def _build_ui(self):
        root = ttk.Frame(self, padding=16)
        root.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(root)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Draft Angle Checker", font=("Segoe UI", 18, "bold")).pack(side=tk.LEFT)

        controls = ttk.Frame(root)
        controls.pack(fill=tk.X, pady=(16, 8))

        ttk.Label(controls, text="Pass threshold (%)").pack(side=tk.LEFT)
        self.threshold_var = tk.DoubleVar(value=80)
        threshold = ttk.Spinbox(
            controls,
            from_=0,
            to=100,
            increment=1,
            width=8,
            textvariable=self.threshold_var,
        )
        threshold.pack(side=tk.LEFT, padx=(8, 18))

        ttk.Button(controls, text="Analyze CATIA Window", command=self.analyze_catia).pack(side=tk.LEFT)
        ttk.Button(controls, text="Open Image", command=self.analyze_image_file).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(controls, text="Window Diagnostics", command=self.show_window_diagnostics).pack(side=tk.LEFT, padx=(8, 0))
        self.save_button = ttk.Button(controls, text="Save Report", command=self.save_report, state=tk.DISABLED)
        self.save_button.pack(side=tk.RIGHT)

        self.status_var = tk.StringVar(value="Open CATIA Draft Analysis or choose an image to begin.")
        self.status_label = ttk.Label(root, textvariable=self.status_var, font=("Segoe UI", 24, "bold"))
        self.status_label.pack(fill=tk.X, pady=(8, 4))

        self.detail_var = tk.StringVar(value="")
        ttk.Label(root, textvariable=self.detail_var).pack(fill=tk.X)

        body = ttk.Notebook(root)
        body.pack(fill=tk.BOTH, expand=True, pady=(14, 0))

        image_frame = ttk.Frame(body)
        body.add(image_frame, text="Analysis")
        ttk.Label(image_frame, text="Analysis Overlay").pack(anchor=tk.W)
        self.image_label = ttk.Label(image_frame, anchor=tk.CENTER)
        self.image_label.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.image_label.bind("<Configure>", self._resize_overlay_preview)

        summary_frame = ttk.Frame(body)
        body.add(summary_frame, text="Summary")
        ttk.Label(summary_frame, text="Summary").pack(anchor=tk.W)
        self.summary_text = tk.Text(summary_frame, height=12, wrap=tk.WORD)
        self.summary_text.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.summary_text.configure(state=tk.DISABLED)
        body.select(image_frame)

    def analyze_catia(self):
        self._set_busy("Capturing CATIA window...")
        self.update_idletasks()
        try:
            self.withdraw()
            time.sleep(0.35)
            capture = capture_active_catia_window()
            self.source_label = f"{capture.window_title} ({capture.width}x{capture.height})"
            self.deiconify()
            self._run_analysis(capture.png_bytes)
        except CatiaIntegrationError as exc:
            self.deiconify()
            self._set_ready()
            messagebox.showerror("CATIA capture failed", str(exc))
        except Exception as exc:
            self.deiconify()
            self._set_ready()
            messagebox.showerror("Analysis failed", str(exc))

    def analyze_image_file(self):
        path = filedialog.askopenfilename(
            title="Choose a CATIA Draft Analysis image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        self.source_label = str(Path(path))
        self._set_busy("Analyzing image...")
        self.update_idletasks()
        try:
            self._run_analysis(Path(path).read_bytes())
        except Exception as exc:
            self._set_ready()
            messagebox.showerror("Analysis failed", str(exc))

    def show_window_diagnostics(self):
        try:
            windows = list_visible_windows()
        except CatiaIntegrationError as exc:
            messagebox.showerror("Window diagnostics failed", str(exc))
            return

        top_windows = windows[:40]
        lines = [
            f"{item['hwnd']} | {item['class_name']} | {item['width']}x{item['height']} | {item['title']}"
            for item in top_windows
        ]
        if not lines:
            lines = ["No visible top-level windows found."]

        diagnostics = tk.Toplevel(self)
        diagnostics.title("Window Diagnostics")
        diagnostics.geometry("900x460")
        text = tk.Text(diagnostics, wrap=tk.NONE)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, "\n".join(lines))
        text.configure(state=tk.DISABLED)

    def _run_analysis(self, image_bytes, use_roi=True, use_graphics_viewport=False):
        analyzer = DraftAnalyzer(
            image_bytes,
            use_roi=use_roi,
            use_graphics_viewport=use_graphics_viewport,
        )
        analyzer.analyze()
        threshold = float(self.threshold_var.get())
        self.summary = analyzer.get_analysis_summary(pass_threshold=threshold)

        overlay = analyzer.get_overlay_image()
        ok, full_overlay_buffer = cv2.imencode(".png", overlay)
        if not ok:
            raise ValueError("Could not render analysis overlay.")
        self.overlay_png = full_overlay_buffer.tobytes()
        self.overlay_image = overlay
        self._resize_overlay_preview()
        self._show_summary()
        self._set_ready()

    def _encode_preview_png(self, image, max_width, max_height):
        height, width = image.shape[:2]
        scale = min(max_width / width, max_height / height, 1)
        if scale < 1:
            image = cv2.resize(image, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)

        ok, buffer = cv2.imencode(".png", image)
        if not ok:
            raise ValueError("Could not render analysis overlay.")
        return buffer.tobytes()

    def _show_overlay(self, png_bytes):
        encoded = base64.b64encode(png_bytes).decode("ascii")
        self.overlay_photo = tk.PhotoImage(data=encoded)
        self.image_label.configure(image=self.overlay_photo)

    def _resize_overlay_preview(self, _event=None):
        if self.overlay_image is None:
            return

        width = max(self.image_label.winfo_width() - 20, 320)
        height = max(self.image_label.winfo_height() - 20, 240)
        preview_png = self._encode_preview_png(self.overlay_image, width, height)
        self._show_overlay(preview_png)

    def _show_summary(self):
        status = self.summary["status"]
        ok_text = "OK" if status == "PASS" else "NOK"
        status_color = "#15803d" if status == "PASS" else "#dc2626"
        self.status_var.set(ok_text)
        self.status_label.configure(foreground=status_color)
        self.detail_var.set("")

        self.summary_text.configure(state=tk.NORMAL)
        self.summary_text.delete("1.0", tk.END)
        self.summary_text.insert(tk.END, json.dumps(self.summary, indent=2))
        self.summary_text.configure(state=tk.DISABLED)
        self.save_button.configure(state=tk.NORMAL)

    def save_report(self):
        if not self.summary:
            return

        output_dir = filedialog.askdirectory(title="Choose report output folder")
        if not output_dir:
            return

        report = Report(self.summary, self.source_label)
        output_path = Path(output_dir)
        text_path = output_path / "draft_angle_report.txt"
        json_path = output_path / "draft_angle_report.json"
        overlay_path = output_path / "draft_angle_overlay.png"

        report.save_text_report(text_path)
        report.save_json_report(json_path)
        if self.overlay_png:
            overlay_path.write_bytes(self.overlay_png)

        messagebox.showinfo("Report saved", f"Saved report files to:\n{output_path}")

    def _set_busy(self, message):
        self.status_var.set(message)
        self.status_label.configure(foreground="#111827")
        self.detail_var.set("")
        self.save_button.configure(state=tk.DISABLED)

    def _set_ready(self):
        if not self.summary:
            self.status_var.set("Open CATIA Draft Analysis or choose an image to begin.")
            self.status_label.configure(foreground="#111827")


def main():
    ensure_process_dpi_aware()
    app = DraftAngleDesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
