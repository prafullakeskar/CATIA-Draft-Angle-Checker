import base64
import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2

from src.analyzer import DraftAnalyzer
from src.catia_integration import CatiaIntegrationError, capture_active_catia_window, list_visible_windows
from src.report import Report


class DraftAngleDesktopApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Draft Angle Checker")
        self.geometry("980x760")
        self.minsize(820, 620)

        self.summary = None
        self.source_label = None
        self.overlay_photo = None
        self.overlay_png = None

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
        self.status_label = ttk.Label(root, textvariable=self.status_var, font=("Segoe UI", 12, "bold"))
        self.status_label.pack(fill=tk.X, pady=(8, 4))

        self.detail_var = tk.StringVar(value="")
        ttk.Label(root, textvariable=self.detail_var).pack(fill=tk.X)

        body = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, pady=(14, 0))

        image_frame = ttk.Frame(body)
        body.add(image_frame, weight=3)
        ttk.Label(image_frame, text="Analysis Overlay").pack(anchor=tk.W)
        self.image_label = ttk.Label(image_frame, anchor=tk.CENTER)
        self.image_label.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        summary_frame = ttk.Frame(body)
        body.add(summary_frame, weight=2)
        ttk.Label(summary_frame, text="Summary").pack(anchor=tk.W)
        self.summary_text = tk.Text(summary_frame, height=12, wrap=tk.WORD)
        self.summary_text.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.summary_text.configure(state=tk.DISABLED)

    def analyze_catia(self):
        self._set_busy("Capturing CATIA window...")
        self.update_idletasks()
        try:
            capture = capture_active_catia_window()
            self.source_label = f"{capture.window_title} ({capture.width}x{capture.height})"
            self._run_analysis(capture.png_bytes)
        except CatiaIntegrationError as exc:
            self._set_ready()
            messagebox.showerror("CATIA capture failed", str(exc))
        except Exception as exc:
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

    def _run_analysis(self, image_bytes):
        analyzer = DraftAnalyzer(image_bytes)
        analyzer.analyze()
        threshold = float(self.threshold_var.get())
        self.summary = analyzer.get_analysis_summary(pass_threshold=threshold)

        overlay = analyzer.get_overlay_image()
        self.overlay_png = self._encode_preview_png(overlay)
        self._show_overlay(self.overlay_png)
        self._show_summary()
        self._set_ready()

    def _encode_preview_png(self, image):
        max_width = 620
        max_height = 520
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

    def _show_summary(self):
        status = self.summary["status"]
        source = self.source_label or "Current analysis"
        ok_text = "OK" if status == "PASS" else "NOT OK"
        self.status_var.set(f"{ok_text} - {source}")
        self.detail_var.set(
            f"Pass: {self.summary['pass_percentage']:.2f}% | "
            f"Fail: {self.summary['fail_percentage']:.2f}% | "
            f"Coverage: {self.summary.get('analyzed_roi_coverage', 0):.2f}% | "
            f"Threshold: {self.summary['pass_threshold']}%"
        )

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
        self.save_button.configure(state=tk.DISABLED)

    def _set_ready(self):
        if not self.summary:
            self.status_var.set("Open CATIA Draft Analysis or choose an image to begin.")


def main():
    app = DraftAngleDesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
