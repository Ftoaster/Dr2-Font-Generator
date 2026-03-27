"""
MTSDF Font Pipeline Manager - GUI Tool

Manages all font conversion pipeline in one GUI:
1. MTSDF Atlas Generation
2. JSON → XML Conversion
3. XML Library Merging
4. Texture PNG → DDS Conversion
5. Coordinate Verification Tool
"""

import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog
import subprocess
import os
import json
import sys
from pathlib import Path
import threading
from datetime import datetime

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Import local modules
try:
    from json_to_xml import XMLGenerator
    from l_merge_libraries import merge_xml_libraries_ordered
    import coordinate_comparator
except ImportError as e:
    print(f"Module import failed: {e}")
    XMLGenerator = None
    merge_xml_libraries_ordered = None
    coordinate_comparator = None

def resource_path(relative_path):
    """Returns resource path from PyInstaller bundle or external"""
    try:
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        base_path = Path(__file__).parent
    return str(base_path / relative_path)


class FontPipelineManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Dr2 Font Generator")

        if getattr(sys, 'frozen', False):
            self.work_dir = Path(sys.executable).parent
        else:
            self.work_dir = Path(__file__).parent

        os.chdir(self.work_dir)

        try:
            if getattr(sys, 'frozen', False):
                bundle_dir = Path(sys._MEIPASS)
                icon_path = bundle_dir / 'icon.ico'
                if not icon_path.exists():
                    icon_path = self.work_dir / 'icon.ico'
            else:
                icon_path = self.work_dir / 'icon.ico'
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except Exception as e:
            print(f"Icon load failed: {e}")

        self.input_dir  = self.work_dir / 'witchs_pot'
        self.output_dir = self.work_dir / 'witchs_gift'

        self.config = {
            'font_file': '',
            'charset_file': '',
            'font_size': '74',
            'pxrange': '4',
            'padding': '0',
            'font_name': 'din_cnd_bold_msdf_0',
            'h_scale': '1.0',
            'h_scale_chars_file': 'none',
            'spacing_chars_file': 'none',
            'spacing_ratio': '1.0',
            'spacing_symmetric': False,
            'uv_inset': '0.0',
        }

        self.is_running = False

        self.setup_ui()
        self.load_config()

    # ── UI setup ────────────────────────────────────────────────────

    def setup_ui(self):
        main_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        main_frame.pack(fill='both', expand=True, padx=12, pady=12)
        # grid 내부 반응형: 가로 weight=1, Log 행(5)만 세로 weight=1
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(5, weight=1)
        self.setup_main_tab(main_frame)

    def setup_main_tab(self, parent):

        LBL_W = 165
        ENT_W = 90

        # ── helpers ─────────────────────────────────────────────────

        _row_counter = [-1]

        def section(title):
            _row_counter[0] += 1
            outer = ctk.CTkFrame(parent, corner_radius=8)
            outer.grid(row=_row_counter[0], column=0, sticky='ew',
                       padx=0, pady=(6, 2))
            outer.columnconfigure(0, weight=1)
            ctk.CTkLabel(outer, text=title,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=("gray20", "#89b4fa")
                         ).pack(anchor='w', padx=12, pady=(8, 4))
            inner = ctk.CTkFrame(outer, fg_color="transparent")
            inner.pack(fill='x', padx=8, pady=(0, 8))
            inner.pack_propagate(True)
            return inner

        def make_row(parent):
            r = ctk.CTkFrame(parent, fg_color="transparent")
            r.pack(fill='x', pady=2)
            return r

        def lbl(parent, text):
            ctk.CTkLabel(parent, text=text, width=LBL_W, anchor='w').pack(
                side='left', padx=(4, 0))

        def hint(parent, text):
            ctk.CTkLabel(parent, text=text,
                         text_color=("gray50", "gray55"),
                         font=ctk.CTkFont(size=11)
                         ).pack(side='left', padx=(6, 0))

        def sep(parent):
            ctk.CTkFrame(parent, height=1,
                         fg_color=("gray75", "gray30")
                         ).pack(fill='x', padx=4, pady=6)

        def target_frame(parent, combo_var, combo_ref_attr, cmd_cb):
            r = make_row(parent)
            lbl(r, "  ↳ Target:")
            cb = ctk.CTkComboBox(r, variable=combo_var, width=180,
                                 state='readonly', command=cmd_cb)
            cb.pack(side='left')
            ctk.CTkButton(r, text="Refresh", width=70,
                          command=self.refresh_txt_combos
                          ).pack(side='left', padx=(6, 0))
            setattr(self, combo_ref_attr, cb)

        # ══ 1. File Selection ════════════════════════════════════════
        f1 = section("File Selection")

        r = make_row(f1)
        lbl(r, "Font File:")
        self.font_file_var = tk.StringVar()
        self.font_combo = ctk.CTkComboBox(r, variable=self.font_file_var, state='readonly')
        self.font_combo.pack(side='left', fill='x', expand=True, padx=(0, 4))
        ctk.CTkButton(r, text="Refresh", width=70,
                      command=self.refresh_font_list
                      ).pack(side='right', padx=(0, 4))

        r = make_row(f1)
        lbl(r, "Charset File:")
        self.charset_var = tk.StringVar()
        self.charset_combo = ctk.CTkComboBox(r, variable=self.charset_var, state='readonly')
        self.charset_combo.pack(side='left', fill='x', expand=True, padx=(0, 4))

        r = make_row(f1)
        lbl(r, "Output Filename:")
        self.font_name_var = tk.StringVar(value=self.config['font_name'])
        self.font_name_combo = ctk.CTkComboBox(
            r, variable=self.font_name_var,
            values=['din_cnd_bold_ita_msdf_0',
                    'din_cnd_bold_msdf_0',
                    'roboto_cnd_reg_msdf_0'])
        self.font_name_combo.pack(side='left', fill='x', expand=True, padx=(0, 4))

        # ══ 2. Atlas Generation (Step 1) ════════════════════════════
        f2 = section("Atlas Generation  (Step 1)")

        r = make_row(f2)
        lbl(r, "Font Size:")
        self.font_size_var = tk.StringVar(value=self.config['font_size'])
        ctk.CTkEntry(r, textvariable=self.font_size_var, width=ENT_W).pack(side='left')

        r = make_row(f2)
        lbl(r, "pxrange:")
        self.pxrange_var = tk.StringVar(value=self.config['pxrange'])
        ctk.CTkEntry(r, textvariable=self.pxrange_var, width=ENT_W).pack(side='left')
        hint(r, "SDF range (px) — larger = sharper edges")

        r = make_row(f2)
        lbl(r, "Padding:")
        self.padding_var = tk.StringVar(value=self.config.get('padding', '0'))
        ctk.CTkEntry(r, textvariable=self.padding_var, width=ENT_W).pack(side='left')
        hint(r, "Empty pixels around each glyph — reduces bleeding")

        # ══ 3. Glyph Adjustments (Step 2) ═══════════════════════════
        f3 = section("Glyph Adjustments  (Step 2)")

        r = make_row(f3)
        lbl(r, "UV Inset (px):")
        self.uv_inset_var = tk.StringVar(value=self.config.get('uv_inset', '0.0'))
        ctk.CTkEntry(r, textvariable=self.uv_inset_var, width=ENT_W).pack(side='left')
        hint(r, "Inset UV coords inward — reduces bleeding  (recommended: 0.5)")

        sep(f3)

        r = make_row(f3)
        lbl(r, "H-Scale:")
        self.h_scale_var = tk.StringVar(value=self.config.get('h_scale', '1.0'))
        ctk.CTkEntry(r, textvariable=self.h_scale_var, width=ENT_W).pack(side='left')
        hint(r, "Horizontal glyph compression  (1.0 = original)")

        self.h_scale_chars_var = tk.StringVar(
            value=self.config.get('h_scale_chars_file', 'none'))
        target_frame(f3, self.h_scale_chars_var,
                     'h_scale_chars_combo', self._on_h_scale_chars_selected)

        self.h_scale_preview_var = tk.StringVar(value="(none: applies to all glyphs)")
        r = make_row(f3)
        ctk.CTkLabel(r, text="", width=LBL_W).pack(side='left', padx=(4, 0))
        ctk.CTkLabel(r, textvariable=self.h_scale_preview_var,
                     text_color=("gray50", "gray55"),
                     font=ctk.CTkFont(size=11)).pack(side='left')

        sep(f3)

        r = make_row(f3)
        lbl(r, "Spacing Ratio:")
        self.spacing_ratio_var = tk.StringVar(
            value=self.config.get('spacing_ratio', '1.0'))
        ctk.CTkEntry(r, textvariable=self.spacing_ratio_var, width=ENT_W).pack(side='left')
        hint(r, "Advance width ratio  (1.0 = original,  0.7 = 30% reduction)")

        self.spacing_chars_var = tk.StringVar(
            value=self.config.get('spacing_chars_file', 'none'))
        target_frame(f3, self.spacing_chars_var,
                     'spacing_chars_combo', self._on_spacing_file_selected)

        self.spacing_preview_var = tk.StringVar(value="(none: applies to all glyphs)")
        r = make_row(f3)
        ctk.CTkLabel(r, text="", width=LBL_W).pack(side='left', padx=(4, 0))
        ctk.CTkLabel(r, textvariable=self.spacing_preview_var,
                     text_color=("gray50", "gray55"),
                     font=ctk.CTkFont(size=11)).pack(side='left')

        self.spacing_symmetric_var = tk.BooleanVar(
            value=self.config.get('spacing_symmetric', False))
        r = make_row(f3)
        ctk.CTkLabel(r, text="", width=LBL_W).pack(side='left', padx=(4, 0))
        ctk.CTkCheckBox(r, text="Symmetric — trim both sides equally",
                        variable=self.spacing_symmetric_var).pack(side='left', pady=(2, 4))

        # ══ 4. Buttons ═══════════════════════════════════════════════
        _row_counter[0] += 1
        bf = ctk.CTkFrame(parent, fg_color="transparent")
        bf.grid(row=_row_counter[0], column=0, pady=8)

        self.run_button = ctk.CTkButton(
            bf, text="Run", width=120,
            fg_color="#2d6a4f", hover_color="#1b4332",
            command=self.run_full_pipeline)
        self.run_button.grid(row=0, column=0, padx=5, pady=3)

        ctk.CTkButton(bf, text="Save Settings", width=120,
                      command=self.save_config
                      ).grid(row=0, column=1, padx=5, pady=3)

        ctk.CTkButton(bf, text="Open Input Folder", width=135,
                      fg_color=("gray70", "gray30"), hover_color=("gray60", "gray25"),
                      text_color=("gray10", "gray90"),
                      command=self.open_input_folder
                      ).grid(row=1, column=0, padx=5, pady=3)

        ctk.CTkButton(bf, text="Open Output Folder", width=135,
                      fg_color=("gray70", "gray30"), hover_color=("gray60", "gray25"),
                      text_color=("gray10", "gray90"),
                      command=self.open_output_folder
                      ).grid(row=1, column=1, padx=5, pady=3)

        # ══ 5. Progress ══════════════════════════════════════════════
        _row_counter[0] += 1
        pf = ctk.CTkFrame(parent, fg_color="transparent")
        pf.grid(row=_row_counter[0], column=0, sticky='ew', pady=(6, 2))

        self.progress_var = tk.StringVar(value="Waiting...")
        ctk.CTkLabel(pf, textvariable=self.progress_var, anchor='w').pack(
            anchor='w', padx=4)

        self.progress_bar = ctk.CTkProgressBar(pf)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill='x', padx=4, pady=(4, 6))

        # ══ 6. Log (row=5, weight=1 → 남은 세로 공간 모두 흡수) ══════
        lf = ctk.CTkFrame(parent, corner_radius=8)
        lf.grid(row=5, column=0, sticky='nsew', pady=(2, 6))
        lf.columnconfigure(0, weight=1)
        lf.rowconfigure(0, weight=1)

        self.log_text = ctk.CTkTextbox(
            lf, font=ctk.CTkFont(family="Consolas", size=11))
        self.log_text.grid(row=0, column=0, sticky='nsew', padx=8, pady=8)

        # ══ 7. Font Viewer ════════════════════════════════════════════
        vf = ctk.CTkFrame(parent, fg_color="transparent")
        vf.grid(row=6, column=0, pady=(0, 6))
        ctk.CTkButton(vf, text="Launch Font Viewer", width=160,
                      command=self.launch_coordinate_comparator).pack()

        self.refresh_font_list()

    # ── File list helpers ────────────────────────────────────────────

    def refresh_font_list(self):
        try:
            if not self.input_dir.exists():
                self.input_dir.mkdir(parents=True)
                self.log_message(f"Input folder created: {self.input_dir}")

            font_files = []
            for ext in ['*.ttf', '*.otf']:
                font_files.extend(self.input_dir.glob(ext))
            font_names = [f.name for f in font_files]

            self.font_combo.configure(values=font_names)
            if font_names:
                self.font_combo.set(font_names[0])
            else:
                self.log_message("[Warning] No font files found")

            charset_files = list(self.input_dir.glob('*.txt'))
            charset_names = ['basic'] + [f.name for f in charset_files]
            self.charset_combo.configure(values=charset_names)
            if 'charset.txt' in charset_names:
                self.charset_combo.set('charset.txt')
            else:
                self.charset_combo.set(charset_names[0])

            self.refresh_txt_combos(silent=True)

        except Exception as e:
            self.log_message(f"[Error] Failed to refresh file list: {e}")

    def refresh_txt_combos(self, silent=False):
        try:
            txt_files = list(self.input_dir.glob('*.txt')) if self.input_dir.exists() else []
            names = ['none'] + [f.name for f in txt_files]

            self.h_scale_chars_combo.configure(values=names)
            if self.h_scale_chars_var.get() not in names:
                self.h_scale_chars_var.set('none')

            self.spacing_chars_combo.configure(values=names)
            if self.spacing_chars_var.get() not in names:
                self.spacing_chars_var.set('none')

            self._update_h_scale_preview()
            self._update_spacing_preview()
        except Exception as e:
            if not silent:
                self.log_message(f"[Error] Failed to refresh txt file list: {e}")

    def _on_h_scale_chars_selected(self, value=None):
        self._update_h_scale_preview()

    def _update_h_scale_preview(self):
        filename = self.h_scale_chars_var.get()
        if filename == 'none':
            self.h_scale_preview_var.set("(none: applies to all glyphs)")
            return
        path = self.input_dir / filename
        if not path.exists():
            self.h_scale_preview_var.set("(file not found)")
            return
        try:
            chars = self._parse_chars_file(path)
            self.h_scale_preview_var.set(f"({len(chars)} chars loaded)")
        except Exception:
            self.h_scale_preview_var.set("(failed to read file)")

    def _on_spacing_file_selected(self, value=None):
        self._update_spacing_preview()

    def _update_spacing_preview(self):
        filename = self.spacing_chars_var.get()
        if filename == 'none':
            self.spacing_preview_var.set("(none: applies to all glyphs)")
            return
        path = self.input_dir / filename
        if not path.exists():
            self.spacing_preview_var.set("(file not found)")
            return
        try:
            chars = self._parse_chars_file(path)
            self.spacing_preview_var.set(f"({len(chars)} chars loaded)")
        except Exception:
            self.spacing_preview_var.set("(failed to read file)")

    def _parse_chars_file(self, path) -> set:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {ord(ch) for ch in content if ch not in ('\n', '\r')}

    def open_input_folder(self):
        if not self.input_dir.exists():
            self.input_dir.mkdir(parents=True)
        os.startfile(str(self.input_dir))

    def open_output_folder(self):
        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True)
        os.startfile(str(self.output_dir))

    # ── Save / Load settings ─────────────────────────────────────────

    def save_config(self):
        config = {
            'font_file':          self.font_file_var.get(),
            'charset_file':       self.charset_var.get(),
            'font_size':          self.font_size_var.get(),
            'pxrange':            self.pxrange_var.get(),
            'padding':            self.padding_var.get(),
            'uv_inset':           self.uv_inset_var.get(),
            'font_name':          self.font_name_var.get(),
            'h_scale':            self.h_scale_var.get(),
            'h_scale_chars_file': self.h_scale_chars_var.get(),
            'spacing_chars_file': self.spacing_chars_var.get(),
            'spacing_ratio':      self.spacing_ratio_var.get(),
            'spacing_symmetric':  self.spacing_symmetric_var.get(),
        }
        filename = self.work_dir / "user_config.json"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self.log_message("Settings saved")
        except Exception as e:
            self.log_message(f"[Error] Failed to save settings")

    def load_config(self):
        filename = self.work_dir / "user_config.json"
        if not filename.exists():
            return
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.font_file_var.set(config.get('font_file', ''))
            self.charset_var.set(config.get('charset_file', ''))
            self.font_size_var.set(config.get('font_size', '74'))
            self.pxrange_var.set(config.get('pxrange', '4'))
            self.padding_var.set(config.get('padding', '0'))
            self.uv_inset_var.set(config.get('uv_inset', '0.0'))
            self.font_name_var.set(config.get('font_name', 'din_cnd_bold_msdf_0'))
            self.h_scale_var.set(config.get('h_scale', '1.0'))
            self.h_scale_chars_var.set(config.get('h_scale_chars_file', 'none'))
            self.spacing_chars_var.set(config.get('spacing_chars_file', 'none'))
            self.spacing_ratio_var.set(config.get('spacing_ratio', '1.0'))
            self.spacing_symmetric_var.set(config.get('spacing_symmetric', False))
        except Exception:
            pass

    # ── Log / Progress ───────────────────────────────────────────────

    def log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}\n"
        self.log_text.insert(ctk.END, log_line)
        self.log_text.see(ctk.END)
        self.root.update_idletasks()

    def update_progress(self, step, total, message):
        pct = step / total
        self.progress_bar.set(pct)
        self.progress_var.set(f"{message} ({step}/{total})")
        self.root.update_idletasks()

    # ── Pipeline ─────────────────────────────────────────────────────

    def run_full_pipeline(self):
        if self.is_running:
            self.log_message("[Warning] Already running.")
            return
        if not self.font_file_var.get():
            self.log_message("[Error] Please select a font file.")
            return
        font_path = self.input_dir / self.font_file_var.get()
        if not font_path.exists():
            self.log_message(f"[Error] Font file does not exist: {font_path}")
            return
        self.output_dir.mkdir(parents=True, exist_ok=True)
        thread = threading.Thread(target=self._run_pipeline_thread, daemon=True)
        thread.start()

    def _run_pipeline_thread(self):
        try:
            self.is_running = True
            self.run_button.configure(state='disabled')
            self.log_message("Pipeline started...")
            total_steps = 4

            self.update_progress(1, total_steps, "Generating MTSDF atlas...")
            if not self.step1_generate_mtsdf():
                self.log_message("[Error] Pipeline aborted: MTSDF generation failed")
                return

            self.update_progress(2, total_steps, "Converting JSON to XML...")
            if not self.step2_json_to_xml():
                self.log_message("[Error] Pipeline aborted: JSON conversion failed")
                return

            self.update_progress(3, total_steps, "Merging XML libraries...")
            if not self.step3_merge_libraries():
                self.log_message("[Error] Pipeline aborted: XML merge failed")
                return

            self.update_progress(4, total_steps, "Converting texture to DDS...")
            if not self.step4_convert_to_dds():
                self.log_message("[Warning] DDS conversion failed (continuing)")

            self.progress_bar.set(1.0)
            self.progress_var.set("Complete!")
            self.log_message("All tasks completed!")

        except Exception as e:
            self.log_message(f"[Error] Exception occurred: {e}")
        finally:
            self.is_running = False
            self.run_button.configure(state='normal')

    def step1_generate_mtsdf(self):
        self.log_message("[1/4] Generating MTSDF atlas...")
        try:
            font_path = self.input_dir / self.font_file_var.get()
            msdf_exe = resource_path('msdf-atlas-gen.exe')
            cmd = [
                msdf_exe,
                '-font', str(font_path),
                '-type', 'mtsdf',
                '-size', self.font_size_var.get(),
                '-pxrange', self.pxrange_var.get(),
                '-yorigin', 'bottom',
            ]
            padding = self.padding_var.get()
            if padding and padding != '0':
                cmd.extend(['-pxpadding', padding])
            texture_name = self.font_name_var.get()
            cmd.extend([
                '-imageout', str(self.output_dir / f'{texture_name}.png'),
                '-json',     str(self.output_dir / 'font-atlas.json'),
            ])
            charset_file = self.charset_var.get()
            if charset_file and charset_file != 'basic':
                charset_path = self.input_dir / charset_file
                if charset_path.exists():
                    cmd.extend(['-charset', str(charset_path)])

            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            result = subprocess.run(cmd, capture_output=True, text=True,
                                    encoding='utf-8', errors='ignore',
                                    startupinfo=startupinfo)
            if result.returncode == 0:
                self.log_message("MTSDF atlas generation complete")
                return True
            else:
                self.log_message(f"[Error] msdf-atlas-gen failed (code: {result.returncode})")
                if result.stderr:
                    self.log_message(f"Error: {result.stderr}")
                return False
        except Exception as e:
            self.log_message(f"[Error] MTSDF generation error: {e}")
            return False

    def step2_json_to_xml(self):
        self.log_message("[2/4] Converting JSON to XML...")
        try:
            generated_library_dir = self.output_dir / 'generated_library'
            generated_library_dir.mkdir(exist_ok=True)
            json_path    = self.output_dir / 'font-atlas.json'
            texture_name = self.font_name_var.get() + ".png"
            font_name    = self.font_name_var.get()

            if not json_path.exists():
                self.log_message(f"[Error] JSON file not found: {json_path}")
                return False
            if XMLGenerator is None:
                self.log_message("[Error] Cannot load json_to_xml module")
                return False

            try:
                h_scale = float(self.h_scale_var.get())
            except ValueError:
                self.log_message("[Warning] Invalid Horizontal Scale value, using 1.0")
                h_scale = 1.0

            h_scale_chars = None
            h_scale_filename = self.h_scale_chars_var.get()
            if h_scale_filename and h_scale_filename != 'none':
                h_scale_path = self.input_dir / h_scale_filename
                if h_scale_path.exists():
                    try:
                        h_scale_chars = self._parse_chars_file(h_scale_path)
                        self.log_message(f"H-Scale chars loaded: {len(h_scale_chars)} chars from {h_scale_filename}")
                    except Exception as e:
                        self.log_message(f"[Warning] Failed to load H-Scale chars file: {e}")
                else:
                    self.log_message(f"[Warning] H-Scale chars file not found: {h_scale_path}")

            try:
                spacing_ratio = float(self.spacing_ratio_var.get())
            except ValueError:
                self.log_message("[Warning] Invalid Spacing Ratio value, using 1.0")
                spacing_ratio = 1.0

            spacing_chars = None
            spacing_filename = self.spacing_chars_var.get()
            if spacing_filename and spacing_filename != 'none':
                spacing_path = self.input_dir / spacing_filename
                if spacing_path.exists():
                    try:
                        spacing_chars = self._parse_chars_file(spacing_path)
                        self.log_message(f"Spacing chars loaded: {len(spacing_chars)} chars from {spacing_filename}")
                    except Exception as e:
                        self.log_message(f"[Warning] Failed to load spacing chars file: {e}")
                else:
                    self.log_message(f"[Warning] Spacing chars file not found: {spacing_path}")

            spacing_symmetric = self.spacing_symmetric_var.get()

            try:
                uv_inset = float(self.uv_inset_var.get())
            except ValueError:
                self.log_message("[Warning] Invalid UV Inset value, using 0.0")
                uv_inset = 0.0

            try:
                generator = XMLGenerator(
                    str(json_path), texture_name, font_name,
                    h_scale=h_scale,
                    h_scale_chars=h_scale_chars,
                    spacing_chars=spacing_chars,
                    spacing_ratio=spacing_ratio,
                    spacing_symmetric=spacing_symmetric,
                    uv_inset=uv_inset,
                )
                generator.generate_libraries(str(generated_library_dir))
                sym_label = " symmetric" if spacing_symmetric else ""
                uv_label  = f", uv_inset={uv_inset}" if uv_inset > 0 else ""
                self.log_message(
                    f"JSON to XML conversion complete "
                    f"(h_scale={h_scale} on {'all' if h_scale_chars is None else f'{len(h_scale_chars)} chars'}, "
                    f"spacing={spacing_ratio}{sym_label} on {'all' if spacing_chars is None else f'{len(spacing_chars)} chars'}"
                    f"{uv_label})"
                )
                return True
            except Exception as e:
                self.log_message(f"[Error] JSON to XML conversion failed: {e}")
                return False
        except Exception as e:
            self.log_message(f"[Error] JSON conversion error: {e}")
            return False

    def step3_merge_libraries(self):
        self.log_message("[3/4] Merging XML libraries...")
        try:
            if merge_xml_libraries_ordered is None:
                self.log_message("[Error] Cannot load l_merge_libraries module")
                return False
            input_dir     = self.output_dir / 'generated_library'
            template_path = resource_path('separated_libraries_raw/LIBRARY_NODE.xml')
            output_path   = self.output_dir / 'node.xml'
            if not os.path.exists(template_path):
                self.log_message(f"[Error] Template file not found: {template_path}")
                return False
            if not input_dir.exists():
                self.log_message(f"[Error] Generated library folder not found: {input_dir}")
                return False
            merge_xml_libraries_ordered(str(input_dir), str(template_path), str(output_path))
            if output_path.exists():
                self.log_message("XML library merge complete")
                return True
            else:
                self.log_message("[Error] node.xml was not created")
                return False
        except Exception as e:
            self.log_message(f"[Error] XML merge error: {e}")
            import traceback
            self.log_message(traceback.format_exc())
            return False

    def step4_convert_to_dds(self):
        self.log_message("[4/4] Converting PNG to DDS...")
        try:
            texture_name = self.font_name_var.get()
            input_png    = self.output_dir / f"{texture_name}.png"
            if not input_png.exists():
                self.log_message(f"[Error] PNG file not found: {input_png}")
                return False
            texconv_exe = resource_path('texconv.exe')
            if not os.path.exists(texconv_exe):
                self.log_message(f"[Error] texconv.exe not found: {texconv_exe}")
                return False
            cmd = [
                texconv_exe,
                '-f', 'R8G8B8A8_UNORM',
                '-w', '0', '-h', '0', '-m', '1',
                '-srgb', '-y',
                '-o', str(self.output_dir),
                str(input_png)
            ]
            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    encoding='utf-8', errors='ignore',
                                    startupinfo=startupinfo)
            if result.returncode == 0:
                self.log_message("DDS conversion complete")
                return True
            else:
                self.log_message(f"[Error] texconv failed (code: {result.returncode})")
                if result.stderr:
                    self.log_message(f"Error: {result.stderr}")
                return False
        except Exception as e:
            self.log_message(f"[Error] DDS conversion error: {e}")
            return False

    def launch_coordinate_comparator(self):
        try:
            if coordinate_comparator is None:
                self.log_message("[Error] Cannot load coordinate_comparator module.")
                return
            self.log_message("Launching coordinate comparator tool...")
            coordinate_comparator.main()
            self.log_message("Coordinate comparator tool closed.")
        except Exception as e:
            self.log_message(f"[Error] Coordinate comparator tool launch failed: {e}")


def main():
    try:
        print("Dr2 Font Generator starting...")
        root = ctk.CTk()
        app = FontPipelineManager(root)
        # 초기 크기: 화면 중앙, 최소 크기 제한 없음
        W, H = 700, 980
        x = (root.winfo_screenwidth() // 2) - (W // 2)
        y = 30
        root.geometry(f'{W}x{H}+{x}+{y}')
        root.mainloop()
    except Exception as e:
        print(f"[Error] Error occurred: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
