from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

import dstar_image_prep as prep


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("D-STAR Image Prep (ID-52)")
        self.geometry("720x520")
        self.minsize(680, 480)

        self.input_path_var = tk.StringVar(value="")
        self.out_dir_var = tk.StringVar(value=str(Path.cwd() / "OUT"))
        self.watermark_var = tk.StringVar(value="")
        self.mode_var = tk.StringVar(value="cover")
        self.max_kb_var = tk.StringVar(value="200")
        self.size_var = tk.StringVar(value="640x480")

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        input_frame = ttk.LabelFrame(self, text="Input")
        input_frame.pack(fill="x", **pad)

        ttk.Label(input_frame, text="File or Folder:").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(input_frame, textvariable=self.input_path_var).grid(row=0, column=1, sticky="we", **pad)

        ttk.Button(input_frame, text="Choose File…", command=self.choose_file).grid(row=0, column=2, **pad)
        ttk.Button(input_frame, text="Choose Folder…", command=self.choose_folder).grid(row=0, column=3, **pad)

        input_frame.columnconfigure(1, weight=1)

        out_frame = ttk.LabelFrame(self, text="Output")
        out_frame.pack(fill="x", **pad)

        ttk.Label(out_frame, text="Output Folder:").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(out_frame, textvariable=self.out_dir_var).grid(row=0, column=1, sticky="we", **pad)
        ttk.Button(out_frame, text="Choose Output…", command=self.choose_output).grid(row=0, column=2, **pad)
        ttk.Button(out_frame, text="Open Output", command=self.open_output_folder).grid(row=0, column=3, **pad)

        out_frame.columnconfigure(1, weight=1)

        settings = ttk.LabelFrame(self, text="Settings")
        settings.pack(fill="x", **pad)

        ttk.Label(settings, text="Watermark (use | for 2 lines):").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(settings, textvariable=self.watermark_var).grid(row=0, column=1, columnspan=3, sticky="we", **pad)

        ttk.Label(settings, text="Resize Mode:").grid(row=1, column=0, sticky="w", **pad)
        ttk.Combobox(settings, textvariable=self.mode_var, values=["cover", "contain", "exact"],
                     state="readonly", width=12).grid(row=1, column=1, sticky="w", **pad)

        ttk.Label(settings, text="Target Size:").grid(row=1, column=2, sticky="e", **pad)
        ttk.Entry(settings, textvariable=self.size_var, width=12).grid(row=1, column=3, sticky="w", **pad)

        ttk.Label(settings, text="Max KB:").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(settings, textvariable=self.max_kb_var, width=12).grid(row=2, column=1, sticky="w", **pad)

        ttk.Label(settings, text="Example: K0PRA|Parker, Colorado").grid(row=2, column=2, columnspan=2, sticky="w", **pad)

        settings.columnconfigure(1, weight=1)

        actions = ttk.Frame(self)
        actions.pack(fill="x", **pad)

        self.run_button = ttk.Button(actions, text="Convert", command=self.on_convert)
        self.run_button.pack(side="left")
        ttk.Button(actions, text="Clear Log", command=self.clear_log).pack(side="left", padx=8)

        log_frame = ttk.LabelFrame(self, text="Log")
        log_frame.pack(fill="both", expand=True, **pad)

        self.log = tk.Text(log_frame, height=12, wrap="word")
        self.log.pack(fill="both", expand=True, padx=10, pady=8)
        self._log_line("Ready. Choose a file or folder, then click Convert.")

    def _log_line(self, msg: str):
        self.log.insert("end", msg + "\n")
        self.log.see("end")

    def clear_log(self):
        self.log.delete("1.0", "end")
        self._log_line("Log cleared.")

    def choose_file(self):
        path = filedialog.askopenfilename(
            title="Choose an image",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp"), ("All files", "*.*")]
        )
        if path:
            self.input_path_var.set(path)
            self._log_line(f"Selected file: {path}")

    def choose_folder(self):
        path = filedialog.askdirectory(title="Choose a folder of images")
        if path:
            self.input_path_var.set(path)
            self._log_line(f"Selected folder: {path}")

    def choose_output(self):
        path = filedialog.askdirectory(title="Choose output folder")
        if path:
            self.out_dir_var.set(path)
            self._log_line(f"Output folder set to: {path}")

    def open_output_folder(self):
        out_dir = Path(self.out_dir_var.get()).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
        import os
        os.startfile(str(out_dir))

    def _parse_size(self) -> tuple[int, int]:
        raw = self.size_var.get().strip().lower()
        if "x" not in raw:
            raise ValueError("Target Size must look like 640x480")
        w_s, h_s = raw.split("x", 1)
        w, h = int(w_s), int(h_s)
        if w <= 0 or h <= 0:
            raise ValueError("Target Size must be positive numbers")
        return (w, h)

    def _parse_max_kb(self) -> int:
        kb = int(self.max_kb_var.get().strip())
        if kb <= 0:
            raise ValueError("Max KB must be a positive number")
        return kb

    def on_convert(self):
        input_path = self.input_path_var.get().strip()
        out_dir = self.out_dir_var.get().strip()
        watermark = self.watermark_var.get().strip()
        mode = self.mode_var.get().strip()

        if not input_path:
            messagebox.showwarning("Missing input", "Please choose an input file or folder.")
            return

        try:
            size = self._parse_size()
            max_kb = self._parse_max_kb()
        except Exception as e:
            messagebox.showerror("Invalid settings", str(e))
            return

        self.run_button.config(state="disabled")
        self._log_line("Starting conversion…")

        t = threading.Thread(
            target=self._run_convert_thread,
            args=(input_path, out_dir, size, max_kb, mode, watermark),
            daemon=True
        )
        t.start()

    def _run_convert_thread(self, input_path, out_dir, size, max_kb, mode, watermark):
        try:
            self._log_line(f"Input: {input_path}")
            self._log_line(f"Output: {out_dir}")
            self._log_line(f"Mode: {mode} | Size: {size[0]}x{size[1]} | Max: {max_kb} KB")
            if watermark:
                self._log_line(f"Watermark: {watermark}")

            prep.run_convert(
                input_path=input_path,
                out_dir=out_dir,
                size=size,
                max_kb=max_kb,
                mode=mode,
                watermark=watermark,
            )

            self._log_line("Done ✅")
            self._log_line("Tip: Click 'Open Output' to view files.")
        except Exception as e:
            self._log_line(f"ERROR: {e}")
            messagebox.showerror("Conversion failed", str(e))
        finally:
            self.run_button.config(state="normal")


if __name__ == "__main__":
    App().mainloop()
