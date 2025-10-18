"""
MSDF Atlas JSON to XML Library Converter

Usage:
    python json_to_xml.py input.json output_dir --texture texture.png --font-name my_font
"""

import json
import struct
import os
import argparse
import xml.etree.ElementTree as ET

class XMLGenerator:
    def __init__(self, json_path, texture_name, font_name):
        """
        Args:
            json_path: msdf-atlas-gen이 생성한 JSON 파일 경로
            texture_name: 텍스처 파일명 (예: "my_font_msdf_0.tga")
            font_name: 폰트 이름 (예: "my_font_msdf")
        """
        self.json_path = json_path
        self.texture_name = texture_name
        self.font_name = font_name
        
        print(f"JSON 파일 로딩: {json_path}")
        with open(json_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        self.atlas_width = self.data['atlas']['width']
        self.atlas_height = self.data['atlas']['height']
        self.glyphs = self.data['glyphs']
        
        # 메트릭 정보 추출
        metrics = self.data.get('metrics', {})
        self.ascender = metrics.get('ascender', 0)
        self.descender = metrics.get('descender', 0)
        self.line_height = metrics.get('lineHeight', 1.0)
        
        print(f"아틀라스 크기: {self.atlas_width}x{self.atlas_height}")
        print(f"글리프 개수: {len(self.glyphs)}")
        
        # ID 생성용 카운터
        self.datablock_counter = 0
        self.segment_counter = 0
    
    def _generate_id(self, prefix=""):
        """고유 ID 생성"""
        # PSSG 스타일 ID 생성 (예: !xC, !yC, !zC ...)
        # 간단하게 순차 번호로 생성
        counter = self.datablock_counter if prefix == "DB" else self.segment_counter
        if prefix == "DB":
            self.datablock_counter += 1
        else:
            self.segment_counter += 1
        return f"!GEN{prefix}{counter:04X}"
    
    def _uv_to_big_endian_hex(self, u, v):
        """UV 좌표를 Big-endian float hex 문자열로 변환"""
        # Big-endian으로 float 2개를 8바이트 hex로 변환
        byte_data = struct.pack('>ff', u, v)
        hex_str = byte_data.hex().upper()
        # 2자리씩 공백으로 구분
        return ' '.join([hex_str[i:i+2] for i in range(0, len(hex_str), 2)])
    
    def _create_vertex_datablock(self, glyph, datablock_id):
        """글리프에 대한 버텍스 DATABLOCK 생성 (planeBounds 없으면 크기 0)"""
        
        # planeBounds가 없으면 모든 좌표를 0으로 설정
        if 'planeBounds' not in glyph or 'atlasBounds' not in glyph:
            p_left = p_right = p_top = p_bottom = 0.0
            left = right = top = bottom = 0.0
        else:
            # 픽셀 좌표를 UV 좌표로 변환
            plane_bounds = glyph['planeBounds']
            atlas_bounds = glyph['atlasBounds']
            
            # 아틀라스 좌표를 UV 좌표로 변환 (0.0 ~ 1.0)
            # DirectX 스타일: V=0이 이미지 상단, V=1이 이미지 하단
            # -yorigin bottom이므로 V 좌표 반전 필요
            left = atlas_bounds['left'] / self.atlas_width
            right = atlas_bounds['right'] / self.atlas_width
            top = 1.0 - (atlas_bounds['bottom'] / self.atlas_height)
            bottom = 1.0 - (atlas_bounds['top'] / self.atlas_height)
            
            # planeBounds를 원본 게임 방식으로 변환 (글자 상단=Y0)
            # planeBounds는 베이스라인 기준이므로, top만큼 아래로 이동
            # planeBounds['top'] = 베이스라인에서 상단까지의 거리 (= verticalBearing)
            vertical_bearing = plane_bounds['top']
            
            p_left = plane_bounds['left']
            p_right = plane_bounds['right']
            p_top = plane_bounds['top'] - vertical_bearing  # = 0
            p_bottom = plane_bounds['bottom'] - vertical_bearing
            
        
        # 4개의 버텍스 (사각형)
        # Vertex 데이터: position(float3) + UV(float2)
        # stride=20, position offset=0, UV offset=12
        
        vertices = [
            # (position_x, position_y, position_z, uv_u, uv_v)
            # DirectX 스타일: top < bottom (V가 위에서 아래로 증가)
            (p_left, p_top, 0.0, left, top),      # 좌상 -> top (작은 V)
            (p_left, p_bottom, 0.0, left, bottom), # 좌하 -> bottom (큰 V)
            (p_right, p_bottom, 0.0, right, bottom), # 우하 -> bottom (큰 V)
            (p_right, p_top, 0.0, right, top),     # 우상 -> top (작은 V)
        ]
        
        # 버텍스 데이터를 Big-endian으로 인코딩
        hex_lines = []
        current_line = []
        
        for i, (px, py, pz, u, v) in enumerate(vertices):
            # position (float3) + UV (float2) = 20 bytes
            vertex_bytes = struct.pack('>fffff', px, py, pz, u, v)
            vertex_hex = vertex_bytes.hex().upper()
            
            # 2자리씩 공백으로 구분하여 추가
            hex_bytes = [vertex_hex[j:j+2] for j in range(0, len(vertex_hex), 2)]
            current_line.extend(hex_bytes)
            
            # 한 줄에 적당한 길이만 (16바이트 = 32자 = 16개의 hex 바이트)
            if len(current_line) >= 16:
                hex_lines.append(' '.join(current_line[:16]))
                current_line = current_line[16:]
        
        # 남은 데이터 추가
        if current_line:
            hex_lines.append(' '.join(current_line))
        
        # DATABLOCK XML 생성
        datablock = ET.Element('DATABLOCK')
        datablock.set('streamCount', '2')
        datablock.set('size', '80')  # 4 vertices * 20 bytes
        datablock.set('elementCount', '4')
        datablock.set('id', datablock_id)
        
        # DATABLOCKSTREAM for Vertex (position)
        stream_vertex = ET.SubElement(datablock, 'DATABLOCKSTREAM')
        stream_vertex.set('renderType', 'Vertex')
        stream_vertex.set('dataType', 'float3')
        stream_vertex.set('offset', '0')
        stream_vertex.set('stride', '20')
        
        # DATABLOCKSTREAM for ST (UV)
        stream_st = ET.SubElement(datablock, 'DATABLOCKSTREAM')
        stream_st.set('renderType', 'ST')
        stream_st.set('dataType', 'float2')
        stream_st.set('offset', '12')
        stream_st.set('stride', '20')
        
        # DATABLOCKDATA
        data_elem = ET.SubElement(datablock, 'DATABLOCKDATA')
        data_elem.text = '\n' + '\n'.join(hex_lines) + ' '
        
        return datablock
    
    def _create_segmentset(self, glyph, datablock_id, segment_id, datasource_id, indexsource_id):
        """SEGMENTSET 생성"""
        segmentset = ET.Element('SEGMENTSET')
        segmentset.set('segmentCount', '1')
        segmentset.set('id', segment_id)
        
        # RENDERDATASOURCE
        datasource = ET.SubElement(segmentset, 'RENDERDATASOURCE')
        datasource.set('streamCount', '2')
        datasource.set('primitive', 'triangles')
        datasource.set('id', datasource_id)
        
        # RENDERINDEXSOURCE
        indexsource = ET.SubElement(datasource, 'RENDERINDEXSOURCE')
        indexsource.set('primitive', 'triangles')
        indexsource.set('maximumIndex', '3')
        indexsource.set('format', 'ushort')
        indexsource.set('count', '6')
        indexsource.set('id', indexsource_id)
        
        # INDEXSOURCEDATA - 사각형을 2개의 삼각형으로
        indexdata = ET.SubElement(indexsource, 'INDEXSOURCEDATA')
        indexdata.text = '\n0 1 2 0 2 3 '
        
        # RENDERSTREAM (2개: Vertex와 ST용)
        stream0 = ET.SubElement(datasource, 'RENDERSTREAM')
        stream0.set('dataBlock', f'#{datablock_id}')
        stream0.set('subStream', '0')
        stream0.set('id', f'{datasource_id}_0')
        
        stream1 = ET.SubElement(datasource, 'RENDERSTREAM')
        stream1.set('dataBlock', f'#{datablock_id}')
        stream1.set('subStream', '1')
        stream1.set('id', f'{datasource_id}_1')
        
        return segmentset
    
    def _create_rendernode(self, glyph, datasource_id, shader_id):
        """RENDERNODE 생성 (planeBounds 없으면 BOUNDINGBOX를 0으로)"""
        unicode = glyph['unicode']
        
        rendernode = ET.Element('RENDERNODE')
        rendernode.set('stopTraversal', '0')
        rendernode.set('nickname', str(unicode))
        rendernode.set('id', str(unicode))
        
        # TRANSFORM (단위 행렬)
        transform = ET.SubElement(rendernode, 'TRANSFORM')
        transform.text = '\n1.000000000e+000 0.000000000e+000 -0.000000000e+000 0.000000000e+000 0.000000000e+000 1.000000000e+000 -0.000000000e+000 0.000000000e+000 \n-0.000000000e+000 -0.000000000e+000 1.000000000e+000 -0.000000000e+000 0.000000000e+000 0.000000000e+000 -0.000000000e+000 1.000000000e+000 '
        
        # BOUNDINGBOX (planeBounds 없으면 모두 0)
        bbox = ET.SubElement(rendernode, 'BOUNDINGBOX')
        if 'planeBounds' in glyph:
            pb = glyph['planeBounds']
            bbox.text = f'\n{pb["left"]:.9e} {pb["bottom"]:.9e} -0.000000000e+000 {pb["right"]:.9e} {pb["top"]:.9e} -0.000000000e+000 '
        else:
            # 원본과 동일하게 크기 0으로 설정
            bbox.text = '\n0.000000000e+000 0.000000000e+000 -0.000000000e+000 0.000000000e+000 0.000000000e+000 -0.000000000e+000 '
        
        # RENDERSTREAMINSTANCE
        stream_instance = ET.SubElement(rendernode, 'RENDERSTREAMINSTANCE')
        stream_instance.set('sourceCount', '1')
        stream_instance.set('indices', f'#{datasource_id}')
        stream_instance.set('streamCount', '0')
        stream_instance.set('shader', f'#{shader_id}')
        stream_instance.set('id', f'{unicode}_SI')
        
        # RENDERINSTANCESOURCE
        instance_source = ET.SubElement(stream_instance, 'RENDERINSTANCESOURCE')
        instance_source.set('source', f'#{datasource_id}')
        
        return rendernode
    
    def generate_libraries(self, output_dir):
        """모든 LIBRARY XML 파일 생성"""
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"\n출력 디렉토리: {output_dir}")
        print("="*60)
        
        # 각 라이브러리 루트 생성
        lib_renderinterfacebound = ET.Element('LIBRARY')
        lib_renderinterfacebound.set('type', 'RENDERINTERFACEBOUND')
        lib_segmentset = ET.Element('LIBRARY')
        lib_segmentset.set('type', 'SEGMENTSET')
        lib_node = ET.Element('LIBRARY')
        lib_node.set('type', 'NODE')
        lib_shaderinstance = ET.Element('LIBRARY')
        lib_shaderinstance.set('type', 'SHADERINSTANCE')
        lib_shadergroup = ET.Element('LIBRARY')
        lib_shadergroup.set('type', 'SHADERGROUP')
        lib_neglyphmetrics = ET.Element('LIBRARY')
        lib_neglyphmetrics.set('type', 'NEGLYPHMETRICS')
        lib_nefontmetrics = ET.Element('LIBRARY')
        lib_nefontmetrics.set('type', 'NEFONTMETRICS')
        
        # ShaderGroup 생성
        shadergroup = self._create_shadergroup()
        lib_shadergroup.append(shadergroup)
        
        # Shader 생성 (모든 글리프가 공유)
        shader_id = self.font_name
        shader = self._create_shader(shader_id, self.texture_name)
        lib_shaderinstance.append(shader)
        
        # ROOTNODE 생성 (모든 RENDERNODE의 부모)
        rootnode = ET.Element('ROOTNODE')
        rootnode.set('stopTraversal', '0')
        rootnode.set('nickname', 'Root')
        rootnode.set('id', 'Root')
        
        # ROOTNODE의 TRANSFORM (단위 행렬)
        root_transform = ET.SubElement(rootnode, 'TRANSFORM')
        root_transform.text = '\n1.000000000e+000 0.000000000e+000 -0.000000000e+000 0.000000000e+000 0.000000000e+000 1.000000000e+000 -0.000000000e+000 0.000000000e+000 \n-0.000000000e+000 -0.000000000e+000 1.000000000e+000 -0.000000000e+000 0.000000000e+000 0.000000000e+000 -0.000000000e+000 1.000000000e+000 '
        
        # ROOTNODE의 BOUNDINGBOX (0으로 초기화)
        root_bbox = ET.SubElement(rootnode, 'BOUNDINGBOX')
        root_bbox.text = '\n0.000000000e+000 0.000000000e+000 0.000000000e+000 0.000000000e+000 0.000000000e+000 0.000000000e+000 '
        
        # 각 글리프에 대해 데이터 생성
        skipped_rendering = 0  # 렌더링 건너뛴 글리프 (메트릭만 생성)
        skipped_glyphs = []  # 건너뛴 글리프 정보 저장
        processed_glyphs = []  # 렌더링 데이터 생성된 글리프
        all_glyphs_with_metrics = []  # 메트릭이 있는 모든 글리프
        
        for i, glyph in enumerate(self.glyphs):
            unicode = glyph['unicode']
            
            # planeBounds가 없는 글리프 추적
            has_planebounds = 'planeBounds' in glyph
            if not has_planebounds:
                skipped_rendering += 1
                skipped_glyphs.append(glyph)
            
            if i % 100 == 0:
                print(f"진행 중: {i}/{len(self.glyphs)} 글리프 처리 중... (크기 0: {skipped_rendering}개)")
            
            processed_glyphs.append(glyph)
            all_glyphs_with_metrics.append(glyph)
            
            # ID 생성
            datablock_id = self._generate_id("DB")
            segment_id = self._generate_id("SEG")
            datasource_id = self._generate_id("DS")
            indexsource_id = self._generate_id("IS")
            
            # DATABLOCK 생성 및 추가 (planeBounds 없으면 크기 0)
            datablock = self._create_vertex_datablock(glyph, datablock_id)
            lib_renderinterfacebound.append(datablock)
            
            # SEGMENTSET 생성 및 추가
            segmentset = self._create_segmentset(glyph, datablock_id, segment_id, 
                                                  datasource_id, indexsource_id)
            lib_segmentset.append(segmentset)
            
            # RENDERNODE 생성 및 추가 (ROOTNODE의 자식으로)
            rendernode = self._create_rendernode(glyph, datasource_id, shader_id)
            rootnode.append(rendernode)
            
            # NEGLYPHMETRICS 생성 및 추가
            metrics = self._create_glyph_metrics(glyph)
            if metrics is not None:
                lib_neglyphmetrics.append(metrics)
        
        # FontMetrics 생성 (모든 메트릭 글리프 포함)
        scale = 1000
        
        # 최대 advance width 계산 (모든 글리프 포함)
        max_advance = max(glyph.get('advance', 0) for glyph in all_glyphs_with_metrics) if all_glyphs_with_metrics else 1.0
        max_advance_scaled = int(max_advance * scale)
        
        fontmetrics = ET.Element('NEFONTMETRICS')
        fontmetrics.set('scale', str(scale))
        fontmetrics.set('ascender', str(int(self.ascender * scale)))
        fontmetrics.set('descender', str(int(self.descender * scale)))
        fontmetrics.set('maximumAdvanceWidth', str(max_advance_scaled))
        fontmetrics.set('numCharacters', str(len(all_glyphs_with_metrics)))
        fontmetrics.set('hasKerningData', '0')
        fontmetrics.set('id', 'NeFontMetricsObj')
        
        # all_glyphs_with_metrics의 각 글리프에 대해 NEGLYPHMETRICSREF 추가
        for glyph in all_glyphs_with_metrics:
            unicode = glyph['unicode']
            metrics_ref = ET.SubElement(fontmetrics, 'NEGLYPHMETRICSREF')
            metrics_ref.set('glyphMetricsRef', f'#glyphMetrics{unicode}')
        
        # FontMetrics를 라이브러리에 추가
        lib_nefontmetrics.append(fontmetrics)
        
        # ROOTNODE를 NODE 라이브러리에 추가
        lib_node.append(rootnode)
        
        # TEXTURE를 RENDERINTERFACEBOUND에 추가
        texture = self._create_texture(self.texture_name)
        lib_renderinterfacebound.append(texture)
        
        print(f"완료: 렌더링={len(processed_glyphs)}, 메트릭만={skipped_rendering}, 총={len(all_glyphs_with_metrics)}/{len(self.glyphs)}")
        
        # 건너뛴 글리프 정보를 파일로 저장
        if skipped_glyphs:
            skipped_file = os.path.join(output_dir, 'skipped_glyphs.txt')
            with open(skipped_file, 'w', encoding='utf-8') as f:
                # 건너뛴 문자들을 한 줄로 표시
                skipped_chars = []
                for glyph in skipped_glyphs:
                    unicode_val = glyph['unicode']
                    try:
                        char = chr(unicode_val)
                        skipped_chars.append(char)
                    except (ValueError, OverflowError):
                        skipped_chars.append(f"[U+{unicode_val:04X}]")
                
                # 한 줄로 출력
                f.write(''.join(skipped_chars) + "\n")
                
            print(f"\n건너뛴 글리프 정보: {skipped_file}")
        
        # XML 파일로 저장 (알파벳 순서)
        self._save_library(lib_nefontmetrics, os.path.join(output_dir, 'LIBRARY_NEFONTMETRICS.xml'))
        self._save_library(lib_neglyphmetrics, os.path.join(output_dir, 'LIBRARY_NEGLYPHMETRICS.xml'))
        self._save_library(lib_node, os.path.join(output_dir, 'LIBRARY_NODE.xml'))
        self._save_library(lib_renderinterfacebound, os.path.join(output_dir, 'LIBRARY_RENDERINTERFACEBOUND.xml'))
        self._save_library(lib_segmentset, os.path.join(output_dir, 'LIBRARY_SEGMENTSET.xml'))
        self._save_library(lib_shadergroup, os.path.join(output_dir, 'LIBRARY_SHADERGROUP.xml'))
        self._save_library(lib_shaderinstance, os.path.join(output_dir, 'LIBRARY_SHADERINSTANCE.xml'))
        
        print("\n생성된 파일:")
        print(f"  - LIBRARY_NEFONTMETRICS.xml")
        print(f"  - LIBRARY_NEGLYPHMETRICS.xml")
        print(f"  - LIBRARY_NODE.xml")
        print(f"  - LIBRARY_RENDERINTERFACEBOUND.xml")
        print(f"  - LIBRARY_SEGMENTSET.xml")
        print(f"  - LIBRARY_SHADERGROUP.xml")
        print(f"  - LIBRARY_SHADERINSTANCE.xml")
    
    def _create_shader(self, shader_id, texture_name):
        """SHADERINSTANCE 생성"""
        shader = ET.Element('SHADERINSTANCE')
        shader.set('shaderGroup', '#ui_2d_uv_instanced.fx')
        shader.set('parameterCount', '4')
        shader.set('parameterSavedCount', '4')
        shader.set('renderSortPriority', '0')
        shader.set('id', shader_id)
        
        # SHADERINPUT 0: constant float4 (0,0,0,0)
        shader_input0 = ET.SubElement(shader, 'SHADERINPUT')
        shader_input0.set('parameterID', '0')
        shader_input0.set('type', 'constant')
        shader_input0.set('format', 'float4')
        shader_input0.text = '\n0.000000000e+000 0.000000000e+000 0.000000000e+000 0.000000000e+000 '
        
        # SHADERINPUT 1: texture
        shader_input1 = ET.SubElement(shader, 'SHADERINPUT')
        shader_input1.set('parameterID', '1')
        shader_input1.set('type', 'texture')
        shader_input1.set('texture', f'#{texture_name}')
        
        # SHADERINPUT 2: constant float4 (1,1,1,1)
        shader_input2 = ET.SubElement(shader, 'SHADERINPUT')
        shader_input2.set('parameterID', '2')
        shader_input2.set('type', 'constant')
        shader_input2.set('format', 'float4')
        shader_input2.text = '\n1.000000000e+000 1.000000000e+000 1.000000000e+000 1.000000000e+000 '
        
        # SHADERINPUT 3: constant float (1.0)
        shader_input3 = ET.SubElement(shader, 'SHADERINPUT')
        shader_input3.set('parameterID', '3')
        shader_input3.set('type', 'constant')
        shader_input3.set('format', 'float')
        shader_input3.text = '\n1.000000000e+000 '
        
        return shader
    
    def _create_texture(self, texture_name):
        """TEXTURE 요소 생성 (더미 4x4 DXT1 텍스처)"""
        texture = ET.Element('TEXTURE')
        texture.set('width', '4')
        texture.set('height', '4')
        texture.set('texelFormat', 'dxt1')
        texture.set('transient', '0')
        texture.set('wrapS', '1')
        texture.set('wrapT', '1')
        texture.set('wrapR', '1')
        texture.set('minFilter', '5')
        texture.set('magFilter', '1')
        texture.set('gammaRemapR', '0')
        texture.set('gammaRemapG', '0')
        texture.set('gammaRemapB', '0')
        texture.set('gammaRemapA', '0')
        texture.set('automipmap', '0')
        texture.set('numberMipMapLevels', '2')
        texture.set('arraySize', '1')
        texture.set('imageBlockCount', '1')
        texture.set('id', texture_name)
        
        # TEXTUREIMAGEBLOCK (더미 데이터)
        imageblock = ET.SubElement(texture, 'TEXTUREIMAGEBLOCK')
        imageblock.set('typename', 'Raw')
        imageblock.set('size', '24')
        
        imageblockdata = ET.SubElement(imageblock, 'TEXTUREIMAGEBLOCKDATA')
        imageblockdata.text = '\n00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 '
        
        return texture
    
    def _create_shadergroup(self):
        """SHADERGROUP 생성"""
        shadergroup = ET.Element('SHADERGROUP')
        shadergroup.set('parameterCount', '4')
        shadergroup.set('parameterSavedCount', '0')
        shadergroup.set('parameterStreamCount', '0')
        shadergroup.set('instancesRequireSorting', '0')
        shadergroup.set('defaultRenderSortPriority', '-2147483648')
        shadergroup.set('passCount', '0')
        shadergroup.set('id', 'ui_2d_uv_instanced.fx')
        
        # SHADERINPUTDEFINITION들
        inputs = [
            ('Phong', 'constant', 'float4'),
            ('TDistanceMap', 'texture', None),
            ('DiffuseColour', 'constant', 'float4'),
            ('Alpha', 'constant', 'float'),
        ]
        
        for name, input_type, format_type in inputs:
            input_def = ET.SubElement(shadergroup, 'SHADERINPUTDEFINITION')
            input_def.set('name', name)
            input_def.set('type', input_type)
            if format_type:
                input_def.set('format', format_type)
        
        return shadergroup
    
    def _create_glyph_metrics(self, glyph):
        """NEGLYPHMETRICS 생성 (planeBounds 없는 경우도 처리)"""
        unicode = glyph['unicode']
        advance = glyph.get('advance', 1.0)
        scale = 1000.0
        
        # planeBounds가 없는 경우 (공백, 제어 문자 등)
        if 'planeBounds' not in glyph:
            # 메트릭은 생성하되, 크기는 0으로 설정
            metrics = ET.Element('NEGLYPHMETRICS')
            metrics.set('advanceWidth', str(int(advance * scale)))
            metrics.set('horizontalBearing', '0')
            metrics.set('verticalBearing', '0')
            metrics.set('physicalWidth', '0')
            metrics.set('physicalHeight', '0')
            metrics.set('codePoint', str(unicode))
            metrics.set('id', f'glyphMetrics{unicode}')
            return metrics
        
        # planeBounds가 있는 경우
        pb = glyph['planeBounds']
        
        # 좌표를 1000 스케일로 변환 (PSSG 표준)
        advance_width = int(advance * scale)
        physical_width = int((pb['right'] - pb['left']) * scale)
        physical_height = int((pb['top'] - pb['bottom']) * scale)
        horizontal_bearing = int(pb['left'] * scale)
        # verticalBearing: 베이스라인에서 글자 상단까지의 거리
        vertical_bearing = int(pb['top'] * scale)
        
        metrics = ET.Element('NEGLYPHMETRICS')
        metrics.set('advanceWidth', str(advance_width))
        metrics.set('horizontalBearing', str(horizontal_bearing))
        metrics.set('verticalBearing', str(vertical_bearing))
        metrics.set('physicalWidth', str(physical_width))
        metrics.set('physicalHeight', str(physical_height))
        metrics.set('codePoint', str(unicode))
        metrics.set('id', f'glyphMetrics{unicode}')
        
        return metrics
    
    def _save_library(self, library_elem, filepath):
        """LIBRARY를 XML 파일로 저장 (포맷팅 적용)"""
        # 들여쓰기 추가 (Python 3.9+의 ET.indent 사용, 없으면 직접 구현)
        try:
            ET.indent(library_elem, space='', level=0)
        except AttributeError:
            # Python 3.8 이하용 대체 구현
            self._indent(library_elem)
        
        # ET.tostring으로 변환
        xml_string = ET.tostring(library_elem, encoding='unicode')
        
        # XML 선언 및 PSSG 구조 추가
        full_xml = f'<?xml version=\'1.0\' encoding=\'utf-8\'?>\n<PSSGFILE version="1.0.0.0"><PSSGDATABASE>{xml_string}</PSSGDATABASE></PSSGFILE>'
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(full_xml)
        
        print(f"저장: {filepath}")
    
    def _indent(self, elem, level=0):
        """XML 트리에 들여쓰기 추가 (ET.indent 대체용)"""
        i = "\n" + level * ""
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + ""
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for child in elem:
                self._indent(child, level+1)
            if not child.tail or not child.tail.strip():
                child.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i
    
    def generate_summary(self):
        """JSON 데이터 요약 출력"""
        print("\n" + "="*60)
        print("JSON 데이터 요약")
        print("="*60)
        print(f"아틀라스 크기: {self.atlas_width}x{self.atlas_height}")
        print(f"글리프 개수: {len(self.glyphs)}")
        
        if self.glyphs:
            first = self.glyphs[0]
            print(f"\n첫 번째 글리프 샘플:")
            print(f"  Unicode: {first['unicode']} ('{chr(first['unicode'])}')")
            
            # atlasBounds와 planeBounds가 있는 경우만 출력
            if 'atlasBounds' in first:
                print(f"  Atlas bounds: {first['atlasBounds']}")
                ab = first['atlasBounds']
                u_min = ab['left'] / self.atlas_width
                u_max = ab['right'] / self.atlas_width
                v_min = ab['top'] / self.atlas_height
                v_max = ab['bottom'] / self.atlas_height
                print(f"  UV 좌표: U=[{u_min:.6f}, {u_max:.6f}], V=[{v_min:.6f}, {v_max:.6f}]")
            else:
                print(f"  Atlas bounds: None (non-rendering glyph)")
            
            if 'planeBounds' in first:
                print(f"  Plane bounds: {first['planeBounds']}")
            else:
                print(f"  Plane bounds: None (non-rendering glyph)")
        
        print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description='Convert MSDF Atlas JSON to XML Libraries',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python json_to_xml.py font.json output_libs --texture my_font_0.tga --font-name my_font_msdf_0
  
생성되는 파일:
  output_libs/LIBRARY_RENDERINTERFACEBOUND.xml
  output_libs/LIBRARY_SEGMENTSET.xml
  output_libs/LIBRARY_NODE.xml
  output_libs/LIBRARY_SHADERINSTANCE.xml
        """
    )
    
    parser.add_argument('json', help='입력 JSON 파일 (msdf-atlas-gen 출력)')
    parser.add_argument('output_dir', help='출력 디렉토리')
    parser.add_argument('--texture', required=True, help='텍스처 파일명 (예: my_font_0.tga)')
    parser.add_argument('--font-name', required=True, help='폰트 이름 (예: my_font_msdf_0)')
    parser.add_argument('--summary', action='store_true', help='JSON 요약만 출력하고 종료')
    
    args = parser.parse_args()
    
    # Generator 생성
    generator = XMLGenerator(args.json, args.texture, args.font_name)
    
    if args.summary:
        # 요약만 출력
        generator.generate_summary()
    else:
        # XML 생성
        generator.generate_summary()
        print("\nXML 파일 생성 시작...")
        generator.generate_libraries(args.output_dir)
        print(f"\n완료! '{args.output_dir}' 폴더를 확인하세요.")


if __name__ == "__main__":
    main()

