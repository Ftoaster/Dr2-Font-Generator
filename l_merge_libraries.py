import xml.etree.ElementTree as ET
import os

def indent_xml(elem, level=0, indent_str=""):
    """
    XML 요소에 줄바꿈을 추가합니다 (들여쓰기는 없이).
    Python 3.9 미만 버전에서 ET.indent 대체용입니다.
    """
    i = "\n" + level * indent_str
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + indent_str
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for child in elem:
            indent_xml(child, level + 1, indent_str)
        if not child.tail or not child.tail.strip():
            child.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

# --- 설정 ---
import os
from pathlib import Path

# 작업 디렉토리 기준 경로 설정
work_dir = Path(__file__).parent

# 1. 분리된 라이브러리 XML 파일들이 있는 폴더 경로
INPUT_FOLDER = work_dir / "witchs_gift" / "generated_library"

# 2. 라이브러리 순서의 기준이 될 '원본' XML 파일 경로
ORDER_TEMPLATE_XML_PATH = work_dir / "separated_libraries_raw" / "LIBRARY_NODE.xml"

# 3. 하나로 합쳐진 최종 XML 파일을 저장할 경로
OUTPUT_XML_PATH = work_dir / "witchs_gift" / "node.xml"
# --- 설정 끝 ---

def merge_xml_libraries_ordered(input_dir, template_path, output_path):
    """
    'template_path'의 라이브러리 순서를 기준으로, 'input_dir' 폴더의
    모든 LIBRARY_*.xml 파일들을 하나의 PSSG XML 파일로 합칩니다.
    """
    # Path 객체를 문자열로 변환
    input_dir = str(input_dir)
    template_path = str(template_path)
    output_path = str(output_path)
    
    print(f"--- XML 라이브러리 순서 보장 병합 시작 ---")
    print(f"입력 폴더: {input_dir}")
    print(f"순서 기준 파일: {template_path}")

    try:
        # 1. 순서의 기준이 될 원본 XML 파일에서 XML 구조 가져오기
        order_tree = ET.parse(template_path)
        order_root = order_tree.getroot()
        order_db = order_root.find('PSSGDATABASE')
        
        # 2. 고정된 라이브러리 순서 (D:\msdf-atlas-gen\node.xml 원본 기준)
        library_order = [
            'NEFONTMETRICS',
            'NEGLYPHMETRICS',
            'SHADERINSTANCE',
            'SHADERGROUP',
            'SEGMENTSET',
            'RENDERINTERFACEBOUND',
            'NODE'
        ]

        print(f"라이브러리 순서 확인: {library_order}")
        print("-" * 30)
        
        # 3. 합쳐질 기본 XML 구조 생성 (원본 속성을 그대로 복사)
        root = ET.Element(order_root.tag, order_root.attrib)
        database = ET.SubElement(root, order_db.tag, order_db.attrib if order_db is not None else {})

        # 4. 고정된 순서에 따라 각 파일을 찾아 병합
        print("병합을 시작합니다...")
        for lib_type in library_order:
            filename = f"LIBRARY_{lib_type}.xml"
            file_path = os.path.join(input_dir, filename)

            if os.path.exists(file_path):
                try:
                    tree = ET.parse(file_path)
                    library_element = tree.find('.//LIBRARY')
                    if library_element is not None:
                        database.append(library_element)
                        print(f"병합 완료: {filename}")
                    else:
                        print(f"[경고] '{filename}' 파일에서 <LIBRARY> 태그를 찾지 못해 건너뜁니다.")
                except ET.ParseError:
                    print(f"[오류] '{filename}' 파일이 올바른 XML 형식이 아닙니다. 건너뜁니다.")
            else:
                print(f"[경고] '{filename}' 파일을 찾을 수 없어 병합에서 제외합니다.")

        # 5. 최종적으로 합쳐진 XML 파일 저장
        final_tree = ET.ElementTree(root)
        
        # 들여쓰기 추가 (줄바꿈만, 들여쓰기 공백은 없음)
        try:
            # Python 3.9 이상
            ET.indent(final_tree, space="", level=0)
        except AttributeError:
            # Python 3.9 미만에서는 수동으로 포맷팅
            indent_xml(root, level=0, indent_str="")
        
        # XML 선언과 함께 파일로 저장
        with open(output_path, 'wb') as f:
            # standalone="yes" 속성을 포함한 XML 선언 작성
            f.write(b'<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n')
            # 루트 요소부터 저장 (xml_declaration=False로 중복 선언 방지)
            final_tree.write(f, encoding='utf-8', xml_declaration=False)

        print("-" * 30)
        print(f"성공! 원본 순서에 맞춰 '{output_path}' 파일로 병합했습니다.")

    except FileNotFoundError:
        print(f"[오류] '{input_dir}' 또는 '{template_path}' 파일을 찾을 수 없습니다.")
    except Exception as e:
        print(f"[오류] 오류 발생: {e}")

# --- 스크립트 실행 ---
if __name__ == '__main__':
    merge_xml_libraries_ordered(INPUT_FOLDER, ORDER_TEMPLATE_XML_PATH, OUTPUT_XML_PATH)