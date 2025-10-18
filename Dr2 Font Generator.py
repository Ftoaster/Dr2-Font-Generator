"""
MTSDF Font Pipeline Manager - GUI Tool

Manages all font conversion pipeline in one GUI:
1. MTSDF Atlas Generation
2. JSON → PSSG XML Conversion
3. XML Library Merging
4. Texture PNG → DDS Conversion
5. Coordinate Verification Tool
"""

import tkinter as tk
from tkinter import ttk, filedialog
import subprocess
import os
import json
import sys
from pathlib import Path
import threading
from datetime import datetime

# Import local modules
try:
    from json_to_pssg import PSSGGenerator
    from l_merge_libraries import merge_xml_libraries_ordered
    import coordinate_comparator
except ImportError as e:
    print(f"Module import failed: {e}")
    PSSGGenerator = None
    merge_xml_libraries_ordered = None
    coordinate_comparator = None

# PyInstaller bundle resource path helper function
def resource_path(relative_path):
    """Returns resource path from PyInstaller bundle or external"""
    try:
        # PyInstaller temp folder
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        # Normal Python script execution
        base_path = Path(__file__).parent
    
    return str(base_path / relative_path)

class FontPipelineManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Dr2 Font Generator")
        self.root.geometry("520x700")
        
        # Working directory (correct path for EXE execution)
        if getattr(sys, 'frozen', False):
            # PyInstaller built EXE execution
            self.work_dir = Path(sys.executable).parent
        else:
            # Normal Python script execution
            self.work_dir = Path(__file__).parent
        
        os.chdir(self.work_dir)
        
        # Set window icon
        try:
            # Find icon from inside or outside EXE
            if getattr(sys, 'frozen', False):
                # PyInstaller bundle internal path
                bundle_dir = Path(sys._MEIPASS)
                icon_path = bundle_dir / 'icon.ico'
                if not icon_path.exists():
                    # Bundle external (same folder as EXE)
                    icon_path = self.work_dir / 'icon.ico'
            else:
                icon_path = self.work_dir / 'icon.ico'
            
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except Exception as e:
            print(f"Icon load failed: {e}")
        
        # Default settings (fixed folder paths)
        self.input_dir = self.work_dir / 'witchs_pot'
        self.output_dir = self.work_dir / 'witchs_gift'
        
        self.config = {
            'font_file': '',
            'charset_file': '',
            'font_size': '74',
            'pxrange': '4',
            'font_name': 'din_cnd_bold_msdf_0',
        }
        
        # Running flag
        self.is_running = False
        
        # Create UI
        self.setup_ui()
        
        # Auto load settings (without log)
        self.load_config()
    
    def setup_ui(self):
        """UI setup"""
        # Main frame (without tabs)
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # === Main pipeline setup ===
        self.setup_main_tab(main_frame)
    
    def setup_main_tab(self, parent):
        """Main pipeline tab setup"""
        # === 1. File Selection ===
        file_frame = ttk.LabelFrame(parent, text="File Selection", padding=10)
        file_frame.pack(fill='x', pady=5)
        
        # Grid layout
        # Font file
        ttk.Label(file_frame, text="Font File:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.font_file_var = tk.StringVar()
        self.font_combo = ttk.Combobox(file_frame, textvariable=self.font_file_var, 
                                       width=40, state='readonly')
        self.font_combo.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="Refresh", 
                  command=self.refresh_font_list, width=10).grid(row=0, column=2, padx=5, pady=5)
        
        # Charset file
        ttk.Label(file_frame, text="Charset File:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.charset_var = tk.StringVar()
        self.charset_combo = ttk.Combobox(file_frame, textvariable=self.charset_var, 
                                         width=40, state='readonly')
        self.charset_combo.grid(row=1, column=1, padx=5, pady=5)
        
        # === 2. MTSDF Settings ===
        mtsdf_frame = ttk.LabelFrame(parent, text="MTSDF Settings", padding=10)
        mtsdf_frame.pack(fill='x', pady=5)
        
        # Grid layout
        # Font size
        ttk.Label(mtsdf_frame, text="Font Size:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.font_size_var = tk.StringVar(value=self.config['font_size'])
        ttk.Entry(mtsdf_frame, textvariable=self.font_size_var, width=20).grid(row=0, column=1, sticky='w', padx=5, pady=5)
        
        # pxrange
        ttk.Label(mtsdf_frame, text="Distance Range (pxrange):").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.pxrange_var = tk.StringVar(value=self.config['pxrange'])
        ttk.Entry(mtsdf_frame, textvariable=self.pxrange_var, width=20).grid(row=1, column=1, sticky='w', padx=5, pady=5)
        
        # Output filename
        ttk.Label(mtsdf_frame, text="Output Filename:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.font_name_var = tk.StringVar(value=self.config['font_name'])
        self.font_name_combo = ttk.Combobox(mtsdf_frame, textvariable=self.font_name_var, width=38)
        self.font_name_combo['values'] = [
            'din_cnd_bold_ita_msdf_0',
            'din_cnd_bold_msdf_0',
            'roboto_cnd_reg_msdf_0'
        ]
        self.font_name_combo.grid(row=2, column=1, sticky='w', padx=5, pady=5)
        
        # === 3. Action Buttons ===
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill='x', pady=10)
        
        self.run_button = ttk.Button(button_frame, text="Run", 
                                     command=self.run_full_pipeline, width=15)
        self.run_button.pack(side='left', padx=5)
        
        ttk.Button(button_frame, text="Save Settings", 
                  command=self.save_config, width=15).pack(side='left', padx=5)
        
        ttk.Button(button_frame, text="Open Input Folder", 
                  command=self.open_input_folder, width=15).pack(side='left', padx=5)
        
        ttk.Button(button_frame, text="Open Output Folder", 
                  command=self.open_output_folder, width=15).pack(side='left', padx=5)
        
        # === 4. Progress ===
        progress_frame = ttk.LabelFrame(parent, text="Progress", padding=10)
        progress_frame.pack(fill='x', pady=5)
        
        self.progress_var = tk.StringVar(value="Waiting...")
        ttk.Label(progress_frame, textvariable=self.progress_var).pack(anchor='w')
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress_bar.pack(fill='x', pady=5)
        
        # === 5. Log ===
        log_frame = ttk.LabelFrame(parent, text="Log", padding=10)
        log_frame.pack(fill='both', expand=True, pady=5)
        
        # Log text widget
        log_scroll = ttk.Scrollbar(log_frame)
        log_scroll.pack(side='right', fill='y')
        
        self.log_text = tk.Text(log_frame, height=10, yscrollcommand=log_scroll.set)
        self.log_text.pack(fill='both', expand=True)
        log_scroll.config(command=self.log_text.yview)
        
        # === 6. Font Viewer Button ===
        viewer_frame = ttk.Frame(parent)
        viewer_frame.pack(fill='x', pady=5)
        
        ttk.Button(viewer_frame, text="Launch Font Viewer", 
                  command=self.launch_coordinate_comparator, width=20).pack(pady=5)
        
        # Initialize file list
        self.refresh_font_list()
    
    # === File list and folder functions ===
    
    def refresh_font_list(self):
        """Refresh font file list from witchs_pot folder"""
        try:
            # Create witchs_pot folder if not exists
            if not self.input_dir.exists():
                self.input_dir.mkdir(parents=True)
                self.log_message(f"Input folder created: {self.input_dir}")
            
            # Find font files (.ttf, .otf)
            font_files = []
            for ext in ['*.ttf', '*.otf']:
                font_files.extend(self.input_dir.glob(ext))
            
            font_names = [f.name for f in font_files]
            self.font_combo['values'] = font_names
            
            if font_names:
                self.font_combo.current(0)
            else:
                self.log_message(f"[Warning] No font files found")
            
            # Find charset files (.txt)
            charset_files = list(self.input_dir.glob('*.txt'))
            charset_names = ['basic'] + [f.name for f in charset_files]
            self.charset_combo['values'] = charset_names
            
            # Auto select charset.txt if exists, otherwise basic
            if 'charset.txt' in charset_names:
                self.charset_combo.set('charset.txt')
            else:
                self.charset_combo.current(0)
            
        except Exception as e:
            self.log_message(f"[Error] Failed to refresh file list: {e}")
    
    def open_input_folder(self):
        """Open input folder"""
        if self.input_dir.exists():
            os.startfile(str(self.input_dir))
        else:
            self.input_dir.mkdir(parents=True)
            os.startfile(str(self.input_dir))
    
    def open_output_folder(self):
        """Open output folder"""
        if self.output_dir.exists():
            os.startfile(str(self.output_dir))
        else:
            self.output_dir.mkdir(parents=True)
            os.startfile(str(self.output_dir))
    
    # === Save/Load settings ===
    
    def save_config(self):
        """Save settings to JSON file"""
        config = {
            'font_file': self.font_file_var.get(),
            'charset_file': self.charset_var.get(),
            'font_size': self.font_size_var.get(),
            'pxrange': self.pxrange_var.get(),
            'font_name': self.font_name_var.get(),
        }
        
        # Auto save to current folder
        filename = self.work_dir / "user_config.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self.log_message("Settings saved")
        except Exception as e:
            self.log_message(f"[Error] Failed to save settings")
    
    def load_config(self):
        """Load settings from JSON file"""
        # Auto load user_config.json from current folder
        filename = self.work_dir / "user_config.json"
        
        if not filename.exists():
            return
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Update UI
            self.font_file_var.set(config.get('font_file', ''))
            self.charset_var.set(config.get('charset_file', ''))
            self.font_size_var.set(config.get('font_size', '74'))
            self.pxrange_var.set(config.get('pxrange', '4'))
            self.font_name_var.set(config.get('font_name', 'din_cnd_bold_msdf_0'))
        except Exception as e:
            pass  # Silently ignore
    
    # === Log functions ===
    
    def log_message(self, message):
        """Log message output"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_line)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def update_progress(self, step, total, message):
        """Update progress"""
        percentage = (step / total) * 100
        self.progress_bar['value'] = percentage
        self.progress_var.set(f"{message} ({step}/{total})")
        self.root.update_idletasks()
    
    # === Main pipeline execution ===
    
    def run_full_pipeline(self):
        """Run full pipeline"""
        if self.is_running:
            self.log_message("[Warning] Already running.")
            return
        
        # Input validation
        if not self.font_file_var.get():
            self.log_message("[Error] Please select a font file.")
            return
        
        font_path = self.input_dir / self.font_file_var.get()
        if not font_path.exists():
            self.log_message(f"[Error] Font file does not exist: {font_path}")
            return
        
        # Create output folder
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Run in separate thread
        thread = threading.Thread(target=self._run_pipeline_thread, daemon=True)
        thread.start()
    
    def _run_pipeline_thread(self):
        """Pipeline execution (separate thread)"""
        try:
            self.is_running = True
            self.run_button.config(state='disabled')
            
            self.log_message("Pipeline started...")
            
            total_steps = 4  # MTSDF generation, JSON conversion, XML merge, DDS conversion
            
            # Step 1: MTSDF atlas generation
            self.update_progress(1, total_steps, "Generating MTSDF atlas...")
            if not self.step1_generate_mtsdf():
                self.log_message("[Error] Pipeline aborted: MTSDF generation failed")
                return
            
            # Step 2: JSON → PSSG XML conversion
            self.update_progress(2, total_steps, "Converting JSON to PSSG XML...")
            if not self.step2_json_to_pssg():
                self.log_message("[Error] Pipeline aborted: JSON conversion failed")
                return
            
            # Step 3: XML library merge
            self.update_progress(3, total_steps, "Merging XML libraries...")
            if not self.step3_merge_libraries():
                self.log_message("[Error] Pipeline aborted: XML merge failed")
                return
            
            # Step 4: DDS conversion (always run)
            self.update_progress(4, total_steps, "Converting texture to DDS...")
            if not self.step4_convert_to_dds():
                self.log_message("[Warning] DDS conversion failed (continuing)")
            
            # Complete
            self.progress_bar['value'] = 100
            self.progress_var.set("Complete!")
            
            self.log_message("All tasks completed!")
            
        except Exception as e:
            self.log_message(f"[Error] Exception occurred: {e}")
        
        finally:
            self.is_running = False
            self.run_button.config(state='normal')
    
    def step1_generate_mtsdf(self):
        """Step 1: MTSDF atlas generation"""
        self.log_message("[1/4] Generating MTSDF atlas...")
        
        try:
            # Full path to font file
            font_path = self.input_dir / self.font_file_var.get()
            
            # Build command (use bundled executable path)
            msdf_exe = resource_path('msdf-atlas-gen.exe')
            cmd = [
                msdf_exe,
                '-font', str(font_path),
                '-type', 'mtsdf',
                '-size', self.font_size_var.get(),
                '-pxrange', self.pxrange_var.get(),
                '-yorigin', 'bottom',  # Always apply
            ]
            
            texture_name = self.font_name_var.get()
            cmd.extend([
                '-imageout', str(self.output_dir / f'{texture_name}.png'),
                '-json', str(self.output_dir / 'font-atlas.json'),
            ])
            
            # Add charset file if exists
            charset_file = self.charset_var.get()
            if charset_file and charset_file != 'basic':
                charset_path = self.input_dir / charset_file
                if charset_path.exists():
                    cmd.extend(['-charset', str(charset_path)])
            
            # Run (hide console window on Windows)
            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', 
                                  errors='ignore', startupinfo=startupinfo)
            
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
    
    def step2_json_to_pssg(self):
        """Step 2: JSON → PSSG XML conversion"""
        self.log_message("[2/4] Converting JSON to PSSG XML...")
        
        try:
            generated_library_dir = self.output_dir / 'generated_library'
            generated_library_dir.mkdir(exist_ok=True)
            
            json_path = self.output_dir / 'font-atlas.json'
            texture_name = self.font_name_var.get() + ".png"
            font_name = self.font_name_var.get()
            
            if not json_path.exists():
                self.log_message(f"[Error] JSON file not found: {json_path}")
                return False
            
            # Direct call to json_to_pssg
            if PSSGGenerator is None:
                self.log_message("[Error] Cannot load json_to_pssg module")
                return False
            
            try:
                generator = PSSGGenerator(str(json_path), texture_name, font_name)
                generator.generate_libraries(str(generated_library_dir))
                self.log_message("JSON to PSSG XML conversion complete")
                return True
            except Exception as e:
                self.log_message(f"[Error] JSON to PSSG XML conversion failed: {e}")
                return False
                
        except Exception as e:
            self.log_message(f"[Error] JSON conversion error: {e}")
            return False
    
    def step3_merge_libraries(self):
        """Step 3: XML library merge"""
        self.log_message("[3/4] Merging XML libraries...")
        
        try:
            # Direct call to l_merge_libraries
            if merge_xml_libraries_ordered is None:
                self.log_message("[Error] Cannot load l_merge_libraries module")
                return False
            
            input_dir = self.output_dir / 'generated_library'
            template_path = self.work_dir / 'separated_libraries_raw' / 'LIBRARY_NODE.xml'
            output_path = self.output_dir / 'node.xml'
            
            merge_xml_libraries_ordered(str(input_dir), str(template_path), str(output_path))
            self.log_message("XML library merge complete")
            return True
                
        except Exception as e:
            self.log_message(f"[Error] XML merge error: {e}")
            return False
    
    def step4_convert_to_dds(self):
        """Step 4: PNG → DDS conversion"""
        self.log_message("[4/4] Converting PNG to DDS...")
        
        try:
            texture_name = self.font_name_var.get()
            input_png = self.output_dir / f"{texture_name}.png"
            
            if not input_png.exists():
                self.log_message(f"[Error] PNG file not found: {input_png}")
                return False
            
            # Run texconv (use bundled executable path)
            texconv_exe = resource_path('texconv.exe')
            if not os.path.exists(texconv_exe):
                self.log_message(f"[Error] texconv.exe not found: {texconv_exe}")
                return False
            
            cmd = [
                texconv_exe,
                '-f', 'R8G8B8A8_UNORM',
                '-w', '0',
                '-h', '0',
                '-m', '1',
                '-srgb',
                '-y',
                '-o', str(self.output_dir),
                str(input_png)
            ]
            
            # Run (hide console window on Windows)
            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', 
                                  errors='ignore', startupinfo=startupinfo)
            
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
    
    # === Verification tool execution ===
    
    def launch_coordinate_comparator(self):
        """Launch coordinate comparator tool"""
        try:
            if coordinate_comparator is None:
                self.log_message("[Error] Cannot load coordinate_comparator module.")
                return
            
            self.log_message("Launching coordinate comparator tool...")
            
            # Direct call since Tkinter is only safe in main thread
            # Main GUI will wait until the new window closes
            coordinate_comparator.main()
            
            self.log_message("Coordinate comparator tool closed.")
            
        except Exception as e:
            self.log_message(f"[Error] Coordinate comparator tool launch failed: {e}")


def main():
    try:
        print("Dr2 Font Generator starting...")
        
        root = tk.Tk()
        app = FontPipelineManager(root)
        
        # Center window
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f'{width}x{height}+{x}+{y}')
        
        root.mainloop()
        
    except Exception as e:
        print(f"[Error] Error occurred: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
