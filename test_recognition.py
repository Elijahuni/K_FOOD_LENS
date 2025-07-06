"""
인식 결과 저장 및 조회 테스트 스크립트
Flask 앱 컨텍스트 내에서 실행해야 합니다.
"""
from flask import session
from modules.database import save_recognition_result, get_recent_recognitions
from bson.objectid import ObjectId
import datetime

def test_save_recognition():
    """인식 결과 저장 테스트"""
    # 테스트용 이미지 경로
    image_path = "static/uploads/test_image.jpg"
    
    # 테스트용 인식 결과
    detected_foods = [
        {
            "food_name": "김밥",
            "confidence": 0.95
        },
        {
            "food_name": "떡볶이",
            "confidence": 0.85
        }
    ]
    
    # 테스트용 유저 ID 세션에 설정
    session['user_id'] = "60a7d12d8f0b2d3e4c5b6a7d"  # 테스트할 실제 사용자 ID로 변경
    
    # 결과 저장
    record_id = save_recognition_result(image_path, detected_foods)
    print(f"저장된 레코드 ID: {record_id}")
    
    # 저장된 결과 확인
    filter = {'user_id': session['user_id']}
    records = get_recent_recognitions(limit=5, filter=filter)
    
    print(f"조회된 레코드 수: {len(records)}")
    for record in records:
        print(f"- ID: {record['_id']}")
        print(f"  이미지: {record['image_path']}")
        print(f"  인식 음식 수: {len(record['detected_foods'])}")
        print(f"  타임스탬프: {record['timestamp']}")
        print("  인식된 음식:")
        for food in record['detected_foods']:
            print(f"    - {food['food_name']} ({food['confidence']:.2f})")
        print()

if __name__ == "__main__":
    # 이 스크립트는 Flask 앱 컨텍스트 내에서 실행해야 합니다.
    # app.py에서 다음과 같이 실행할 수 있습니다:
    # 
    # with app.app_context():
    #     from test_recognition import test_save_recognition
    #     test_save_recognition()
    #
    print("이 스크립트는 Flask 앱 컨텍스트 내에서 실행해야 합니다.")