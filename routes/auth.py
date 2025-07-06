# routes/auth.py
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from bson.objectid import ObjectId
import functools

from modules.database import get_db

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """로그인 페이지 및 처리"""
    if request.method == 'POST':
        email = request.form.get('email')  # username 대신 email 사용
        password = request.form.get('password')
        
        if not email or not password:
            flash('이메일과 비밀번호를 모두 입력해주세요.', 'error')
            return render_template('auth/login.html')
        
        try:
            db = get_db()
            # 이메일로 사용자 검색
            user = db.users.find_one({'email': email})
            
            if not user or not check_password_hash(user['password'], password):
                flash('이메일 또는 비밀번호가 올바르지 않습니다.', 'error')
                return render_template('auth/login.html')
            
            # 세션에 사용자 정보 저장
            session.clear()
            session['user_id'] = str(user['_id'])
            session['email'] = user['email']
            
            # username이 있으면 저장, 없으면 이메일에서 추출
            if 'username' in user:
                session['username'] = user['username']
            else:
                session['username'] = user['email'].split('@')[0]
            
            flash('로그인 되었습니다.', 'success')
            return redirect(url_for('main.index'))
            
        except Exception as e:
            logger.error(f"로그인 중 오류 발생: {e}")
            flash('로그인 처리 중 오류가 발생했습니다.', 'error')
            return render_template('auth/login.html')
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """회원가입 페이지 및 처리"""
    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        
        # 알레르기 및 채식 정보 가져오기
        allergens = request.form.getlist('allergens')  # 체크박스 여러 개 선택 가능
        vegetarian = 'vegetarian' in request.form  # 체크박스 선택 여부
        
        # 입력 검증
        if not email or not username or not password or not password_confirm:
            flash('모든 필수 필드를 입력해주세요.', 'error')
            return render_template('auth/register.html')
        
        if password != password_confirm:
            flash('비밀번호가 일치하지 않습니다.', 'error')
            return render_template('auth/register.html')
        
        try:
            db = get_db()
            
            # 중복 사용자 검사
            if db.users.find_one({'username': username}):
                flash('이미 사용 중인 아이디입니다.', 'error')
                return render_template('auth/register.html')
                
            if db.users.find_one({'email': email}):
                flash('이미 사용 중인 이메일입니다.', 'error')
                return render_template('auth/register.html')
            
            # 새 사용자 추가
            user = {
                'username': username,
                'password': generate_password_hash(password),
                'email': email,
                'created_at': datetime.now(),
                'preferences': {
                    'allergens': allergens,  # 알레르기 정보 저장
                    'vegetarian': vegetarian,  # 채식 정보 저장
                    'preferred_categories': []
                },
                'stats': {
                    'recognitions': 0,
                    'menu_recognitions': 0
                }
            }
            
            db.users.insert_one(user)
            
            flash('회원가입이 완료되었습니다. 로그인해주세요.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            logger.error(f"회원가입 중 오류 발생: {e}")
            flash('회원가입 처리 중 오류가 발생했습니다.', 'error')
            return render_template('auth/register.html')
    
    return render_template('auth/register.html')

@auth_bp.route('/logout')
def logout():
    """로그아웃 처리"""
    session.clear()
    flash('로그아웃 되었습니다.', 'success')
    return redirect(url_for('main.index'))

@auth_bp.route('/profile')
def profile():
    if 'user_id' not in session:
        flash('Login required.', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        db = get_db()
        user_id = session.get('user_id')
        
        # Convert string ID to ObjectId
        try:
            object_id = ObjectId(user_id)
        except Exception as e:
            session.clear()
            flash('Session expired. Please login again.', 'error')
            return redirect(url_for('auth.login'))
        
        user = db.users.find_one({'_id': object_id})
        
        if not user:
            session.clear()
            flash('User not found. Please login again.', 'error')
            return redirect(url_for('auth.login'))
        
        # Add default values if needed
        if 'stats' not in user:
            user['stats'] = {'recognitions': 0, 'menu_recognitions': 0}
        if 'preferences' not in user:
            user['preferences'] = {'allergens': [], 'vegetarian': False, 'preferred_categories': []}
        
        return render_template('auth/profile.html', user=user)
        
    except Exception as e:
        logger.error(f"Profile error: {e}")
        flash('An error occurred while loading your profile.', 'error')
        return redirect(url_for('main.index'))

@auth_bp.route('/preferences', methods=['GET', 'POST'])
def preferences():
    """사용자 음식 선호도 설정 페이지"""
    if 'user_id' not in session:
        flash('로그인이 필요합니다.', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        try:
            # 알레르기 정보
            allergens = request.form.getlist('allergens')
            
            # 채식 여부
            vegetarian = request.form.get('vegetarian') == 'on'
            
            # 선호 음식 카테고리
            preferred_categories = request.form.getlist('preferred_categories')
            
            # 사용자 설정 업데이트
            db = get_db()
            db.users.update_one(
                {'_id': ObjectId(session['user_id'])},
                {'$set': {
                    'preferences.allergens': allergens,
                    'preferences.vegetarian': vegetarian,
                    'preferences.preferred_categories': preferred_categories
                }}
            )
            
            flash('선호도 설정이 저장되었습니다.', 'success')
            return redirect(url_for('auth.profile'))
            
        except Exception as e:
            logger.error(f"선호도 설정 저장 중 오류 발생: {e}")
            flash('선호도 설정 저장 중 오류가 발생했습니다.', 'error')
    
    # GET 요청 처리
    try:
        db = get_db()
        user = db.users.find_one({'_id': ObjectId(session['user_id'])})
        
        # 알레르기 옵션 목록 (대표적인 알레르기 유발 식품)
        allergen_options = [
            {'id': 'gluten', 'name': '글루텐'},
            {'id': 'dairy', 'name': '유제품'},
            {'id': 'soy', 'name': '대두'},
            {'id': 'nuts', 'name': '견과류'},
            {'id': 'shellfish', 'name': '갑각류'},
            {'id': 'fish', 'name': '생선'},
            {'id': 'eggs', 'name': '계란'},
            {'id': 'sesame', 'name': '참깨'}
        ]
        
        # 음식 카테고리 옵션
        category_options = [
            {'id': 'rice', 'name': '밥류'},
            {'id': 'noodle', 'name': '면류'},
            {'id': 'soup', 'name': '국/찌개류'},
            {'id': 'meat', 'name': '육류'},
            {'id': 'seafood', 'name': '해산물'},
            {'id': 'vegetable', 'name': '채소류'},
            {'id': 'side_dish', 'name': '반찬류'},
            {'id': 'street_food', 'name': '길거리 음식'}
        ]
        
        return render_template('auth/preferences.html', 
                               user=user,
                               allergen_options=allergen_options,
                               category_options=category_options)
                               
    except Exception as e:
        logger.error(f"선호도 페이지 로드 중 오류 발생: {e}")
        flash('선호도 설정을 불러오는 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('auth.profile'))

def login_required(view):
    """로그인이 필요한 뷰에 데코레이터로 사용"""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user_id' not in session:
            flash('로그인이 필요합니다.', 'error')
            return redirect(url_for('auth.login'))
        return view(**kwargs)
    return wrapped_view