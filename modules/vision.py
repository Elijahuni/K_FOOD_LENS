# modules/vision.py
import logging
import os
import numpy as np
import cv2
from ultralytics import YOLO
from flask import current_app, g
from datetime import datetime

logger = logging.getLogger(__name__)

# 클래스별 최적 모델 매핑
CLASS_MODEL_MAPPING = {
    'gimbap': 'model_m',             # YOLOv8m이 더 좋음 (0.986 vs 0.947)
    'tteokbokki': 'model_m',         # YOLOv8m이 약간 더 좋음 (0.894 vs 0.889)
    'samgyetang': 'model_l',         # YOLOv8l이 더 좋음 (0.874 vs 0.868)
    'kimchi': 'model_m',             # YOLOv8m이 훨씬 더 좋음 (0.965 vs 0.826)
    'jajangmyeon': 'model_m',        # YOLOv8m이 훨씬 더 좋음 (0.986 vs 0.801)
    'pajeon': 'model_m',             # YOLOv8m이 약간 더 좋음 (0.980 vs 0.956)
    'yangnyeom_chicken': 'model_l',  # YOLOv8l이 훨씬 더 좋음 (0.868 vs 0.732)
    'grilled_eel': 'model_m',        # YOLOv8m이 더 좋음 (0.812 vs 0.777)
    'braised_cutlassfish': 'model_m', # YOLOv8m이 더 좋음 (0.817 vs 0.809)
    'bulgogi': 'model_l',            # YOLOv8l이 약간 더 좋음 (0.797 vs 0.789)
    'bibimbap': 'model_l',           # YOLOv8l이 더 좋음 (0.945 vs 0.897)
    'samgyeopsal': 'model_m',        # YOLOv8m이 약간 더 좋음 (0.830 vs 0.811)
    'sundae': 'model_l',             # YOLOv8l이 약간 더 좋음 (0.971 vs 0.966)
    'jeyuk_bokkeum': 'model_m',      # YOLOv8m이 약간 더 좋음 (0.902 vs 0.900)
    'ramyeon': 'model_m',            # YOLOv8m이 약간 더 좋음 (0.905 vs 0.903)
    'mul_naengmyeon': 'model_m',     # YOLOv8m이 약간 더 좋음 (0.910 vs 0.907)
    'bibim_naengmyeon': 'model_l',   # YOLOv8l이 더 좋음 (0.948 vs 0.921)
    'jokbal': 'model_m',             # YOLOv8m이 약간 더 좋음 (0.935 vs 0.931)
    'galbitang': 'model_l',          # YOLOv8l이 더 좋음 (0.904 vs 0.900)
    'gamjatang': 'model_m',          # YOLOv8m이 약간 더 좋음 (0.884 vs 0.879)
    'kimchi_fried_rice': 'model_l',  # YOLOv8l이 더 좋음 (0.976 vs 0.927)
    'kimchi_jjigae': 'model_m',      # YOLOv8m이 더 좋음 (0.892 vs 0.809)
    'doenjang_jjigae': 'model_m',    # YOLOv8m이 더 좋음 (0.944 vs 0.911)
    'mandu': 'model_m',              # YOLOv8m이 약간 더 좋음 (0.927 vs 0.922)
    'bossam': 'model_l',             # YOLOv8l이 더 좋음 (0.950 vs 0.882)
}

# 클래스 이름을 메타데이터의 nameEn과 매핑하는 사전
CLASS_TO_METADATA_MAPPING = {
    'gimbap': 'Gimbap',
    'tteokbokki': 'Stir-fried Rice Cake',
    'samgyetang': 'Ginseng Chicken Soup',
    'kimchi': 'Kimchi(Baechukimchi)',
    'jajangmyeon': 'Jajangmyeon',
    'pajeon': 'Green Onion Pancake',
    'yangnyeom_chicken': 'Seasoned Fried Chicken',
    'grilled_eel': 'Grilled Eel',
    'braised_cutlassfish': 'Braised Cutlassfish',
    'bulgogi': 'Bulgogi',
    'bibimbap': 'Bibimbap',
    'samgyeopsal': 'Grilled Pork Belly',
    'sundae': 'Blood Sausage',
    'jeyuk_bokkeum': 'Stir-fried Pork',
    'ramyeon': 'Ramyeon',
    'mul_naengmyeon': 'Cold Buckwheat Noodles',
    'bibim_naengmyeon': 'Spicy Buckwheat Noodles',
    'jokbal': 'Braised Pigs\' Feet',
    'galbitang': 'Short Rib Soup',
    'gamjatang': 'Pork Back-bone Stew',
    'kimchi_fried_rice': 'Kimchi Fried Rice',
    'kimchi_jjigae': 'Kimchi Stew',
    'doenjang_jjigae': 'Soybean Paste Stew',
    'mandu': 'Dumplings',
    'bossam': 'Kimchi Wraps with Pork'
}

models = {
    'model_m': None,
    'model_l': None
}

def init_vision_models(app):
    """YOLO 모델을 초기화합니다."""
    global models
    try:
        logger.info("YOLOv8 모델 로딩 중...")
        model_m_path = app.config['MODEL_M_PATH']
        model_l_path = app.config['MODEL_L_PATH']
        
        # 모델 파일 존재 확인
        if not os.path.exists(model_m_path):
            logger.error(f"모델 파일을 찾을 수 없습니다: {model_m_path}")
            return False
        
        if not os.path.exists(model_l_path):
            logger.error(f"모델 파일을 찾을 수 없습니다: {model_l_path}")
            return False
        
        # 모델 로드
        from ultralytics import YOLO
        models['model_m'] = YOLO(model_m_path)
        models['model_l'] = YOLO(model_l_path)
        
        logger.info("YOLOv8 모델 로딩 완료")
        return True
    except Exception as e:
        logger.error(f"YOLO 모델 로딩 중 오류 발생: {e}")
        models['model_m'] = None
        models['model_l'] = None
        return False

def get_models():
    """YOLO 모델을 가져옵니다."""
    global models
    if models['model_m'] is None or models['model_l'] is None:
        logger.error("YOLO 모델이 초기화되지 않았습니다.")
        return None, None
    return models['model_m'], models['model_l']

def ensemble_predictions_class_based(img_path, conf_threshold=0.25):
    """클래스별 선택적 앙상블 방식으로 두 모델의 예측을 결합합니다."""
    try:
        # 이미지 검증
        if not verify_image(img_path):
            logger.error(f"이미지 검증 실패: {img_path}")
            return [], [], []
        
        # 모델 가져오기
        model_m, model_l = get_models()
        if model_m is None or model_l is None:
            logger.error("모델이 초기화되지 않았습니다.")
            return [], [], []
        
        # 성능 측정 시작
        import time
        start_time = time.time()
        
        # 각 모델의 예측 수행
        try:
            results_m = model_m(img_path, conf=conf_threshold)[0]
        except Exception as e:
            logger.error(f"모델 M 추론 실패: {str(e)}")
            return [], [], []
        
        try:
            results_l = model_l(img_path, conf=conf_threshold)[0]
        except Exception as e:
            logger.error(f"모델 L 추론 실패: {str(e)}")
            return [], [], []
        
        # 결과를 결합하기 위한 빈 리스트
        ensemble_boxes = []
        ensemble_scores = []
        ensemble_class_ids = []
        
        # 클래스 이름 가져오기
        class_names = results_m.names
        
        # 첫 번째 모델(YOLOv8m)의 결과 처리
        if hasattr(results_m, 'boxes') and len(results_m.boxes) > 0:
            try:
                boxes_m = results_m.boxes.xyxy.cpu().numpy()
                scores_m = results_m.boxes.conf.cpu().numpy()
                class_ids_m = results_m.boxes.cls.cpu().numpy().astype(int)
                
                # 모델 M의 결과에서 각 클래스별로 선택
                for i in range(len(boxes_m)):
                    class_id = class_ids_m[i]
                    class_name = class_names[class_id]
                    
                    # 매핑 테이블에서 이 클래스에 최적인 모델 확인
                    if class_name in CLASS_MODEL_MAPPING and CLASS_MODEL_MAPPING[class_name] == 'model_m':
                        ensemble_boxes.append(boxes_m[i])
                        ensemble_scores.append(scores_m[i])
                        ensemble_class_ids.append(class_id)
            except Exception as e:
                logger.warning(f"YOLOv8m 결과 처리 중 오류 발생: {e}")
        
        # 두 번째 모델(YOLOv8l)의 결과 처리
        if hasattr(results_l, 'boxes') and len(results_l.boxes) > 0:
            try:
                boxes_l = results_l.boxes.xyxy.cpu().numpy()
                scores_l = results_l.boxes.conf.cpu().numpy()
                class_ids_l = results_l.boxes.cls.cpu().numpy().astype(int)
                
                # 모델 L의 결과에서 각 클래스별로 선택
                for i in range(len(boxes_l)):
                    class_id = class_ids_l[i]
                    class_name = class_names[class_id]
                    
                    # 매핑 테이블에서 이 클래스에 최적인 모델 확인
                    if class_name in CLASS_MODEL_MAPPING and CLASS_MODEL_MAPPING[class_name] == 'model_l':
                        ensemble_boxes.append(boxes_l[i])
                        ensemble_scores.append(scores_l[i])
                        ensemble_class_ids.append(class_id)
            except Exception as e:
                logger.warning(f"YOLOv8l 결과 처리 중 오류 발생: {e}")
        
        # 결합된 결과에 NMS 적용
        if ensemble_boxes:
            ensemble_boxes = np.array(ensemble_boxes)
            ensemble_scores = np.array(ensemble_scores)
            ensemble_class_ids = np.array(ensemble_class_ids)
            
            # NMS 적용 - 입력 형식 확인
            if len(ensemble_boxes) > 0:
                try:
                    indices = cv2.dnn.NMSBoxes(
                        ensemble_boxes.tolist(), 
                        ensemble_scores.tolist(), 
                        conf_threshold, 
                        0.45
                    )
                    
                    filtered_boxes = []
                    filtered_scores = []
                    filtered_class_ids = []
                    
                    # OpenCV 버전에 따라 indices 형식이 다를 수 있으므로 안전하게 처리
                    if isinstance(indices, np.ndarray):
                        # 최신 OpenCV 버전
                        for idx in indices:
                            filtered_boxes.append(ensemble_boxes[idx])
                            filtered_scores.append(ensemble_scores[idx])
                            filtered_class_ids.append(int(ensemble_class_ids[idx]))
                    else:
                        # 이전 OpenCV 버전
                        for i in indices:
                            idx = i if isinstance(i, int) else i[0]
                            filtered_boxes.append(ensemble_boxes[idx])
                            filtered_scores.append(ensemble_scores[idx])
                            filtered_class_ids.append(int(ensemble_class_ids[idx]))
                    
                    # 성능 측정 종료
                    elapsed_time = time.time() - start_time
                    
                    # 결과 로깅
                    logger.info(f"앙상블 결과: {len(filtered_boxes)}개 객체 감지됨 ({elapsed_time:.2f}초)")
                    
                    return filtered_boxes, filtered_scores, filtered_class_ids
                except Exception as e:
                    logger.error(f"NMS 적용 중 오류 발생: {e}")
        
        # 앙상블 결과가 없으면 원본 결과 중 하나 사용
        if hasattr(results_m, 'boxes') and len(results_m.boxes) > 0:
            try:
                boxes = results_m.boxes.xyxy.cpu().numpy()
                scores = results_m.boxes.conf.cpu().numpy()
                class_ids = results_m.boxes.cls.cpu().numpy().astype(int)
                
                # 성능 측정 종료
                elapsed_time = time.time() - start_time
                
                logger.info(f"앙상블 없음, YOLOv8m 결과 사용: {len(boxes)}개 객체 감지됨 ({elapsed_time:.2f}초)")
                return boxes, scores, class_ids
            except Exception as e:
                logger.warning(f"YOLOv8m 결과 대체 처리 중 오류 발생: {e}")
        
        if hasattr(results_l, 'boxes') and len(results_l.boxes) > 0:
            try:
                boxes = results_l.boxes.xyxy.cpu().numpy()
                scores = results_l.boxes.conf.cpu().numpy()
                class_ids = results_l.boxes.cls.cpu().numpy().astype(int)
                
                # 성능 측정 종료
                elapsed_time = time.time() - start_time
                
                logger.info(f"앙상블 없음, YOLOv8l 결과 사용: {len(boxes)}개 객체 감지됨 ({elapsed_time:.2f}초)")
                return boxes, scores, class_ids
            except Exception as e:
                logger.warning(f"YOLOv8l 결과 대체 처리 중 오류 발생: {e}")
        
        # 결과가 없는 경우
        elapsed_time = time.time() - start_time
        logger.warning(f"앙상블 및 개별 모델 결과 모두 처리 실패 ({elapsed_time:.2f}초)")
        return [], [], []
    except Exception as e:
        logger.error(f"앙상블 예측 중 예기치 않은 오류 발생: {e}", exc_info=True)
        return [], [], []

def verify_image(img_path):
    """이미지 파일을 검증합니다."""
    try:
        if not os.path.exists(img_path):
            logger.error(f"이미지 파일이 존재하지 않습니다: {img_path}")
            return False
        
        # OpenCV로 이미지 읽기 테스트
        img = cv2.imread(img_path)
        if img is None or img.size == 0:
            logger.error(f"이미지 파일을 읽을 수 없습니다: {img_path}")
            return False
        
        # 이미지 크기가 너무 작은지 확인
        if img.shape[0] < 10 or img.shape[1] < 10:
            logger.error(f"이미지 크기가 너무 작습니다: {img.shape}")
            return False
        
        return True
    except Exception as e:
        logger.error(f"이미지 검증 중 예기치 않은 오류: {e}", exc_info=True)
        return False

def get_class_to_metadata_mapping():
    """클래스 이름과 메타데이터 이름 간의 매핑을 반환합니다."""
    return CLASS_TO_METADATA_MAPPING