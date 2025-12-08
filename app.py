import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from fredapi import Fred
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore')

# ============================================================
# 페이지 설정
# ============================================================
st.set_page_config(
    page_title="통합 금융 위험관리 대시보드",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# 1. 로그인 상태 확인 함수
# ============================================================
def check_password():
    """비밀번호 확인 및 로그인 상태 관리"""
    if st.session_state.get('password_correct', False):
        return True
    
    st.title("🔒 퀀트 대시보드 로그인")
    
    with st.form("credentials"):
        username = st.text_input("아이디 (ID)", key="username")
        password = st.text_input("비밀번호 (Password)", type="password", key="password")
        submit_btn = st.form_submit_button("로그인", type="primary")
    
    if submit_btn:
        try:
            if "passwords" in st.secrets and username in st.secrets["passwords"]:
                if password == st.secrets["passwords"][username]:
                    st.session_state['password_correct'] = True
                    st.rerun()
                else:
                    st.error("😕 비밀번호가 올바르지 않습니다.")
            else:
                st.error("😕 존재하지 않는 아이디입니다.")
        except Exception as e:
            st.error(f"로그인 오류: {str(e)}")
            
    return False

if not check_password():
    st.stop()

# ============================================================
# 2. API 키 설정
# ============================================================
try:
    FRED_API_KEY = st.secrets["FRED_API_KEY"]
except KeyError:
    st.error("❌ FRED_API_KEY가 Secrets에 설정되지 않았습니다.")
    st.stop()

try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    GEMINI_AVAILABLE = True
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
except KeyError:
    GEMINI_AVAILABLE = False
    st.sidebar.warning("⚠️ Gemini API 키가 없어 AI 분석이 비활성화됩니다.")
except Exception as e:
    GEMINI_AVAILABLE = False
    st.sidebar.warning(f"⚠️ Gemini 초기화 실패: {str(e)}")

fred = Fred(api_key=FRED_API_KEY)

# ============================================================
# 3. 스프레드 시나리오 정의
# ============================================================
SCENARIOS = {
    1: {
        'title': '🟡 시나리오 1: 스태그플레이션 우려',
        'meaning': '수익률 곡선 역전 + 긴축 기대 → 인플레이션 지속 + 성장 둔화 조합',
        'risk': '⚠️ 고위험',
        'color': '#f57f17',
        'assets': {
            '주식 (성장주)': '⚠️ 축소 (20-30%)',
            '주식 (가치주)': '✅ 유지 (30-40%)',
            '기술주': '🔴 대폭 축소 (10-15%)',
            '비트코인·고위험 자산': '🔴 최소화 (0-5%)',
            '부동산/리츠': '⚠️ 선별적 (10-15%)',
            '채권': '⚠️ 단기채 중심 (20-30%)',
            '원자재/금': '✅ 확대 (15-20%)',
            '현금': '✅ 비중 확대 (10-20%)'
        }
    },
    2: {
        'title': '🚨 시나리오 2: 침체 경고 (리세션 베이스)',
        'meaning': '수익률 곡선 역전 + 완화 기대 → 경기 침체 임박 신호',
        'risk': '⚠️⚠️ 최고위험',
        'color': '#c62828',
        'assets': {
            '주식 (성장주)': '🚫 강한 축소/청산 (0-10%)',
            '주식 (가치주)': '⚠️ 최소화 (10-20%)',
            '기술주/고베타': '🚫 청산 권고',
            '비트코인·고위험 자산': '🚫 비중 최소/0%',
            '부동산/리츠': '🔴 축소 (0-5%)',
            '채권': '✅ 장기 국채 비중 확대 (40-50%)',
            '금·방어적 실물자산': '✅ 핵심 (20-30%)',
            '현금': '✅ 20-30% 수준 확보'
        }
    },
    3: {
        'title': '✅ 시나리오 3: 건강한 성장',
        'meaning': '정상 수익률 곡선 + 긴축 기대 → 건강한 성장 / 인플레이션 관리',
        'risk': '✅ 저위험',
        'color': '#2e7d32',
        'assets': {
            '주식 (성장주)': '✅ 공격적 (40-50%)',
            '주식 (가치주)': '✅ 균형 (20-30%)',
            '기술주': '✅ 비중 확대 (25-35%)',
            '비트코인·위험자산': '⚠️ 선택적 (5-10%)',
            '부동산/리츠': '✅ 우호적 환경 (10-20%)',
            '채권': '⚠️ 최소화 (5-10%)',
            '금·원자재': '➡️ 중립 (5-10%)',
            '현금': '➡️ 최소 (5-10%)'
        }
    },
    4: {
        'title': '🔄 시나리오 4: 정책 전환점 (Pivot 기대)',
        'meaning': '정상 곡선 + 완화 기대 → 긴축 사이클 종료/피벗 기대',
        'risk': '➡️ 중간위험',
        'color': '#1565c0',
        'assets': {
            '주식 (성장주)': '⚠️ 조정 (25-35%)',
            '주식 (가치주)': '✅ 확대 (25-35%)',
            '기술주': '⚠️ 선별적 (20-25%)',
            '비트코인·위험자산': '✅ 점진적 확대 (10-15%)',
            '부동산/리츠': '✅ 매수 기회 (15-20%)',
            '채권': '✅ 장기채 비중 확대 (20-30%)',
            '금·원자재': '➡️ 중립 (5-10%)',
            '현금': '➡️ 10-15% 유지'
        }
    }
}

# ============================================================
# 4. 데이터 수집 함수
# ============================================================
@st.cache_data(ttl=3600)
def fetch_series_with_ffill(series_id, start_date, name=""):
    """FRED에서 시리즈를 가져오고 forward-fill로 결측치 보정"""
    try:
        data = fred.get_series(series_id, observation_start=start_date)
        if len(data) > 0:
            data = data.sort_index().ffill()
            return data
        else:
            return pd.Series(dtype=float)
    except Exception as e:
        st.warning(f"⚠️ {name or series_id} 수집 실패: {e}")
        return pd.Series(dtype=float)

@st.cache_data(ttl=3600)
def load_all_series(start_date):
    """모든 시리즈를 한 번에 수집"""
    
    with st.spinner('📡 FRED API에서 데이터 수집 중...'):
        series_dict = {
            'DGS10': fetch_series_with_ffill('DGS10', start_date, "10년물 국채"),
            'DGS2': fetch_series_with_ffill('DGS2', start_date, "2년물 국채"),
            'T10Y2Y': fetch_series_with_ffill('T10Y2Y', start_date, "장단기 금리차"),
            'HY_SPREAD': fetch_series_with_ffill('BAMLH0A0HYM2', start_date, "하이일드 스프레드"),
            'IG_SPREAD': fetch_series_with_ffill('BAMLC0A0CM', start_date, "투자등급 스프레드"),
            'FEDFUNDS': fetch_series_with_ffill('FEDFUNDS', start_date, "연준 기준금리"),
            'EFFR': fetch_series_with_ffill('EFFR', start_date, "유효 연방기금금리"),
            'WALCL': fetch_series_with_ffill('WALCL', start_date, "연준 총자산"),
            'CC_DELINQ': fetch_series_with_ffill('DRCCLACBS', start_date, "신용카드 연체율"),
            'CONS_DELINQ': fetch_series_with_ffill('DRCLACBS', start_date, "소비자 대출 연체율"),
            'AUTO_DELINQ': fetch_series_with_ffill('DROCLACBS', start_date, "오토론 연체율"),
            'CRE_DELINQ_ALL': fetch_series_with_ffill('DRCRELEXFACBS', start_date, "CRE 연체율"),
            'CRE_DELINQ_TOP100': fetch_series_with_ffill('DRCRELEXFT100S', start_date, "CRE 연체율(Top100)"),
            'CRE_DELINQ_SMALL': fetch_series_with_ffill('DRCRELEXFOBS', start_date, "CRE 연체율(기타)"),
            'RE_DELINQ_ALL': fetch_series_with_ffill('DRSREACBS', start_date, "부동산 연체율"),
            'CRE_LOAN_AMT': fetch_series_with_ffill('CREACBM027NBOG', start_date, "CRE 대출 총액"),
        }
    
    return series_dict

def build_master_df(series_dict):
    """10년물 금리를 기준 인덱스로 통합 DataFrame 생성"""
    base = series_dict['DGS10']
    df = pd.DataFrame({'DGS10': base})
    
    for name, s in series_dict.items():
        if name == 'DGS10':
            continue
        df[name] = s.reindex(df.index, method='ffill')
    
    # 파생 지표 계산
    df['YIELD_CURVE_DIRECT'] = series_dict['T10Y2Y'].reindex(df.index, method='ffill')
    df['YIELD_CURVE_CALC'] = df['DGS10'] - df['DGS2']
    df['YIELD_CURVE'] = df['YIELD_CURVE_DIRECT'].fillna(df['YIELD_CURVE_CALC'])
    df['RATE_GAP'] = df['DGS10'] - df['FEDFUNDS']
    df['POLICY_SPREAD'] = df['DGS2'] - df['EFFR']
    
    return df.dropna(subset=['DGS10'])

# ============================================================
# 5. 분석 함수들
# ============================================================
def find_inversion_periods(yield_curve_series):
    """수익률 곡선 역전 구간 탐지"""
    inversions = []
    in_inv = False
    start = None
    
    for date, val in yield_curve_series.items():
        if pd.isna(val):
            continue
        if val < 0 and not in_inv:
            in_inv = True
            start = date
        elif val >= 0 and in_inv:
            inversions.append((start, date))
            in_inv = False
    
    if in_inv:
        inversions.append((start, yield_curve_series.index[-1]))
    
    return inversions

def assess_macro_risk(df):
    """종합 위험도 평가"""
    latest = df.iloc[-1]
    risk_score = 0
    warnings_ = []
    
    # 1) 수익률 곡선
    yc = latest['YIELD_CURVE']
    if yc < 0:
        risk_score += 3
        warnings_.append("🔴 수익률 곡선 역전 (경기침체 전조)")
    elif yc < 0.3:
        risk_score += 1
        warnings_.append("⚠️ 수익률 곡선 평탄화 (역전 임박)")
    
    # 2) 10년물 금리
    if latest['DGS10'] > 4.5:
        risk_score += 2
        warnings_.append("⚠️ 10년물 금리 고점 영역")
    elif latest['DGS10'] > 4.0:
        risk_score += 1
        warnings_.append("💡 10년물 금리 상승 추세")
    
    # 3) 하이일드 스프레드
    hy = latest['HY_SPREAD']
    if hy > 5.0:
        risk_score += 3
        warnings_.append("🔴 하이일드 스프레드 급등")
    elif hy > 4.5:
        risk_score += 2
        warnings_.append("⚠️ 하이일드 스프레드 확대")
    
    # 4) 금리 괴리
    rg = latest['RATE_GAP']
    if rg > 1.0:
        risk_score += 2
        warnings_.append("💧 금리 괴리 과도 확대")
    elif rg > 0.5:
        risk_score += 1
        warnings_.append("💧 금리 괴리 확대")
    
    # 5) 신용카드 연체율
    if 'CC_DELINQ' in df.columns:
        cc = df['CC_DELINQ'].dropna()
        if len(cc) > 0:
            cc_val = cc.iloc[-1]
            if cc_val > 5.0:
                risk_score += 3
                warnings_.append("🔴 신용카드 연체율 >5%")
            elif cc_val > 3.5:
                risk_score += 2
                warnings_.append("🪳 신용카드 연체율 급등")
    
    # 6) CRE 연체율
    if 'CRE_DELINQ_ALL' in df.columns:
        cre = df['CRE_DELINQ_ALL'].dropna()
        if len(cre) > 0:
            cre_val = cre.iloc[-1]
            if cre_val > 3.0:
                risk_score += 3
                warnings_.append("🔴 CRE 연체율 >3%")
            elif cre_val > 2.0:
                risk_score += 2
                warnings_.append("🏢 CRE 연체율 상승")
    
    # 7) 오토론 연체율
    if 'AUTO_DELINQ' in df.columns:
        au = df['AUTO_DELINQ'].dropna()
        if len(au) > 0:
            au_val = au.iloc[-1]
            if au_val > 3.0:
                risk_score += 2
                warnings_.append("🚗 오토론 연체율 >3%")
            elif au_val > 2.5:
                risk_score += 1
                warnings_.append("🚗 오토론 연체율 상승세")
    
    # 위험도 등급
    if risk_score >= 10:
        level = "🔴 CRITICAL RISK"
        color = "darkred"
    elif risk_score >= 7:
        level = "🔴 HIGH RISK"
        color = "red"
    elif risk_score >= 4:
        level = "🟡 MEDIUM RISK"
        color = "orange"
    else:
        level = "🟢 LOW RISK"
        color = "green"
    
    return {
        "score": risk_score,
        "level": level,
        "color": color,
        "warnings": warnings_,
        "latest": latest
    }

def determine_scenario(yield_curve, policy_spread):
    """금리 스프레드 기반 시나리오 판별"""
    inverted = yield_curve < 0
    easing_expected = policy_spread < 0
    
    if inverted and not easing_expected:
        return 1  # 스태그플레이션
    elif inverted and easing_expected:
        return 2  # 침체 경고
    elif not inverted and not easing_expected:
        return 3  # 건강한 성장
    else:
        return 4  # 정책 전환점

# ============================================================
# 6. Gemini AI 분석 함수들
# ============================================================
def extract_section(text, section_name):
    """텍스트에서 특정 섹션 추출"""
    try:
        if section_name not in text:
            return None
        
        start = text.find(section_name) + len(section_name)
        
        next_sections = ["MARKET_STATUS:", "KEY_RISKS:", "STRATEGY:", "FULL_ANALYSIS:", "```"]
        end = len(text)
        
        for next_section in next_sections:
            if next_section == section_name:
                continue
            pos = text.find(next_section, start)
            if pos != -1 and pos < end:
                end = pos
        
        section = text[start:end].strip()
        section = section.replace("```", "").strip()
        
        return section
        
    except Exception:
        return None

def generate_market_summary(df, risk_info, scenario_info):
    """메인 대시보드용 간결한 AI 시장 분석 요약"""
    if not GEMINI_AVAILABLE:
        return {
            'market_status': '⚠️ API 없음',
            'key_risks': '⚠️ API 없음',
            'strategy': '⚠️ API 없음',
            'full_analysis': '⚠️ Gemini API가 설정되지 않았습니다.'
        }
    
    latest = df.iloc[-1]
    
    prompt = f"""
당신은 금융시장 전문가입니다. 다음 데이터를 바탕으로 **간결하고 실용적인** 시장 분석을 제공하세요.

## 현재 시장 데이터 ({df.index[-1].strftime('%Y-%m-%d')})
- 수익률 곡선(10Y-2Y): {latest['YIELD_CURVE']:.2f}%p
- 10년물 금리: {latest['DGS10']:.2f}%
- 하이일드 스프레드: {latest['HY_SPREAD']:.2f}%
- 종합 위험도: {risk_info['level']}
- 현재 시나리오: {scenario_info['title']}

## 요청사항 (각 항목을 **2-3문장**으로 간결하게):

### 1. MARKET_STATUS (현재 시장 상황)
시장의 핵심 상태를 2-3문장으로 요약하세요.

### 2. KEY_RISKS (주요 리스크 3가지)
현재 가장 중요한 리스크 3가지를 bullet point로 나열하세요.
각 리스크는 1줄로 간결하게 작성하세요.

### 3. STRATEGY (투자 전략 제언)
현 상황에서 투자자가 취해야 할 핵심 전략을 2-3문장으로 제시하세요.

### 4. FULL_ANALYSIS (상세 분석)
위 3가지를 종합하여 전체적인 시장 분석을 5-7문장으로 작성하세요.

**응답 형식** (반드시 이 형식을 지켜주세요):
