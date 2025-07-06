import cv2
import numpy as np
import os
import json
import base64
from datetime import datetime
from flask import current_app, url_for
from bson import json_util

def create_text_overlay_image(img_path, boxes, scores, class_ids, class_names, food_info=None):
    """
    인식 결과에 텍스트 오버레이를 추가한 이미지 생성 (영어로만 표시)
    """
    try:
        # 이미지 로드
        img = cv2.imread(img_path)
        if img is None:
            return None
            
        # 이미지 복사
        result_img = img.copy()
        
        # 사용된 모델 정보 표시 - 오른쪽 상단으로 이동
        model_info = "YOLOv8 Ensemble Model"
        model_text_size = cv2.getTextSize(model_info, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
        model_text_x = result_img.shape[1] - model_text_size[0] - 10  # 오른쪽에서 10픽셀 여백
        cv2.putText(result_img, model_info, (model_text_x, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # 각 인식된 객체에 대해 처리
        for i, box in enumerate(boxes):
            class_id = int(class_ids[i])
            score = scores[i]
            
            # 좌표 변환
            x1, y1, x2, y2 = map(int, box)
            
            # 클래스 이름 가져오기 - 영어 이름 사용
            class_name = class_names.get(class_id, f"Class {class_id}")
            
            # 바운딩 박스 그리기
            cv2.rectangle(result_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # 음식에 대한 기본 정보 가져오기 - 영어 이름 우선 사용
            eng_name = ""
            allergens = []
            veg_status = ""
            
            if food_info and class_name in food_info:
                food_details = food_info[class_name]
                # 영어 이름 가져오기 (없으면 class_name 사용)
                eng_name = food_details.get('nameEn', class_name)
                allergens = food_details.get('allergens', [])
                
                # 채식 상태를 영어로 변환
                korean_veg_status = food_details.get('vegetarianStatus', '')
                if korean_veg_status == '완전채식':
                    veg_status = 'Vegetarian'
                elif korean_veg_status == '부분채식':
                    veg_status = 'Vegetarian-Optional'
                else:
                    veg_status = 'Non-Vegetarian'
            
            # 텍스트 배경 그리기
            label = eng_name if eng_name else class_name
            conf_text = f"Confidence: {score:.2f}"
            veg_text = f"Diet: {veg_status}" if veg_status else ""
            
            # 텍스트 크기 계산
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            thickness = 2
            
            (label_width, label_height), _ = cv2.getTextSize(label, font, font_scale, thickness)
            (conf_width, conf_height), _ = cv2.getTextSize(conf_text, font, 0.5, 1)
            (veg_width, veg_height), _ = cv2.getTextSize(veg_text, font, 0.5, 1)
            
            # 가장 넓은 텍스트 너비 사용
            max_width = max(label_width, conf_width, veg_width) + 20
            
            # 텍스트 배경 위치 (바운딩 박스 위)
            bg_height = label_height + conf_height + veg_height + 35
            
            # 이미지 위쪽을 벗어나지 않도록 조정
            text_y_start = max(0, y1 - bg_height - 5)
            
            # 배경 좌표
            bg_x1 = x1
            bg_y1 = text_y_start
            bg_x2 = x1 + max_width
            bg_y2 = text_y_start + bg_height
            
            # 배경 그리기 (50% 투명도의 검은색)
            overlay = result_img.copy()
            cv2.rectangle(overlay, (bg_x1, bg_y1), (bg_x2, bg_y2), (0, 0, 0), -1)
            # 투명도 적용 (0.5 = 50% 투명)
            cv2.addWeighted(overlay, 0.5, result_img, 0.5, 0, result_img)
            
            # 텍스트 그리기
            y_offset = bg_y1 + label_height + 5
            cv2.putText(result_img, label, (bg_x1 + 10, y_offset), 
                       font, font_scale, (0, 255, 0), thickness)
            
            y_offset += conf_height + 10
            cv2.putText(result_img, conf_text, (bg_x1 + 10, y_offset), 
                       font, 0.5, (255, 255, 255), 1)
            
            if veg_text:
                y_offset += veg_height + 10
                # 채식 상태에 따라 색상 설정
                veg_color = (0, 255, 0) if "Vegetarian" in veg_status else (0, 165, 255) if "Optional" in veg_status else (0, 0, 255)
                cv2.putText(result_img, veg_text, (bg_x1 + 10, y_offset), 
                           font, 0.5, veg_color, 1)
            
            # 알레르기 정보 추가 (바운딩 박스 아래)
            if allergens:
                allergen_text = "Allergens: " + ", ".join(allergens)
                (allergen_width, allergen_height), _ = cv2.getTextSize(allergen_text, font, 0.5, 1)
                
                # 알레르기 정보 배경
                allergen_bg_y1 = y2 + 5
                allergen_bg_y2 = allergen_bg_y1 + allergen_height + 10
                allergen_bg_x2 = x1 + allergen_width + 20
                
                # 배경 그리기 (50% 투명도의 검은색)
                overlay = result_img.copy()
                cv2.rectangle(overlay, (x1, allergen_bg_y1), (allergen_bg_x2, allergen_bg_y2), (0, 0, 0), -1)
                cv2.addWeighted(overlay, 0.5, result_img, 0.5, 0, result_img)
                
                # 알레르기 정보 텍스트 (빨간색으로 강조)
                cv2.putText(result_img, allergen_text, (x1 + 10, allergen_bg_y1 + allergen_height + 5), 
                           font, 0.5, (0, 0, 255), 1)
        
        # 결과 이미지 저장
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        output_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'results')
        os.makedirs(output_dir, exist_ok=True)
        
        base_filename = os.path.basename(img_path)
        filename, ext = os.path.splitext(base_filename)
        result_filename = f"{timestamp}_{filename}_result{ext}"
        result_path = os.path.join(output_dir, result_filename)
        
        cv2.imwrite(result_path, result_img)
        
        return result_path
    except Exception as e:
        import traceback
        print(f"텍스트 오버레이 이미지 생성 중 오류: {e}")
        print(traceback.format_exc())
        return None

def generate_modal_data(img_path, boxes, scores, class_ids, class_names, food_info=None):
    """
    모달 윈도우용 데이터 생성
    """
    try:
        # 이미지 base64 인코딩
        with open(img_path, 'rb') as img_file:
            img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
        
        # 인식 결과 데이터 생성
        detection_data = []
        
        for i, box in enumerate(boxes):
            class_id = int(class_ids[i])
            score = float(scores[i])
            class_name = class_names.get(class_id, f"Class {class_id}")
            
            # 음식 상세 정보
            food_detail = None
            if food_info and class_name in food_info:
                food_detail = food_info[class_name]
            
            detection_data.append({
                'box': {
                    'x1': float(box[0]),
                    'y1': float(box[1]),
                    'x2': float(box[2]),
                    'y2': float(box[3])
                },
                'class_id': class_id,
                'class_name': class_name,
                'confidence': score,
                'food_info': food_detail
            })
        
        # 결과 데이터
        modal_data = {
            'image_base64': img_base64,
            'detections': detection_data
        }
        
        return modal_data
    except Exception as e:
        import traceback
        print(f"모달 데이터 생성 중 오류: {e}")
        print(traceback.format_exc())
        return None
def create_interactive_html(modal_data, title='K-FOOD LENS - 인식 결과'):
    """
    인터랙티브 HTML 결과 페이지 생성 - 간소화된 버전
    """
    # 이 함수는 더 이상 인터랙티브 HTML 결과를 생성하지 않습니다
    # 대신 None을 반환합니다
    return None
def get_default_template():
    """기본 HTML 템플릿 반환 - 간소화된 버전"""
    # 이 함수는 더 이상 인터랙티브 템플릿을 제공하지 않습니다
    return None  
def save_modal_html(modal_data, food_info=None):
    """
    모달 창 HTML 파일 저장 (이전 버전과의 호환성 유지)
    """
    return None