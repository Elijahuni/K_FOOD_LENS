# routes/info.py
import logging
from flask import Blueprint, render_template

logger = logging.getLogger(__name__)

info_bp = Blueprint('info', __name__)

@info_bp.route('/contact')
def contact():
    """연락처 페이지"""
    return render_template('info/contact.html', active_page='contact')

@info_bp.route('/privacy')
def privacy():
    """개인정보 처리방침 페이지"""
    return render_template('info/privacy.html', active_page='privacy')

@info_bp.route('/terms')
def terms():
    """이용약관 페이지"""
    return render_template('info/terms.html', active_page='terms')