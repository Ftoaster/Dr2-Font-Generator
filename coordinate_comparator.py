"""
Font Coordinate Viewer - Original vs New File Visualization Tool
"""
import tkinter as tk
from tkinter import ttk, messagebox
import json
import xml.etree.ElementTree as ET
import struct
import os
import sys
from pathlib import Path
from PIL import Image, ImageTk

# Helper function to find PyInstaller bundled resource paths
def resource_path(relative_path):
    """Returns resource path from inside or outside PyInstaller bundle"""
    try:
        # Temporary folder created by PyInstaller
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        # Running as regular Python script
        base_path = Path(__file__).parent
    
    return base_path / relative_path

class CoordinateComparator:
    def __init__(self, root):
        
        self.root = root
        self.root.title("Font Coordinate Viewer")
        
        # Set working directory (use correct path when running as EXE)
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller-built EXE
            self.work_dir = Path(sys.executable).parent
        else:
            # Running as regular Python script
            self.work_dir = Path(__file__).parent
        os.chdir(self.work_dir)
        
        # Load Atlas image size
        self.atlas_width, self.atlas_height = self.load_atlas_size()
        
        # Calculate window size based on atlas aspect ratio
        self.calculate_window_size()
        
        # Use resource_path() for bundled resources, work_dir for external folders
        self.font_paths = {
            'original_pssg': 'b_fonts_jpn.pssg',
            'original_node': resource_path('separated_libraries_raw') / 'LIBRARY_NODE.xml',
            'original_segmentset': resource_path('separated_libraries_raw') / 'LIBRARY_SEGMENTSET.xml',
            'original_renderinterfacebound': resource_path('separated_libraries_raw') / 'LIBRARY_RENDERINTERFACEBOUND.xml',
            'original_fontmetrics': resource_path('separated_libraries_raw') / 'LIBRARY_NEFONTMETRICS.xml',
            'original_glyphmetrics': resource_path('separated_libraries_raw') / 'LIBRARY_NEGLYPHMETRICS.xml',
            'new_fontmetrics': self.work_dir / 'witchs_gift' / 'generated_library' / 'LIBRARY_NEFONTMETRICS.xml',
            'new_glyphmetrics': self.work_dir / 'witchs_gift' / 'generated_library' / 'LIBRARY_NEGLYPHMETRICS.xml',
            'new_json': self.work_dir / 'witchs_gift' / 'font-atlas.json'
        }
        
        # Atlas image paths (original_texture is bundled)
        self.atlas_paths = {
            'original': resource_path('original_texture'),
            'new': self.find_new_atlas_texture()
        }
        
        # Image cache (PhotoImage must maintain references)
        self.tk_images = []
        
        # metrics cache
        self.font_metrics = {}
        self.glyph_metrics = {}
        
        # Loaded data cache (stores both Original and transformed coordinates)
        self.loaded_data = {}

        # Create UI elements
        self.setup_ui()
        
        # Check required file paths
        self.check_file_paths()
        
        self.log_message(" App initialization complete")
    
    def find_new_atlas_texture(self):
        """Automatically finds PNG file in witchs_gift folder"""
        try:
            witchs_gift_dir = self.work_dir / 'witchs_gift'
            if not witchs_gift_dir.exists():
                return None
            
            # Find .png files in witchs_gift folder
            png_files = list(witchs_gift_dir.glob('*.png'))
            
            if png_files:
                # Return first PNG file
                return png_files[0]
            
            return None
        except Exception as e:
            print(f"[Warning] PNG file search failed: {e}")
            return None
    
    def load_atlas_size(self):
        """Load atlas image size from JSON"""
        try:
            json_path = 'witchs_gift/font-atlas.json'
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if 'atlas' in data:
                    width = data['atlas'].get('width', 2048)
                    height = data['atlas'].get('height', 2048)
                    print(f" Atlas size: {width}x{height}")
                    return width, height
        except Exception as e:
            print(f"[Warning] Atlas size loading failed: {e}")
        
        # Default values
        return 2048, 2048
    
    def calculate_window_size(self):
        """Calculate window and canvas size based on Atlas aspect ratio"""
        # Atlas aspect ratio
        atlas_ratio = self.atlas_width / self.atlas_height
        
        # Base pixel size for UV box (match grid range 1.5)
        base_scale = 300  # 300px = 1.0 Position unit
        uv_box_base = int(base_scale * 1.5)  # ±1.5 range = 450px
        
        # UV box size (maintain aspect ratio)
        if atlas_ratio >= 1.0:
            # Wider
            self.uv_box_width = uv_box_base
            self.uv_box_height = int(uv_box_base / atlas_ratio)
        else:
            # Taller
            self.uv_box_width = int(uv_box_base * atlas_ratio)
            self.uv_box_height = uv_box_base
        
        # Grid range (±1.5 range)
        self.grid_scale = base_scale  # 300px = 1.0 Position unit
        grid_range_x = int(base_scale * 1.5)  # ±1.5 = 450px
        grid_range_y = int(base_scale * 1.5)  # ±1.5 = 450px
        
        # Canvas size (grid ±1.5 range + minimum margin)
        margin = 80  # Reduced margin (200 -> 80)
        self.canvas_width = (grid_range_x * 2) + margin * 2
        self.canvas_height = (grid_range_y * 2) + margin * 2
        
        # Window size (canvas + control + log) - 15% reduction
        window_width = int((self.canvas_width + 30) * 0.85)
        window_height = int((self.canvas_height + 250) * 0.85)  # Control + log area reduced
        
        self.root.geometry(f"{window_width}x{window_height}")
        
        print(f" UV box size: {self.uv_box_width}x{self.uv_box_height}")
        print(f" Canvas size: {self.canvas_width}x{self.canvas_height}")
        print(f" Window size: {window_width}x{window_height}")
    
    def setup_ui(self):
        """Create and arrange UI elements."""
        # Control frame (top)
        control_frame = ttk.Frame(self.root)
        control_frame.pack(side=tk.TOP, pady=10)
        
        # Character input
        ttk.Label(control_frame, text="Characters to compare:").pack(side=tk.LEFT, padx=(10, 2))
        self.char_entry = ttk.Entry(control_frame, width=20)
        self.char_entry.pack(side=tk.LEFT, padx=5)
        self.char_entry.insert(0, "c, 1, A") # Default
        
        ttk.Button(control_frame, text="Start Comparison", command=self.compare_coordinates).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Clear Canvas", command=self.clear_canvas).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Check File Paths", command=self.check_file_paths).pack(side=tk.LEFT, padx=5)
        
        # Checkbox frame (below control)
        checkbox_frame = ttk.Frame(self.root)
        checkbox_frame.pack(side=tk.TOP, pady=5)
        
        # Explicitly specify master for BooleanVar
        self.show_original = tk.BooleanVar(master=self.root, value=True)  # Default ON
        self.show_new = tk.BooleanVar(master=self.root, value=True)  # Default ON
        self.show_glyph_image = tk.BooleanVar(master=self.root, value=True)  # Default ON
        self.apply_baseline_transform = tk.BooleanVar(master=self.root, value=True)  # Baseline transform default ON
        
        # Use tk.Checkbutton (more stable than ttk)
        tk.Checkbutton(checkbox_frame, text="Show Original Box (Solid)", variable=self.show_original,
                       command=self.redraw_if_loaded).pack(side=tk.LEFT, padx=10)
        tk.Checkbutton(checkbox_frame, text="Show New Box (Dashed)", variable=self.show_new,
                       command=self.redraw_if_loaded).pack(side=tk.LEFT, padx=10)
        tk.Checkbutton(checkbox_frame, text="Show Glyph Image", variable=self.show_glyph_image,
                       command=self.redraw_if_loaded).pack(side=tk.LEFT, padx=10)
        tk.Checkbutton(checkbox_frame, text="Transform Position Y (Baseline=0)", variable=self.apply_baseline_transform,
                       command=self.redraw_if_loaded).pack(side=tk.LEFT, padx=10)
        
        # Canvas setup (center) - auto-adjust to window size
        canvas_frame = ttk.Frame(self.root)
        canvas_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.canvas = tk.Canvas(canvas_frame, bg='white')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bind to window resize event
        self.canvas.bind('<Configure>', self.on_canvas_resize)
        
        # Info text (bottom)
        self.info_text = tk.Text(self.root, height=10, width=120)
        self.info_text.pack(side=tk.BOTTOM, pady=10)

        # Setup insert wrapper synchronized with console
        self._info_text_insert = self.info_text.insert
        def logging_insert(index, message):
            if message:
                print(message.rstrip("\n"))
            self._info_text_insert(index, message)
        self.info_text.insert = logging_insert
        
        # Store coordinates data
        self.coordinates = {}
        
        # Dictionary for storing click info
        self.item_info = {}
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        
        # Store last comparison input (for checkbox toggle)
        self.last_char_input = None

    def on_canvas_click(self, event):
        """Called on canvas click to display info of the nearest item."""
        canvas = event.widget
        x, y = canvas.canvasx(event.x), canvas.canvasy(event.y)
        
        # find_closest returns a tuple, so get the first element
        item_ids = canvas.find_closest(x, y)
        if not item_ids:
            return
        
        item_id = item_ids[0]
        
        if item_id in self.item_info:
            info_str = self.item_info[item_id]
            self.log_message(f"🖱️ Selected item: {info_str}")
            messagebox.showinfo("Selected Character Info", info_str)
        else:
            # Debug: Check clicked item ID and stored info
            print(f"Clicked item ID: {item_id}, no info")
            # print(self.item_info)

    def on_closing(self):
        """Called when window is closing."""
        self.log_message("Font Coordinate Viewer closing.")
        self.root.destroy()

    def load_font_metrics(self, source='original'):
        """Font metrics loading (NEFONTMETRICS)"""
        try:
            if source == 'original':
                metrics_path = self.font_paths['original_fontmetrics']
            else:
                metrics_path = self.font_paths['new_fontmetrics']
            
            if not os.path.exists(metrics_path):
                self.log_message(f"[Warning] Font metrics file not found: {metrics_path}")
                return None
            
            tree = ET.parse(metrics_path)
            root = tree.getroot()
            
            fontmetrics_elem = root.find('.//NEFONTMETRICS')
            if fontmetrics_elem is None:
                return None
            
            metrics = {
                'scale': float(fontmetrics_elem.get('scale', 1000)),
                'ascender': float(fontmetrics_elem.get('ascender', 0)),
                'descender': float(fontmetrics_elem.get('descender', 0)),
                'maximumAdvanceWidth': float(fontmetrics_elem.get('maximumAdvanceWidth', 0)),
                'numCharacters': int(fontmetrics_elem.get('numCharacters', 0)),
                'source': source
            }
            
            self.font_metrics[source] = metrics
            self.log_message(f" {source} font metrics loaded: scale={metrics['scale']}, ascender={metrics['ascender']}, descender={metrics['descender']}")
            return metrics
            
        except Exception as e:
            self.log_message(f"[Error] Font metrics loading error ({source}): {e}")
            return None
    
    def load_glyph_metrics(self, codepoint, source='original'):
        """Load individual glyph metrics (NEGLYPHMETRICS)"""
        try:
            if source == 'original':
                metrics_path = self.font_paths['original_glyphmetrics']
            else:
                metrics_path = self.font_paths['new_glyphmetrics']
            
            if not os.path.exists(metrics_path):
                return None
            
            # Check cache
            cache_key = f"{source}_{codepoint}"
            if cache_key in self.glyph_metrics:
                return self.glyph_metrics[cache_key]
            
            tree = ET.parse(metrics_path)
            root = tree.getroot()
            
            # codePoint로 NEGLYPHMETRICS 찾기
            glyph_elem = root.find(f'.//NEGLYPHMETRICS[@codePoint="{codepoint}"]')
            if glyph_elem is None:
                return None
            
            metrics = {
                'advanceWidth': float(glyph_elem.get('advanceWidth', 0)),
                'horizontalBearing': float(glyph_elem.get('horizontalBearing', 0)),
                'verticalBearing': float(glyph_elem.get('verticalBearing', 0)),
                'physicalWidth': float(glyph_elem.get('physicalWidth', 0)),
                'physicalHeight': float(glyph_elem.get('physicalHeight', 0)),
                'codePoint': int(glyph_elem.get('codePoint', 0)),
                'source': source
            }
            
            # Store in cache
            self.glyph_metrics[cache_key] = metrics
            return metrics
            
        except Exception as e:
            self.log_message(f"[Warning] Glyph metrics loading error ({source}, {codepoint}): {e}")
            return None
    
    def calculate_position_from_metrics(self, glyph_metrics, font_metrics):
        """Calculate Position coordinates from metrics"""
        scale = font_metrics['scale']
        
        # Calculate normalized coordinates
        pos_left = glyph_metrics['horizontalBearing'] / scale
        pos_right = (glyph_metrics['horizontalBearing'] + glyph_metrics['physicalWidth']) / scale
        pos_top = glyph_metrics['verticalBearing'] / scale
        pos_bottom = (glyph_metrics['verticalBearing'] - glyph_metrics['physicalHeight']) / scale
        
        # 4 vertices (top-left, bottom-left, bottom-right, top-right)
        positions = [
            (pos_left, pos_top, 0.0),       # 좌상
            (pos_left, pos_bottom, 0.0),    # 좌하
            (pos_right, pos_bottom, 0.0),   # 우하
            (pos_right, pos_top, 0.0),      # 우상
        ]
        
        return positions
    
    def check_file_paths(self):
        """Check if required files exist"""
        # Use resource_path for bundled resources
        required_files = [
            (resource_path("separated_libraries_raw/LIBRARY_NODE.xml"), "separated_libraries_raw/LIBRARY_NODE.xml"),
            (resource_path("separated_libraries_raw/LIBRARY_SEGMENTSET.xml"), "separated_libraries_raw/LIBRARY_SEGMENTSET.xml"), 
            (resource_path("separated_libraries_raw/LIBRARY_RENDERINTERFACEBOUND.xml"), "separated_libraries_raw/LIBRARY_RENDERINTERFACEBOUND.xml"),
            (resource_path("separated_libraries_raw/LIBRARY_NEFONTMETRICS.xml"), "separated_libraries_raw/LIBRARY_NEFONTMETRICS.xml"),
            (resource_path("separated_libraries_raw/LIBRARY_NEGLYPHMETRICS.xml"), "separated_libraries_raw/LIBRARY_NEGLYPHMETRICS.xml"),
            (self.work_dir / "witchs_gift/font-atlas.json", "witchs_gift/font-atlas.json")
        ]
        
        optional_files = [
            (self.work_dir / "witchs_gift/generated_library/LIBRARY_NEFONTMETRICS.xml", "witchs_gift/generated_library/LIBRARY_NEFONTMETRICS.xml"),
            (self.work_dir / "witchs_gift/generated_library/LIBRARY_NEGLYPHMETRICS.xml", "witchs_gift/generated_library/LIBRARY_NEGLYPHMETRICS.xml")
        ]
        
        missing_files = []
        for full_path, display_path in required_files:
            if not os.path.exists(full_path):
                missing_files.append(display_path)
        
        if missing_files:
            self.log_message("[Error] Missing required files:")
            for file_path in missing_files:
                self.log_message(f"  - {file_path}")
            self.log_message("")
        else:
            self.log_message(" All required files exist.")
        
        # Check optional files
        missing_optional = []
        for full_path, display_path in optional_files:
            if not os.path.exists(full_path):
                missing_optional.append(display_path)
        
        if missing_optional:
            self.log_message("[Info] Missing optional files (new file metrics):")
            for file_path in missing_optional:
                self.log_message(f"  - {file_path}")
        
        self.log_message("")
        
        # Attempt Font metrics loading
        self.load_font_metrics('original')
        if not missing_optional:
            self.load_font_metrics('new')
    
    def clear_canvas(self):
        """Clear all items from canvas."""
        self.canvas.delete("all")
        # Clear image cache
        self.tk_images.clear()
    
    def on_canvas_resize(self, event):
        """Called on canvas resize - redraws content to fit current size"""
        # Store new canvas size
        new_width = event.width
        new_height = event.height
        
        # Ignore if size is too small
        if new_width < 100 or new_height < 100:
            return
        
        # Update canvas size
        self.canvas_width = new_width
        self.canvas_height = new_height
        
        # Redraw if data is loaded
        if self.loaded_data:
            self.redraw_if_loaded()
    
    def draw_canvas_layout(self):
        """Draw Canvas layout (title, UV box, grid, crosshair)"""
        # Title
        self.canvas.create_text(self.canvas_width//2, 20, 
                               text=f"Position coordinates comparison (origin at center, solid=Original, dashed=new file)", 
                               fill='black', font=('Arial', 14, 'bold'))
        
        # UV comparison box
        origin_x = self.canvas_width // 2
        origin_y = self.canvas_height // 2
        
        uv_box_x1 = origin_x - self.uv_box_width
        uv_box_y1 = origin_y - self.uv_box_height
        uv_box_x2 = origin_x
        uv_box_y2 = origin_y
        
        self.canvas.create_rectangle(uv_box_x1, uv_box_y1, uv_box_x2, uv_box_y2, 
                                    outline='#AAAAAA', width=2, dash=(5, 3))
        self.canvas.create_text(uv_box_x1 + 5, uv_box_y1 + 5, 
                               text=f"[UV coordinates comparison] {self.atlas_width}x{self.atlas_height}", 
                               fill='#666666', font=('Arial', 9, 'bold'), anchor='nw')
        self.canvas.create_text((uv_box_x1 + uv_box_x2) // 2, uv_box_y2 - 10, 
                               text="solid=Original | dashed=new", 
                               fill='#999999', font=('Arial', 7), anchor='center')
        
        # Draw grid
        self.draw_grid()
        
        # Center crosshair for position rendering area
        self.draw_position_crosshair()
    
    def redraw_if_loaded(self):
        """Redraw only canvas with already loaded data when checkbox changes"""
        if not self.loaded_data:
            return
        
        # Clear canvas and redraw (no file loading)
        self.clear_canvas()
        
        # Redraw title and grid
        self.draw_canvas_layout()
        
        # Render with stored data
        self.render_loaded_data()
    
    def render_loaded_data(self):
        """Render with stored data"""
        # UV rendering settings
        pos_origin_x = self.canvas_width // 2
        pos_origin_y = self.canvas_height // 2
        uv_offset_x = pos_origin_x - self.uv_box_width + 10
        uv_offset_y = pos_origin_y - self.uv_box_height + 30
        uv_scale = min(self.uv_box_width, self.uv_box_height) - 20
        
        for codepoint, data in self.loaded_data.items():
            color = data['color']
            char = chr(codepoint) if codepoint < 0x110000 else '?'
            original_data = data.get('original')
            new_data = data.get('new')
            
            # 체크박스 상태에 따라 UV coordinates 그리기
            if self.show_original.get() and original_data:
                self.draw_rectangle(original_data['uvs'], color, f"{char}", codepoint, "Original", 
                                  uv_offset_x, uv_offset_y, style='solid', scale=uv_scale)
            if self.show_new.get() and new_data:
                self.draw_rectangle(new_data['uvs'], color, f"{char}", codepoint, "New", 
                                  uv_offset_x, uv_offset_y, style='dashed', scale=uv_scale)
            
            # Position Y 변환 체크박스 상태에 따라 coordinates 선택
            use_transformed = self.apply_baseline_transform.get()
            
            # 체크박스 상태에 따라 Position coordinates 그리기
            if self.show_original.get() and original_data:
                positions = original_data['positions_transformed'] if use_transformed else original_data['positions_raw']
                self.draw_position_rectangle(positions, original_data['uvs'], None, 
                                            color, f"{char}", codepoint, "Original", 
                                            pos_origin_x, pos_origin_y, style='solid', 
                                            source=original_data.get('source', 'original'))
            if self.show_new.get() and new_data:
                positions = new_data['positions_transformed'] if use_transformed else new_data['positions_raw']
                self.draw_position_rectangle(positions, new_data['uvs'], None, 
                                            color, f"{char}", codepoint, "New", 
                                            pos_origin_x, pos_origin_y, style='dashed', 
                                            source=new_data.get('source', 'generated_library'))
            
            # 체크박스 상태에 따라 글자 이미지 렌더링
            if self.show_glyph_image.get():
                if self.show_original.get() and original_data:
                    positions = original_data['positions_transformed'] if use_transformed else original_data['positions_raw']
                    self.render_glyph_image(
                        positions,
                        original_data['uvs'],
                        original_data.get('texture'),
                        pos_origin_x,
                        pos_origin_y,
                        source='original'
                    )
                if self.show_new.get() and new_data:
                    positions = new_data['positions_transformed'] if use_transformed else new_data['positions_raw']
                    self.render_glyph_image(
                        positions,
                        new_data['uvs'],
                        new_data.get('texture'),
                        pos_origin_x,
                        pos_origin_y,
                        source='new'
                    )
        
        # 모든 렌더링 완료 후 UI 업데이트
        self.root.update_idletasks()
        
    def convert_position_to_baseline(self, positions, codepoint, source='original'):
        """Position coordinates를 baseline 기준으로 변환
        
        XML은 좌상단 정렬이므로:
        - 모든 글자의 상단이 같은 Y 위치 (좌상단 정렬)
        - verticalBearing: baseline에서 글자 상단까지의 거리
        
        변환: 각 글자의 상단을 baseline + verticalBearing 위치로 이동
        
        Args:
            positions: Position coordinates 리스트
            codepoint: 코드포인트
            source: 'original' 또는 'new'
        """
        try:
            # Font metrics loading
            if source not in self.font_metrics:
                self.load_font_metrics(source)
            
            if source not in self.font_metrics:
                return positions  # metrics 없으면 Original 그대로
            
            font_metrics = self.font_metrics[source]
            scale = font_metrics['scale']
            
            # 글리프 metrics 로드
            glyph_metrics = self.load_glyph_metrics(codepoint, source)
            if not glyph_metrics:
                return positions  # metrics 없으면 Original 그대로
            
            # verticalBearing: baseline에서 글자 상단까지의 거리
            vertical_bearing = glyph_metrics['verticalBearing']
            
            # baseline 기준 상단 위치
            # 정규화: verticalBearing / scale
            baseline_to_top = vertical_bearing / scale
            
            # 디버깅: coordinates 출력
            if positions:
                self.log_message(f"    Before transform {source} Position (codePoint={codepoint}):")
                self.log_message(f"       Top-left: ({positions[0][0]:.4f}, {positions[0][1]:.4f})")
                if len(positions) > 1:
                    self.log_message(f"       Bottom-left: ({positions[1][0]:.4f}, {positions[1][1]:.4f})")
            
            # 각 글자의 상단 Y 위치 (좌상단 또는 우상단)
            top_y = positions[0][1] if positions else 0.0
            
            # baseline 위치 = 상단 - verticalBearing
            baseline_y = top_y - baseline_to_top
            
            self.log_message(f"    {source} top Y={top_y:.4f}")
            self.log_message(f"    {source} baseline Y={baseline_y:.4f} (top - verticalBearing)")
            
            converted_positions = []
            for pos in positions:
                # baseline을 Y=0으로 이동
                # new_Y = Y - baseline_Y
                new_y = pos[1] - baseline_y
                converted_positions.append((pos[0], new_y, pos[2]))
            
            # 디버깅: 변환 후 coordinates 출력
            if converted_positions:
                self.log_message(f"     After transform Position:")
                self.log_message(f"       Top-left: ({converted_positions[0][0]:.4f}, {converted_positions[0][1]:.4f})")
                if len(converted_positions) > 1:
                    self.log_message(f"       Bottom-left: ({converted_positions[1][0]:.4f}, {converted_positions[1][1]:.4f})")
            
            return converted_positions
            
        except Exception as e:
            self.log_message(f"[Warning] baseline conversion error: {e}")
            return positions
    
    def load_original_coordinates(self, codepoint):
        """Load coordinates of specified codepoint from original file"""
        try:
            # Original PSSG 파일에서 coordinates 추출 (번들 리소스 경로 사용)
            original_xml_path = self.font_paths['original_node']
            if not os.path.exists(original_xml_path):
                self.log_message(f"[Error] File not found: {original_xml_path}")
                return None
                
            tree = ET.parse(original_xml_path)
            root = tree.getroot()
            
            # 지정된 코드포인트의 노드 찾기
            target_node = None
            for node in root.findall('.//RENDERNODE'):
                if node.get('id') == str(codepoint):
                    target_node = node
                    break
            
            if not target_node:
                self.log_message(f"[Error] RENDERNODE with ID='{codepoint}' not found in original file.")
                return None
            
            # Original 파일은 RENDERSTREAMINSTANCE 구조 사용
            renderstream = target_node.find('.//RENDERSTREAMINSTANCE')
            if not renderstream:
                self.log_message("[Error] RENDERSTREAMINSTANCEnot found.")
                return None
            
            # RENDERDATASOURCE 찾기 - indices 속성에서 '#' 제거
            renderdatasource_id = renderstream.get('indices')
            if not renderdatasource_id:
                self.log_message("[Error] indices attribute not found.")
                return None
            
            if renderdatasource_id.startswith('#'):
                renderdatasource_id = renderdatasource_id[1:]  # '#' 제거
            
            segmentset_path = self.font_paths['original_segmentset']
            if not os.path.exists(segmentset_path):
                self.log_message(f"[Error] File not found: {segmentset_path}")
                return None
                
            segmentset_tree = ET.parse(segmentset_path)
            segmentset_root = segmentset_tree.getroot()
            
            # RENDERDATASOURCE 찾기
            self.log_message(f"RENDERDATASOURCE ID '{renderdatasource_id}' Searching...")
            renderdatasource = segmentset_root.find(f'.//RENDERDATASOURCE[@id="{renderdatasource_id}"]')
            if not renderdatasource:
                self.log_message(f"[Error] RENDERDATASOURCE ID='{renderdatasource_id}'not found.")
                return None
            self.log_message(f" RENDERDATASOURCE ID='{renderdatasource_id}' Found!")
            
            # RENDERSTREAM들 찾기 (subStream="0"과 subStream="1")
            self.log_message("Searching RENDERSTREAMs...")
            renderstreams = renderdatasource.findall('./RENDERSTREAM')
            self.log_message(f"Found RENDERSTREAM count: {len(renderstreams)}")
            
            if not renderstreams:
                self.log_message("[Error] Cannot find RENDERSTREAM.")
                return None
            
            # subStream="0" (보통 Position)과 subStream="1" (보통 UV) 찾기
            position_stream = None
            uv_stream = None
            
            for i, stream in enumerate(renderstreams):
                sub_stream = stream.get('subStream')
                data_block = stream.get('dataBlock')
                self.log_message(f"RENDERSTREAM {i}: subStream='{sub_stream}' (type: {type(sub_stream)}), dataBlock='{data_block}'")
                
                if sub_stream == '0' or sub_stream == 0:
                    position_stream = stream
                    self.log_message(f" Position stream found: dataBlock='{data_block}'")
                elif sub_stream == '1' or sub_stream == 1:
                    uv_stream = stream
                    self.log_message(f" UV stream found: dataBlock='{data_block}'")
            
            self.log_message(f"Final check - Position stream: {'Found' if position_stream else 'None'}")
            self.log_message(f"Final check - UV stream: {'Found' if uv_stream else 'None'}")
            self.log_message(f"position_stream value: {position_stream}")
            self.log_message(f"uv_stream value: {uv_stream}")
            self.log_message(f"position_stream is None: {position_stream is None}")
            self.log_message(f"uv_stream is None: {uv_stream is None}")
            
            if position_stream is None or uv_stream is None:
                self.log_message("[Error] Cannot find Position or UV stream.")
                self.log_message(f"   Position stream: {'Found' if position_stream is not None else 'None'}")
                self.log_message(f"   UV stream: {'Found' if uv_stream is not None else 'None'}")
                return None
            
            # dataBlock ID 추출 (두 스트림이 같은 dataBlock을 사용할 수 있음)
            datablock_id = position_stream.get('dataBlock')
            if not datablock_id:
                self.log_message("[Error] dataBlock attribute not found.")
                return None
            
            self.log_message(f"Original dataBlock ID: {datablock_id}")
            
            if datablock_id.startswith('#'):
                datablock_id = datablock_id[1:]
            
            self.log_message(f"Processed dataBlock ID: {datablock_id}")
            
            # DATABLOCK 찾기
            datablock_path = self.font_paths['original_renderinterfacebound']
            if not os.path.exists(datablock_path):
                self.log_message(f"[Error] File not found: {datablock_path}")
                return None
                
            datablock_tree = ET.parse(datablock_path)
            datablock_root = datablock_tree.getroot()
            
            # DATABLOCK 찾기
            datablock = datablock_root.find(f'.//DATABLOCK[@id="{datablock_id}"]')
            if not datablock:
                self.log_message(f"[Error] DATABLOCK ID='{datablock_id}'not found.")
                return None
            
            data_elem = datablock.find('./DATABLOCKDATA')
            if data_elem is None:
                self.log_message("[Error] DATABLOCKDATA element not found.")
                return None
            
            # 데이터 텍스트 추출 및 정리
            raw_text = data_elem.text or ''
            hex_data = raw_text.replace(' ', '').replace('\n', '').replace('\t', '').replace('\r', '')
            
            self.log_message(f"DATABLOCKDATA Original length: {len(raw_text)}")
            self.log_message(f"DATABLOCKDATA hex length: {len(hex_data)}")
            self.log_message(f"DATABLOCKDATA hex preview: {hex_data[:80]}")
            
            if not hex_data:
                self.log_message("[Error] DATABLOCKDATAis empty.")
                return None
                
            byte_data = bytes.fromhex(hex_data)
            
            element_count = int(datablock.get('elementCount', 0))
            stride_attr = datablock.get('stride')
            self.log_message(f"DATABLOCK attributes: elementCount={element_count}, stride attribute={stride_attr}")
            
            # stride 속성이 없으면 DATABLOCKSTREAM에서 가져옵니다
            if stride_attr:
                stride = int(stride_attr)
            else:
                # DATABLOCKSTREAM에서 stride 찾기
                stream = datablock.find('./DATABLOCKSTREAM')
                if stream is not None:
                    stride = int(stream.get('stride', 0))
                    self.log_message(f"Stride found in DATABLOCKSTREAM: {stride}")
                else:
                    stride = 0
            
            if element_count == 0 or stride == 0:
                self.log_message(f"[Error] Invalid data: elementCount={element_count}, stride={stride}")
                return None
            
            # DATABLOCKSTREAM 찾기 (Position과 UV 스트림)
            self.log_message(f"DATABLOCK ID: {datablock_id}")
            self.log_message(f"elementCount: {element_count}, stride: {stride}")
            
            position_stream_elem = datablock.find('./DATABLOCKSTREAM[@renderType="Vertex"]')
            uv_stream_elem = datablock.find('./DATABLOCKSTREAM[@renderType="ST"]')
            
            # 디버깅 정보 추가
            self.log_message(f"DATABLOCK ID: {datablock_id}")
            self.log_message(f"elementCount: {element_count}, stride: {stride}")
            
            if position_stream_elem is not None:
                self.log_message(f" Position stream found: offset={position_stream_elem.get('offset')}")
            else:
                self.log_message("[Error] Cannot find Position stream.")
                
            if uv_stream_elem is not None:
                self.log_message(f" UV stream found: offset={uv_stream_elem.get('offset')}")
            else:
                self.log_message("[Error] Cannot find UV stream.")
                
            if position_stream_elem is None or uv_stream_elem is None:
                self.log_message("[Error] Cannot find Position or UV stream.")
                return None
            
            pos_offset = int(position_stream_elem.get('offset', 0))
            uv_offset = int(uv_stream_elem.get('offset', 0))
            
            # coordinates 추출
            positions = []
            uvs = []
            
            for i in range(element_count):
                try:
                    # Position coordinates
                    pos_position = (i * stride) + pos_offset
                    if pos_position + 12 > len(byte_data):  # 3 * 4 bytes
                        break
                    x, y, z = struct.unpack_from('>fff', byte_data, pos_position)
                    positions.append((x, y, z))
                    
                    # UV coordinates
                    uv_position = (i * stride) + uv_offset
                    if uv_position + 8 > len(byte_data):  # 2 * 4 bytes
                        break
                    u, v = struct.unpack_from('>ff', byte_data, uv_position)
                    uvs.append((u, v))
                    
                except struct.error as e:
                    self.log_message(f"[Warning] Struct unpacking error at vertex {i}: {e}")
                    break
            
            # 텍스처 파일명 추출
            texture_filename = None
            renderstream_inst = target_node.find('.//RENDERSTREAMINSTANCE[@shader]')
            if renderstream_inst is not None:
                shader_id = renderstream_inst.get('shader')
                if shader_id:
                    # shader="#din_cnd_bold_msdf_0" -> din_cnd_bold_msdf_0.png
                    texture_filename = shader_id.strip('#') + '.png'
                    self.log_message(f"Texture file: {texture_filename}")
            
            if not texture_filename:
                texture_filename = 'din_cnd_bold_msdf_0.png'  # fallback
                self.log_message(f"[Warning] No texture info, using default: {texture_filename}")
            
            if positions and uvs:
                self.log_message(f" Original Coordinates loaded successfully: {len(positions)}vertices")
                
                # raw와 transformed coordinates 모두 저장 (체크박스 토글용)
                transformed_positions = self.convert_position_to_baseline(positions, codepoint, 'original')
                
                return {
                    'positions_raw': positions,
                    'positions_transformed': transformed_positions,
                    'uvs': uvs,
                    'texture': texture_filename,
                    'source': 'original',
                    'codepoint': codepoint
                }
            else:
                self.log_message("[Error] Cannot extract coordinates data.")
                
        except Exception as e:
            self.log_message(f"[Error] Original file loading error: {e}")
            import traceback
            self.log_message(f"Detailed error: {traceback.format_exc()}")
            
        return None
    
    def load_coordinates_from_libdir(self, lib_dir, codepoint):
        """Load codepoint coordinates from specified library directory (shared for Original/new XML)"""
        is_test_output = 'generated_library' in str(lib_dir)
        try:
            node_path = os.path.join(lib_dir, 'LIBRARY_NODE.xml')
            seg_path = os.path.join(lib_dir, 'LIBRARY_SEGMENTSET.xml')
            rib_path = os.path.join(lib_dir, 'LIBRARY_RENDERINTERFACEBOUND.xml')

            if not (os.path.exists(node_path) and os.path.exists(seg_path) and os.path.exists(rib_path)):
                self.log_message(f"[Error] Cannot find library XML: {lib_dir}")
                return None

            node_tree = ET.parse(node_path)
            node_root = node_tree.getroot()

            # RENDERNODE 찾기
            target_node = None
            for node in node_root.findall('.//RENDERNODE'):
                if node.get('id') == str(codepoint):
                    target_node = node
                    break

            if not target_node:
                self.log_message(f"[Error] RENDERNODE with ID='{codepoint}' not found in '{lib_dir}'.")
                return None

            # RENDERSTREAMINSTANCE -> indices
            renderstream = target_node.find('.//RENDERSTREAMINSTANCE')
            if not renderstream:
                self.log_message("[Error] RENDERSTREAMINSTANCEnot found.")
                return None

            datasource_id = renderstream.get('indices') or ''
            if datasource_id.startswith('#'):
                datasource_id = datasource_id[1:]

            seg_tree = ET.parse(seg_path)
            seg_root = seg_tree.getroot()
            datasource = seg_root.find(f'.//RENDERDATASOURCE[@id="{datasource_id}"]')
            if not datasource:
                self.log_message(f"[Error] RENDERDATASOURCE ID='{datasource_id}'not found.")
                return None

            # DATABLOCK ID 추출 (subStream=0/1 중 아무거나의 dataBlock)
            streams = datasource.findall('./RENDERSTREAM')
            if not streams:
                self.log_message("[Error] No RENDERSTREAM.")
                return None
            datablock_id = None
            for s in streams:
                db = s.get('dataBlock')
                if db:
                    datablock_id = db[1:] if db.startswith('#') else db
                    break
            if not datablock_id:
                self.log_message("[Error] dataBlock IDnot found.")
                return None

            rib_tree = ET.parse(rib_path)
            rib_root = rib_tree.getroot()
            datablock = rib_root.find(f'.//DATABLOCK[@id="{datablock_id}"]')
            if not datablock:
                self.log_message(f"[Error] DATABLOCK ID='{datablock_id}'not found.")
                return None

            data_elem = datablock.find('./DATABLOCKDATA')
            if data_elem is None or (data_elem.text or '').strip() == '':
                self.log_message("[Error] DATABLOCKDATAis empty.")
                return None

            hex_data = (data_elem.text or '').replace(' ', '').replace('\n', '').replace('\t', '').replace('\r', '')
            byte_data = bytes.fromhex(hex_data)

            element_count = int(datablock.get('elementCount', 0))
            # stride는 DATABLOCKSTREAM stride 사용 (없으면 DATABLOCK stride)
            stride_attr = datablock.get('stride')
            if stride_attr:
                stride = int(stride_attr)
            else:
                stream_any = datablock.find('./DATABLOCKSTREAM')
                stride = int(stream_any.get('stride', 0)) if stream_any is not None else 0
            if element_count == 0 or stride == 0:
                self.log_message(f"[Error] Invalid data: elementCount={element_count}, stride={stride}")
                return None

            pos_stream = datablock.find('./DATABLOCKSTREAM[@renderType="Vertex"]')
            uv_stream = datablock.find('./DATABLOCKSTREAM[@renderType="ST"]')
            if pos_stream is None or uv_stream is None:
                self.log_message("[Error] Cannot find Position or UV stream.")
                return None

            pos_offset = int(pos_stream.get('offset', 0))
            uv_offset = int(uv_stream.get('offset', 0))

            positions = []
            uvs = []
            for i in range(element_count):
                base = i * stride
                if base + pos_offset + 12 > len(byte_data):
                    break
                x, y, z = struct.unpack_from('>fff', byte_data, base + pos_offset)
                positions.append((x, y, z))

                if base + uv_offset + 8 > len(byte_data):
                    break
                u, v = struct.unpack_from('>ff', byte_data, base + uv_offset)
                uvs.append((u, v))

            if positions and uvs:
                self.log_message(f" '{lib_dir}' Coordinates loaded successfully: {len(positions)}vertices")
                
                # raw와 transformed coordinates 모두 저장 (체크박스 토글용)
                source = 'new' if is_test_output else 'original'
                transformed_positions = self.convert_position_to_baseline(positions, codepoint, source)
                
                return { 
                    'positions_raw': positions,
                    'positions_transformed': transformed_positions,
                    'uvs': uvs, 
                    'texture': None,
                    'source': 'generated_library' if is_test_output else 'original',
                    'codepoint': codepoint
                }

        except Exception as e:
            self.log_message(f"[Error] XML loading error ({lib_dir}): {e}")
            import traceback
            self.log_message(f"Detailed error: {traceback.format_exc()}")

        return None

    def load_new_coordinates(self, codepoint):
        """Load coordinates of specified codepoint from new file"""
        try:
            # 1) 새 XML(lib) 우선 사용: witchs_gift/generated_library 디렉토리
            lib_dir = os.path.join(self.work_dir, 'witchs_gift', 'generated_library')
            if os.path.isdir(lib_dir):
                xml_data = self.load_coordinates_from_libdir(lib_dir, codepoint)
                if xml_data:
                    return xml_data

            # JSON 데이터 로드
            json_path = 'witchs_gift/font-atlas.json'
            if not os.path.exists(json_path):
                self.log_message(f"[Error] File not found: {json_path}")
                return None
                
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if 'glyphs' not in data:
                self.log_message("[Error] JSON file missing 'glyphs' key.")
                return None
            
            # 지정된 코드포인트의 글리프 찾기
            target_glyph = None
            for glyph in data['glyphs']:
                if glyph.get('unicode') == codepoint:
                    target_glyph = glyph
                    break
            
            if not target_glyph:
                self.log_message(f"[Error] Glyph with codepoint {codepoint} not found in new file.")
                return None
                
            if 'planeBounds' not in target_glyph or 'atlasBounds' not in target_glyph:
                self.log_message("[Error] Glyph missing 'planeBounds' or 'atlasBounds'.")
                return None
            
            pb = target_glyph['planeBounds']
            ab = target_glyph['atlasBounds']
            
            # JSON은 Original 수치를 그대로 사용 (Y는 위가 +)
            positions = [
                (pb['left'], pb['top'], 0.0),      # 좌상
                (pb['left'], pb['bottom'], 0.0),   # 좌하
                (pb['right'], pb['bottom'], 0.0),  # 우하
                (pb['right'], pb['top'], 0.0),     # 우상
            ]
            
            # UV coordinates (atlasBounds 기반)
            if 'atlas' not in data or 'width' not in data['atlas'] or 'height' not in data['atlas']:
                self.log_message("[Error] JSON file missing atlas information.")
                return None
                
            atlas_width = data['atlas']['width']
            atlas_height = data['atlas']['height']
            
            if atlas_width <= 0 or atlas_height <= 0:
                self.log_message(f"[Error] Invalid atlas size: {atlas_width}x{atlas_height}")
                return None
            
            # UV coordinates: DirectX 스타일 (V=0이 상단, V=1이 하단)
            # Original XML도 DirectX 스타일이므로 그대로 사용
            uvs = [
                (ab['left'] / atlas_width, ab['top'] / atlas_height),      # 좌상 -> top (작은 V)
                (ab['left'] / atlas_width, ab['bottom'] / atlas_height),   # 좌하 -> bottom (큰 V)
                (ab['right'] / atlas_width, ab['bottom'] / atlas_height),  # 우하 -> bottom (큰 V)
                (ab['right'] / atlas_width, ab['top'] / atlas_height),     # 우상 -> top (작은 V)
            ]
            
            self.log_message(f" New Coordinates loaded successfully: {len(positions)} vertices")
            return {
                'positions': positions,
                'uvs': uvs,
                'texture': 'font-atlas.png',
                'source': 'json'
            }
            
        except json.JSONDecodeError as e:
            self.log_message(f"[Error] JSON parsing error: {e}")
        except Exception as e:
            self.log_message(f"[Error] New file loading error: {e}")
            import traceback
            self.log_message(f"Detailed error: {traceback.format_exc()}")
            
        return None
    
    def draw_rectangle(self, coords, color, label, codepoint, info_prefix, offset_x=0, offset_y=0, style='solid', scale=200):
        """UV coordinates로 투명 사각형 그리기"""
        if len(coords) < 4:
            self.log_message(f"[Error] {label}: less than 4 coordinates ({len(coords)})")
            return None
        
        # coordinates를 캔버스 coordinates로 변환 (UV는 0~1 범위)
        canvas_coords = []
        for i, coord in enumerate(coords):
            x = coord[0] * scale + offset_x
            y = coord[1] * scale + offset_y
            canvas_coords.extend([x, y])

        # 스타일에 따라 실선 또는 점선으로 그리기
        if style == 'dashed':
            rect_id = self.canvas.create_polygon(canvas_coords, outline=color, width=2, fill='', dash=(6, 3))
        else: # solid
            rect_id = self.canvas.create_polygon(canvas_coords, outline=color, width=2, fill='')

        # 라벨 추가 (점선일 경우 라벨 위치 조정)
        center_x = sum(canvas_coords[::2]) / 4
        center_y = sum(canvas_coords[1::2]) / 4
        label_offset = 7 if style == 'dashed' else -7
        
        text_id = self.canvas.create_text(center_x, center_y + label_offset, text=label, 
                                         fill=color, font=('Arial', 9, 'bold'))
        
        # 클릭 정보를 위해 ID와 정보 저장
        info_str = f"{info_prefix}: '{label}' (ID: {codepoint})"
        self.item_info[rect_id] = info_str
        self.item_info[text_id] = info_str
        
        return rect_id

    def draw_position_rectangle(self, pos_coords, uv_coords, source_image, color, label, codepoint, info_prefix, offset_x=0, offset_y=0, style='solid', source='original'):
        """Position coordinates를 기반으로 텍스처가 입혀진 사각형을 그립니다."""
        if len(pos_coords) < 4:
            self.log_message(f"[Error] {label}: less than 4 Position coordinates ({len(pos_coords)})")
            return None

        # 1. Position coordinates를 캔버스 coordinates로 변환 (원점 기준)
        # simple_position_viewer.py와 동일한 방식 사용
        scale = self.grid_scale  # position 스케일 (동적)
        
        canvas_coords = []
        for coord in pos_coords:
            # X: position coordinates를 원점 기준으로 변환
            canvas_x = offset_x + (coord[0] * scale)
            
            # Y: 반전 (canvas는 아래가 +, position은 위가 +)
            canvas_y = offset_y - (coord[1] * scale)
            
            canvas_coords.extend([canvas_x, canvas_y])

        # 바운딩 박스 계산
        x_coords = canvas_coords[::2]  # 짝수 인덱스 = x coordinates
        y_coords = canvas_coords[1::2]  # 홀수 인덱스 = y coordinates
        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)

        # 시계방향 사각형 coordinates (좌상, 좌하, 우하, 우상)
        canvas_pos_coords = [
            x_min, y_min,
            x_min, y_max,
            x_max, y_max,
            x_max, y_min,
        ]

        # 2. 이미지 렌더링은 제거됨

        # 3. 테두리 사각형 그리기
        if style == 'dashed':
            rect_id = self.canvas.create_polygon(canvas_pos_coords, outline=color, width=2, fill='', dash=(6, 3))
        else: # solid
            rect_id = self.canvas.create_polygon(canvas_pos_coords, outline=color, width=2, fill='')

        # 4. 라벨 추가
        center_x = (x_min + x_max) / 2
        center_y = (y_min + y_max) / 2
        if style == 'dashed':
            center_y += 10
            
        text_id = self.canvas.create_text(center_x, center_y, text=label, fill=color, font=('Arial', 12, 'bold'))
        
        # 5. 클릭 정보를 위해 ID와 정보 저장
        info_str = f"{info_prefix}: '{label}' (ID: {codepoint})"
        if rect_id: self.item_info[rect_id] = info_str
        if text_id: self.item_info[text_id] = info_str
        
        return rect_id

    def render_glyph_image(self, pos_coords, uv_coords, texture_filename, origin_x, origin_y, source='original'):
        """
        실제 글자 이미지를 Atlas에서 crop하여 Position 위치에 렌더링합니다.
        
        Args:
            pos_coords: Position coordinates 리스트 [(x,y,z), ...]
            uv_coords: UV coordinates 리스트 [(u,v), ...]
            texture_filename: 텍스처 파일명 (Original용) 또는 None (새 파일용)
            origin_x, origin_y: 캔버스 원점 위치
            source: 'original' 또는 'new'
        """
        try:
            # 1. Atlas 이미지 로드
            if source == 'original':
                # Original: original_texture 폴더에서 찾기
                if not texture_filename:
                    return
                texture_path = self.atlas_paths['original'] / texture_filename
            else:
                # 새 파일: witchs_gift/font-atlas.png
                texture_path = self.atlas_paths['new']
            
            if not texture_path.exists():
                self.log_message(f"[Warning] Texture file not found: {texture_path}")
                return
            
            atlas_img = Image.open(texture_path)
            
            # 2. UV coordinates로 Atlas에서 글자 영역 crop
            us = [uv[0] for uv in uv_coords]
            vs = [uv[1] for uv in uv_coords]
            
            img_width, img_height = atlas_img.size
            
            # DirectX 스타일: Original과 새 파일 모두 동일한 방식 사용
            tex_left = min(us) * img_width
            tex_right = max(us) * img_width
            tex_top = min(vs) * img_height
            tex_bottom = max(vs) * img_height
            
            # Crop 영역이 유효한지 확인
            if tex_right <= tex_left or tex_bottom <= tex_top:
                return
            
            glyph_img = atlas_img.crop((tex_left, tex_top, tex_right, tex_bottom))
            
            # 3. Position coordinates를 캔버스 coordinates로 변환
            scale = self.grid_scale
            
            xs = [pos[0] for pos in pos_coords]
            ys = [pos[1] for pos in pos_coords]
            
            pos_left = min(xs)
            pos_right = max(xs)
            pos_top = max(ys)  # Y는 위쪽이 큰 값
            pos_bottom = min(ys)  # Y는 아래쪽이 작은 값
            
            # Canvas coordinates로 변환
            canvas_left = origin_x + (pos_left * scale)
            canvas_right = origin_x + (pos_right * scale)
            canvas_top = origin_y - (pos_top * scale)  # Y 반전
            canvas_bottom = origin_y - (pos_bottom * scale)  # Y 반전
            
            # 렌더링 크기 계산
            render_width = int(canvas_right - canvas_left)
            render_height = int(canvas_bottom - canvas_top)
            
            if render_width <= 0 or render_height <= 0:
                return
            
            # 4. 이미지 리사이즈
            resized_glyph = glyph_img.resize((render_width, render_height), Image.Resampling.LANCZOS)
            
            # 5. PhotoImage로 변환 (master를 명시적으로 지정하여 참조 유지)
            tk_image = ImageTk.PhotoImage(resized_glyph, master=self.root)
            self.tk_images.append(tk_image)
            
            # 6. Canvas에 이미지 표시
            # 좌상단 위치에 anchor='nw'로 배치
            self.canvas.create_image(canvas_left, canvas_top, image=tk_image, anchor='nw')
            
        except Exception as e:
            self.log_message(f"[Warning] Character image rendering failed: {e}")

    def log_message(self, message):
        """GUI와 콘솔에 메시지 로깅"""
        if hasattr(self, "info_text"):
            text = message if message.endswith("\n") else message + "\n"
            self.info_text.insert(tk.END, text)
            self.info_text.see(tk.END)

    def analyze_and_log_differences(self, codepoint, original_data, new_data):
        """coordinates 차이를 분석하고 로그에 기록합니다."""
        char = chr(codepoint) if codepoint < 0x110000 else '?'
        
        # metrics 정보 로드
        original_glyph_metrics = self.load_glyph_metrics(codepoint, 'original')
        new_glyph_metrics = self.load_glyph_metrics(codepoint, 'new')
        
        # metrics 정보 출력
        self.log_message(f"\n'{char}' (codePoint={codepoint}) metrics info:")
        
        if original_glyph_metrics:
            self.log_message(f"  [Original metrics]")
            self.log_message(f"    - advanceWidth: {original_glyph_metrics['advanceWidth']}")
            self.log_message(f"    - horizontalBearing: {original_glyph_metrics['horizontalBearing']}")
            self.log_message(f"    - verticalBearing: {original_glyph_metrics['verticalBearing']} (from top-left)")
            self.log_message(f"    - physicalWidth: {original_glyph_metrics['physicalWidth']}")
            self.log_message(f"    - physicalHeight: {original_glyph_metrics['physicalHeight']}")
            
            # Baseline 변환 정보
            if 'original' in self.font_metrics:
                font_metrics = self.font_metrics['original']
                scale = font_metrics['scale']
                vertical_bearing = original_glyph_metrics['verticalBearing']
                baseline_to_top = vertical_bearing / scale
                
                self.log_message(f"    - Baseline transform:")
                self.log_message(f"      verticalBearing={vertical_bearing} (from baseline to top)")
                self.log_message(f"      baseline_to_top = verticalBearing / scale = {baseline_to_top:.4f}")
                self.log_message(f"      Transform formula: new_Y = Original_Y - (Original_top_Y - baseline_to_top)")
                self.log_message(f"      → Align each character's baseline to Y=0")
        else:
            self.log_message(f"  [Warning] No Original metrics info")
        
        if new_glyph_metrics:
            self.log_message(f"  [New metrics]")
            self.log_message(f"    - advanceWidth: {new_glyph_metrics['advanceWidth']}")
            self.log_message(f"    - horizontalBearing: {new_glyph_metrics['horizontalBearing']}")
            self.log_message(f"    - verticalBearing: {new_glyph_metrics['verticalBearing']} (from baseline to top)")
            self.log_message(f"    - physicalWidth: {new_glyph_metrics['physicalWidth']}")
            self.log_message(f"    - physicalHeight: {new_glyph_metrics['physicalHeight']}")
            
            # metrics으로 계산한 Position과 실제 Position 비교
            if 'new' in self.font_metrics:
                calculated_pos = self.calculate_position_from_metrics(new_glyph_metrics, self.font_metrics['new'])
                self.log_message(f"    - metrics-based Position (from baseline):")
                self.log_message(f"      Top-left: ({calculated_pos[0][0]:.4f}, {calculated_pos[0][1]:.4f})")
                self.log_message(f"      Bottom-left: ({calculated_pos[1][0]:.4f}, {calculated_pos[1][1]:.4f})")
                self.log_message(f"      Bottom-right: ({calculated_pos[2][0]:.4f}, {calculated_pos[2][1]:.4f})")
                self.log_message(f"      Top-right: ({calculated_pos[3][0]:.4f}, {calculated_pos[3][1]:.4f})")
        else:
            self.log_message(f"  [Info] No new metrics info")
        
        # 한쪽 데이터만 있는 경우 비교 생략
        if not original_data or not new_data:
            self.log_message(f"\n[Warning] Only one side has data, skipping difference comparison.")
            return
        
        # 실제 Position coordinates 출력 (체크박스 상태에 따라 선택)
        use_transformed = self.apply_baseline_transform.get()
        original_positions = original_data['positions_transformed'] if use_transformed else original_data['positions_raw']
        new_positions = new_data['positions_transformed'] if use_transformed else new_data['positions_raw']
        original_uvs = original_data['uvs']
        new_uvs = new_data['uvs']
        
        self.log_message(f"\nActual Position coordinates:")
        self.log_message(f"  [Original] Top-left: ({original_positions[0][0]:.4f}, {original_positions[0][1]:.4f})")
        self.log_message(f"  [New] Top-left: ({new_positions[0][0]:.4f}, {new_positions[0][1]:.4f})")

        if len(original_positions) != len(new_positions) or len(original_uvs) != len(new_uvs):
            self.log_message(f"[Error] coordinates count mismatch: Original {len(original_positions)}, New {len(new_positions)}")
            return

        differences = []
        for i in range(len(original_positions)):
            original_pos = original_positions[i]
            new_pos = new_positions[i]
            original_uv = original_uvs[i]
            new_uv = new_uvs[i]

            # Position 차이 계산
            pos_diff = [abs(a - b) for a, b in zip(original_pos, new_pos)]
            pos_diff_sum = sum(pos_diff)

            # UV 차이 계산
            uv_diff = [abs(a - b) for a, b in zip(original_uv, new_uv)]
            uv_diff_sum = sum(uv_diff)

            # 차이가 있는 경우 로그에 추가
            if pos_diff_sum > 0.0001 or uv_diff_sum > 0.0001: # 작은 차이는 무시
                differences.append(f"  - vertex {i}: Position diff: {pos_diff_sum:.6f}, UV diff: {uv_diff_sum:.6f}")

        if differences:
            self.log_message(f"\n'{char}' coordinates difference analysis:")
            for diff in differences:
                self.log_message(diff)
        else:
            self.log_message(f"\n '{char}' coordinates are identical.")

    def draw_position_crosshair(self):
        """Display crosshair at center (0,0) of position rendering area"""
        x_center = self.canvas_width // 2
        y_center = self.canvas_height // 2
        
        # 원점 십자선 (굵게)
        self.canvas.create_line(x_center - 15, y_center, x_center + 15, y_center, 
                               fill='black', width=3)
        self.canvas.create_line(x_center, y_center - 15, x_center, y_center + 15, 
                               fill='black', width=3)
        
        # 원점 레이블
        self.canvas.create_text(x_center + 30, y_center - 30, text='Origin (0, 0)', 
                               fill='black', font=('Arial', 11, 'bold'))

    def draw_grid(self):
        """Position 영역에 그리드 그리기"""
        # 원점 설정 (캔버스 중앙)
        origin_x = self.canvas_width // 2
        origin_y = self.canvas_height // 2
        
        grid_color = '#E0E0E0'  # 옅은 회색
        scale = self.grid_scale  # position 스케일 (300px = 1.0 Position 단위)
        grid_range_x = int(scale * 1.5)  # ±1.5 범위 = 450px
        grid_range_y = int(scale * 1.5)  # ±1.5 범위 = 450px
        grid_step = 50  # 50픽셀 간격
        
        # 세로 그리드선 (X축)
        for i in range(-grid_range_x, grid_range_x + 1, grid_step):
            x = origin_x + i
            line_width = 2 if i == 0 else (1 if i % 100 == 0 else 0.5)
            line_color = '#666666' if i == 0 else ('#CCCCCC' if i % 100 == 0 else grid_color)
            
            self.canvas.create_line(x, origin_y - grid_range_y, x, origin_y + grid_range_y,
                                   fill=line_color, width=line_width)
            
            # 눈금 숫자 (100px 간격마다)
            if i % 100 == 0:
                pos_value = i / scale
                self.canvas.create_text(x, origin_y + grid_range_y + 15,
                                       text=f"{pos_value:.2f}", fill='#999999', font=('Arial', 8))
        
        # 가로 그리드선 (Y축)
        for i in range(-grid_range_y, grid_range_y + 1, grid_step):
            y = origin_y + i
            line_width = 2 if i == 0 else (1 if i % 100 == 0 else 0.5)
            line_color = '#666666' if i == 0 else ('#CCCCCC' if i % 100 == 0 else grid_color)
            
            self.canvas.create_line(origin_x - grid_range_x, y, origin_x + grid_range_x, y,
                                   fill=line_color, width=line_width)
            
            # 눈금 숫자 (100px 간격마다)
            if i % 100 == 0:
                pos_value = -i / scale
                self.canvas.create_text(origin_x - grid_range_x - 30, y,
                                       text=f"{pos_value:.2f}", fill='#999999', font=('Arial', 8))
        
        # 축 레이블
        self.canvas.create_text(origin_x + grid_range_x - 30, origin_y + 25,
                               text='X →', fill='#666666', font=('Arial', 10, 'bold'))
        self.canvas.create_text(origin_x + 25, origin_y - grid_range_y + 30,
                               text='↑ Y', fill='#666666', font=('Arial', 10, 'bold'))

    def compare_coordinates(self):
        """coordinates 비교 실행"""
        self.clear_canvas()
        
        char_input = self.char_entry.get().strip()
        if not char_input:
            self.log_message("[Error] Please enter characters to compare.")
            messagebox.showerror("Input Error", "Please enter characters to compare.")
            return
        
        # 마지막 입력 저장 (체크박스 토글 시 재사용)
        self.last_char_input = char_input

        try:
            # 쉼표로 구분된 ID 또는 문자열 입력 처리
            if ',' in char_input:
                codepoints = []
                parts = [p.strip() for p in char_input.split(',')]
                for part in parts:
                    if not part: continue
                    # 단일 문자인지, 숫자인지 확인
                    if len(part) == 1 and not part.isdigit():
                        codepoints.append(ord(part))
                    else:
                        codepoints.append(int(part))
            # 단일 문자 또는 문자열
            else:
                codepoints = [ord(c) for c in char_input]
        except (ValueError, TypeError) as e:
            self.log_message(f"[Error] Invalid input: '{char_input}'. Error: {e}")
            messagebox.showerror("Input Error", f"Invalid input: '{char_input}'.\nEnter a character, Unicode ID, or comma-separated list.")
            return

        self.root.title(f"'{char_input}' coordinates comparison")
        self.log_message(f"'{char_input}' Starting coordinate comparison...\n")
        self.root.update()

        # Canvas 지우고 레이아웃 그리기
        self.clear_canvas()
        self.draw_canvas_layout()

        colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'cyan']
        
        # 데이터 로드 및 캐싱 (raw/transformed 둘 다 저장)
        self.loaded_data.clear()
        
        for i, codepoint in enumerate(codepoints):
            color = colors[i % len(colors)]
            char = chr(codepoint) if codepoint < 0x110000 else '?'

            self.log_message(f"\n--- '{char}' (ID: {codepoint}) Processing started (Color: {color}) ---")

            original_data = self.load_original_coordinates(codepoint)
            new_data = self.load_new_coordinates(codepoint)

            if not original_data and not new_data:
                self.log_message(f"[Error] Cannot find data for '{char}', skipping.")
                continue
            
            # 한쪽 데이터만 있는 경우 경고 출력
            if not original_data:
                self.log_message(f"[Warning] '{char}': No Original data (only new XML exists)")
            if not new_data:
                self.log_message(f"[Warning] '{char}': No new data (only Original XML exists)")
            
            # 데이터 캐싱 (체크박스 변경 시 재사용)
            self.loaded_data[codepoint] = {
                'original': original_data,
                'new': new_data,
                'color': color
            }

            # UV 비교: 동적 크기 UV 박스 영역
            # Position coordinates 원점 (캔버스 중앙)
            pos_origin_x = self.canvas_width // 2
            pos_origin_y = self.canvas_height // 2
            
            uv_offset_x = pos_origin_x - self.uv_box_width + 10  # UV 박스 좌상단 + 여백
            uv_offset_y = pos_origin_y - self.uv_box_height + 30
            
            # UV scale: atlas 비율에 맞춤 (작은 쪽 기준)
            uv_scale = min(self.uv_box_width, self.uv_box_height) - 20  # 여백
            
            # 체크박스 상태에 따라 UV coordinates 그리기
            if self.show_original.get() and original_data:
                self.draw_rectangle(original_data['uvs'], color, f"{char}", codepoint, "Original", 
                                  uv_offset_x, uv_offset_y, style='solid', scale=uv_scale)
            if self.show_new.get() and new_data:
                self.draw_rectangle(new_data['uvs'], color, f"{char}", codepoint, "New", 
                                  uv_offset_x, uv_offset_y, style='dashed', scale=uv_scale)
            
            # Position Y 변환 체크박스 상태에 따라 coordinates 선택
            use_transformed = self.apply_baseline_transform.get()
            
            # 체크박스 상태에 따라 Position coordinates 그리기
            if self.show_original.get() and original_data:
                positions = original_data['positions_transformed'] if use_transformed else original_data['positions_raw']
                self.draw_position_rectangle(positions, original_data['uvs'], None, 
                                            color, f"{char}", codepoint, "Original", 
                                            pos_origin_x, pos_origin_y, style='solid', 
                                            source=original_data.get('source', 'original'))
            if self.show_new.get() and new_data:
                positions = new_data['positions_transformed'] if use_transformed else new_data['positions_raw']
                self.draw_position_rectangle(positions, new_data['uvs'], None, 
                                            color, f"{char}", codepoint, "New", 
                                            pos_origin_x, pos_origin_y, style='dashed', 
                                            source=new_data.get('source', 'generated_library'))
            
            # 체크박스 상태에 따라 글자 이미지 렌더링
            if self.show_glyph_image.get():
                if self.show_original.get() and original_data:
                    positions = original_data['positions_transformed'] if use_transformed else original_data['positions_raw']
                    self.render_glyph_image(
                        positions,
                        original_data['uvs'],
                        original_data.get('texture'),
                        pos_origin_x,
                        pos_origin_y,
                        source='original'
                    )
                if self.show_new.get() and new_data:
                    positions = new_data['positions_transformed'] if use_transformed else new_data['positions_raw']
                    self.render_glyph_image(
                        positions,
                        new_data['uvs'],
                        new_data.get('texture'),
                        pos_origin_x,
                        pos_origin_y,
                        source='new'
                    )

            self.analyze_and_log_differences(codepoint, original_data, new_data)

        self.log_message("\n All characters processed successfully.")

def main():
    try:
        print(" Starting coordinates comparison tool...")
        
        # Tkinter 초기화
        root = tk.Tk()
        print(" Tkinter window created")
        
        # 창 설정은 CoordinateComparator 클래스에서 수행
        # root.title("소문자 'c' coordinates 비교 도구")
        # root.geometry("1400x900")
        
        # 앱 초기화
        app = CoordinateComparator(root)
        print(" App initialization complete")

        # 창 닫기 프로토콜 연결
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        
        # 창을 화면 중앙에 배치
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f'{width}x{height}+{x}+{y}')
        
        # 창을 강제로 앞으로 가져오기
        root.lift()
        root.attributes('-topmost', True)
        root.after_idle(lambda: root.attributes('-topmost', False))
        
        print(" Usage:")
        print("  1. Use 'Check File Paths' button to verify required files exist")
        print("  2. Use 'Start coordinates Comparison' button to run comparison")
        print("  3. Use 'Clear Canvas' button to reset display")
        print(" GUI window displaying...")
        print(" If window is not visible, check the taskbar!")
        
        # 메인 루프 시작
        root.mainloop()
        print(" GUI closed")
        
    except Exception as e:
        print(f"[Error] Error occurred: {e}")
        import traceback
        traceback.print_exc()
        try:
            messagebox.showerror("Error", f"An error occurred during program execution:\n{e}")
        except:
            print("Cannot display messagebox either.")

if __name__ == "__main__":
    main()
