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
    page_title="신용지표 연체율 대시보드(후행지표)",
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
```
MARKET_STATUS:
[2-3문장]

KEY_RISKS:
- [리스크 1]
- [리스크 2]
- [리스크 3]

STRATEGY:
[2-3문장]

FULL_ANALYSIS:
[5-7문장]
```

간결하고 실용적으로 작성하세요.
"""
    
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        response = model.generate_content(
            prompt, 
            generation_config={
                'max_output_tokens': 1024,
                'temperature': 0.7
            },
            safety_settings=safety_settings
        )
        
        if not response.candidates or not response.candidates[0].content.parts:
            return {
                'market_status': '⚠️ AI 응답 생성 실패',
                'key_risks': '안전 필터에 의해 차단되었습니다.',
                'strategy': '다시 시도하세요',
                'full_analysis': '응답이 차단되었습니다.'
            }
            
        text = response.text

        # 섹션 추출
        market_status = extract_section(text, "MARKET_STATUS:")
        key_risks = extract_section(text, "KEY_RISKS:")
        strategy = extract_section(text, "STRATEGY:")
        full_analysis = extract_section(text, "FULL_ANALYSIS:")
        
        return {
            'market_status': market_status or "현재 시장은 복합적인 신호를 보이고 있습니다.",
            'key_risks': key_risks or "• 리스크 분석 중...",
            'strategy': strategy or "신중한 접근이 필요합니다.",
            'full_analysis': full_analysis or text
        }
        
    except Exception as e:
        error_msg = str(e)
        if "quota" in error_msg.lower() or "429" in error_msg:
            return {
                'market_status': '⚠️ API 할당량 초과',
                'key_risks': '잠시 후 다시 시도하세요',
                'strategy': '10-60분 후 재시도',
                'full_analysis': f'⚠️ Gemini API 할당량 초과: {error_msg}'
            }
        return {
            'market_status': '⚠️ 오류 발생',
            'key_risks': f'{error_msg}',
            'strategy': '다시 시도하세요',
            'full_analysis': f'⚠️ 오류: {error_msg}'
        }

def generate_comprehensive_analysis(df, risk_info):
    """종합 AI 분석"""
    if not GEMINI_AVAILABLE:
        return "⚠️ Gemini API가 설정되지 않았습니다."
    
    latest = df.iloc[-1]
    
    prompt = f"""
당신은 거시경제 및 금융시장 전문가입니다. 다음 데이터를 분석하고 한국어로 상세한 인사이트를 제공하세요.

## 현재 금융시장 지표 ({df.index[-1].strftime('%Y-%m-%d')})

### 금리 지표:
- 10년물 국채: {latest['DGS10']:.2f}%
- 2년물 국채: {latest['DGS2']:.2f}%
- 연준 기준금리: {latest['FEDFUNDS']:.2f}%
- 수익률 곡선(10Y-2Y): {latest['YIELD_CURVE']:.2f}%p

### 신용 스프레드:
- 하이일드 스프레드: {latest['HY_SPREAD']:.2f}%
- 투자등급 스프레드: {latest['IG_SPREAD']:.2f}%

### 종합 위험도:
- 위험 수준: {risk_info['level']}
- 리스크 점수: {risk_info['score']}/20

## 분석 요청:
1. **현재 시장 상황 종합 평가** (3-4문장)
2. **주요 리스크 요인** (5-6개 bullet points)
3. **향후 시나리오 분석** (낙관/중립/비관, 각 확률 포함)
4. **투자 전략 제언** (자산배분 및 리스크 관리)

간결하고 실용적으로 작성해주세요.
"""
    
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        response = model.generate_content(
            prompt, 
            generation_config={
                'max_output_tokens': 2048,
                'temperature': 0.7
            },
            safety_settings=safety_settings
        )
        
        if not response.candidates or not response.candidates[0].content.parts:
            return "⚠️ AI 응답이 안전 필터에 의해 차단되었습니다. 다시 시도하세요."
        
        return response.text
        
    except Exception as e:
        error_msg = str(e)
        if "quota" in error_msg.lower() or "429" in error_msg:
            return "⚠️ API 할당량 초과. 잠시 후 다시 시도하세요."
        return f"⚠️ AI 분석 생성 중 오류: {str(e)}"

def generate_indicator_analysis(df, indicator_name, depth="기본"):
    """개별 지표 AI 분석 - 전체 지표 포함"""
    if not GEMINI_AVAILABLE:
        return "⚠️ Gemini API가 설정되지 않았습니다."
    
    latest = df.iloc[-1]
    
    indicator_map = {
        "수익률곡선": ("YIELD_CURVE", "%p", "수익률 곡선 (10Y-2Y)"),
        "10년물금리": ("DGS10", "%", "10년물 국채 금리"),
        "2년물금리": ("DGS2", "%", "2년물 국채 금리"),
        "연준기준금리": ("FEDFUNDS", "%", "연준 기준금리 (FEDFUNDS)"),
        "유효연방기금금리": ("EFFR", "%", "유효 연방기금금리 (EFFR)"),
        "금리괴리": ("RATE_GAP", "%p", "금리 괴리 (10Y - FEDFUNDS)"),
        "정책스프레드": ("POLICY_SPREAD", "%p", "정책 스프레드 (2Y - EFFR)"),
        "하이일드스프레드": ("HY_SPREAD", "%", "하이일드 스프레드"),
        "투자등급스프레드": ("IG_SPREAD", "%", "투자등급 스프레드"),
        "연준총자산": ("WALCL", "B", "연준 총자산 (WALCL)"),
        "신용카드연체율": ("CC_DELINQ", "%", "신용카드 연체율"),
        "소비자연체율": ("CONS_DELINQ", "%", "소비자 대출 연체율"),
        "오토연체율": ("AUTO_DELINQ", "%", "오토론 연체율"),
        "CRE연체율": ("CRE_DELINQ_ALL", "%", "상업용 부동산(CRE) 연체율"),
        "부동산연체율": ("RE_DELINQ_ALL", "%", "부동산 대출 연체율"),
        "CRE대출총액": ("CRE_LOAN_AMT", "B", "CRE 대출 총액")
    }
    
    col, unit, display = indicator_map.get(indicator_name, ("DGS10", "%", indicator_name))
    
    if col not in df.columns:
        return f"⚠️ {display} 데이터가 없습니다."
    
    val_series = df[col].dropna()
    if len(val_series) == 0:
        return f"⚠️ {display} 데이터가 충분하지 않습니다."
    
    val = val_series.iloc[-1]
    
    if len(val_series) >= 7:
        change_7d = ((val_series.iloc[-1] - val_series.iloc[-7]) / val_series.iloc[-7]) * 100
    else:
        change_7d = 0
    
    if len(val_series) >= 30:
        change_30d = ((val_series.iloc[-1] - val_series.iloc[-30]) / val_series.iloc[-30]) * 100
    else:
        change_30d = 0
    
    ma_info = ""
    if f"{col}_MA7" in df.columns:
        ma7 = df[f"{col}_MA7"].dropna().iloc[-1] if len(df[f"{col}_MA7"].dropna()) > 0 else val
        ma30 = df[f"{col}_MA30"].dropna().iloc[-1] if len(df[f"{col}_MA30"].dropna()) > 0 else val
        ma_info = f"\n- MA7: {ma7:.2f}{unit}, MA30: {ma30:.2f}{unit}"
    
    prompt = f"""
{display} 지표를 깊이 분석해주세요. 한국어로 답변하세요.

## 지표 정보:
- 현재 값: {val:.2f}{unit}
- 7일 변화율: {change_7d:+.1f}%
- 30일 변화율: {change_30d:+.1f}%{ma_info}

## 분석 깊이: {depth}
- '요약': 각 항목 1-2문장
- '기본': 각 항목 2-3문장
- '딥다이브': 상세 분석 + bullet points

## 분석 항목:
1. 현재 수준 평가 및 의미
2. 최근 추세 분석 (7일/30일 기준)
3. 경고/위험 레벨 판단
4. 과거 유사 상황과 비교
5. 투자자 관점의 리스크와 기회
6. 주시해야 할 트리거 레벨

위 모드에 맞춰 답변하세요.
"""
    
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        tokens = 2048 if depth == "딥다이브" else 1024
        
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        response = model.generate_content(
            prompt, 
            generation_config={
                'max_output_tokens': tokens,
                'temperature': 0.7
            },
            safety_settings=safety_settings
        )
        
        if not response.candidates or not response.candidates[0].content.parts:
            return "⚠️ AI 응답이 안전 필터에 의해 차단되었습니다. 다시 시도하세요."
        
        return response.text
        
    except Exception as e:
        error_msg = str(e)
        if "quota" in error_msg.lower() or "429" in error_msg:
            return "⚠️ API 할당량 초과. 잠시 후 다시 시도하세요."
        return f"⚠️ 분석 생성 중 오류: {str(e)}"

def generate_chat_response(df, risk_info, user_question, history):
    """챗봇 응답 생성"""
    if not GEMINI_AVAILABLE:
        return "⚠️ Gemini API가 설정되지 않았습니다."
    
    latest = df.iloc[-1]
    
    recent_history = history[-6:] if history else []
    history_text = "\n".join([f"{'사용자' if m['role']=='user' else 'AI'}: {m['content']}" for m in recent_history])
    
    prompt = f"""
당신은 금융시장 전문가입니다. 한국어로 답변하세요.

## 현재 시장 상황:
- 수익률 곡선: {latest['YIELD_CURVE']:.2f}%p
- 하이일드 스프레드: {latest['HY_SPREAD']:.2f}%
- 위험도: {risk_info['level']}

## 이전 대화:
{history_text}

## 사용자 질문:
"{user_question}"

1. 질문 재정리 (1문장)
2. 핵심 답변 (3-6문장)
3. 체크포인트 (필요시 bullet)

투자 권유가 아닌 원칙 중심으로 답변하세요.
"""
    
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        response = model.generate_content(
            prompt, 
            generation_config={
                'max_output_tokens': 1024,
                'temperature': 0.8
            },
            safety_settings=safety_settings
        )
        
        if not response.candidates or not response.candidates[0].content.parts:
            return "⚠️ AI 응답이 안전 필터에 의해 차단되었습니다. 질문을 다시 작성해주세요."
        
        return response.text
        
    except Exception as e:
        error_msg = str(e)
        if "quota" in error_msg.lower() or "429" in error_msg:
            return "⚠️ API 할당량 초과. 잠시 후 다시 시도하세요."
        return f"⚠️ 응답 생성 중 오류: {str(e)}"

# ============================================================
# 7. 차트 생성 함수들
# ============================================================
def plot_macro_risk_dashboard(df, inversion_periods, risk, period_name):
    """5개 패널 메인 대시보드"""
    fig = make_subplots(
        rows=5, cols=1,
        subplot_titles=(
            '🔴 수익률 곡선 (10Y-2Y) & 역전 구간',
            '💧 단·장기 금리 & 기준금리',
            '⚖️ 금리 괴리 (10Y - FEDFUNDS)',
            '🪳 신용 스프레드 (High Yield & IG)',
            '🪳 연체율 (신용카드 / 소비자 / 오토 / CRE)'
        ),
        vertical_spacing=0.06,
        row_heights=[0.22, 0.2, 0.18, 0.18, 0.22]
    )
    
    # 1) 수익률 곡선
    fig.add_trace(
        go.Scatter(x=df.index, y=df['YIELD_CURVE'], name='10Y-2Y',
                   line=dict(color='darkred', width=2.5),
                   fill='tozeroy', fillcolor='rgba(139,0,0,0.15)'),
        row=1, col=1
    )
    fig.add_hline(y=0, line_dash="dash", line_color="black", row=1, col=1)
    for start, end in inversion_periods:
        fig.add_vrect(x0=start, x1=end, fillcolor="rgba(255,0,0,0.25)",
                      layer="below", line_width=0, row=1, col=1)
    
    # 2) 금리
    fig.add_trace(go.Scatter(x=df.index, y=df['DGS10'], name='10Y', line=dict(color='blue', width=2)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['DGS2'], name='2Y', line=dict(color='orange', width=2)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['FEDFUNDS'], name='FFR', line=dict(color='green', width=2)), row=2, col=1)
    
    # 3) 금리 괴리
    fig.add_trace(
        go.Scatter(x=df.index, y=df['RATE_GAP'], name='10Y-FFR',
                   line=dict(color='purple', width=2),
                   fill='tozeroy', fillcolor='rgba(128,0,128,0.1)'),
        row=3, col=1
    )
    
    # 4) 스프레드
    fig.add_trace(go.Scatter(x=df.index, y=df['HY_SPREAD'], name='HY', line=dict(color='red', width=2)), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['IG_SPREAD'], name='IG', line=dict(color='cyan', width=2)), row=4, col=1)
    
    # 5) 연체율
    if 'CC_DELINQ' in df:
        fig.add_trace(go.Scatter(x=df.index, y=df['CC_DELINQ'], name='카드', mode='lines+markers', line=dict(color='red', width=2)), row=5, col=1)
    if 'AUTO_DELINQ' in df:
        fig.add_trace(go.Scatter(x=df.index, y=df['AUTO_DELINQ'], name='오토', mode='lines+markers', line=dict(color='green', width=2)), row=5, col=1)
    if 'CRE_DELINQ_ALL' in df:
        fig.add_trace(go.Scatter(x=df.index, y=df['CRE_DELINQ_ALL'], name='CRE', mode='lines+markers', line=dict(color='brown', width=2)), row=5, col=1)
    
    fig.update_layout(
        height=1800,
        title_text=f"<b>🏦 금융 위험관리 대시보드</b><br><sub>{period_name} | {risk['level']} (점수: {risk['score']}/20)</sub>",
        showlegend=True,
        hovermode='x unified'
    )
    
    return fig

def plot_scenario_analysis(df, period_name):
    """시나리오 분석 차트"""
    fig = make_subplots(
        rows=3, cols=1,
        subplot_titles=('금리 추이', '수익률 곡선', '정책 스프레드'),
        vertical_spacing=0.12,
        row_heights=[0.4, 0.3, 0.3]
    )
    
    # 금리
    fig.add_trace(go.Scatter(x=df.index, y=df['DGS10'], name='10Y', line=dict(color='blue', width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['DGS2'], name='2Y', line=dict(color='orange', width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EFFR'], name='EFFR', line=dict(color='green', width=2)), row=1, col=1)
    
    # 수익률 곡선
    fig.add_trace(
        go.Scatter(x=df.index, y=df['YIELD_CURVE'], name='10Y-2Y',
                   line=dict(color='purple', width=2),
                   fill='tozeroy', fillcolor='rgba(128,0,128,0.1)'),
        row=2, col=1
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)
    
    # 정책 스프레드
    fig.add_trace(
        go.Scatter(x=df.index, y=df['POLICY_SPREAD'], name='2Y-EFFR',
                   line=dict(color='orange', width=2),
                   fill='tozeroy', fillcolor='rgba(255,165,0,0.1)'),
        row=3, col=1
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=3, col=1)
    
    fig.update_layout(
        height=1000,
        title_text=f"<b>금리 스프레드 분석</b><br><sub>{period_name}</sub>",
        showlegend=True,
        hovermode='x unified'
    )
    
    return fig

# ============================================================
# 8. 메인 앱
# ============================================================
def main():
    st.title("📊 통합 금융 위험관리 대시보드")
    st.markdown("---")
    
    # 사이드바 설정
    st.sidebar.header("⚙️ 분석 설정")
    
    period_options = {
        "최근 60일": 60,
        "최근 1년": 365,
        "최근 2년": 730,
        "최근 5년": 1825,
        "2008년 금융위기 이후": "2007-01-01",
        "2000년 이후": "2000-01-01",
        "사용자 정의": "custom"
    }
    
    selected_period = st.sidebar.selectbox("📅 분석 기간", list(period_options.keys()), index=2)
    
    if selected_period == "사용자 정의":
        custom_date = st.sidebar.date_input("시작 날짜", value=datetime.now() - timedelta(days=730))
        start_date = custom_date.strftime('%Y-%m-%d')
        period_name = f"{start_date}부터"
    elif selected_period in ["2008년 금융위기 이후", "2000년 이후"]:
        start_date = period_options[selected_period]
        period_name = selected_period
    else:
        lookback_days = period_options[selected_period]
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
        period_name = selected_period
    
    st.sidebar.success(f"✅ 기간: {period_name}")
    
    if st.sidebar.button("🔄 데이터 새로고침", type="primary"):
        st.cache_data.clear()
        st.rerun()
    
    # 데이터 로드
    try:
        series_dict = load_all_series(start_date)
        df = build_master_df(series_dict)
    except Exception as e:
        st.error(f"❌ 데이터 로드 실패: {str(e)}")
        st.stop()
        return
    
    if df.empty:
        st.error("❌ 데이터가 없습니다.")
        st.stop()
        return
    
    # 분석
    latest = df.iloc[-1]
    inversion_periods = find_inversion_periods(df['YIELD_CURVE'])
    risk = assess_macro_risk(df)
    
    yc = latest['YIELD_CURVE']
    ps = latest['POLICY_SPREAD']
    scenario_num = determine_scenario(yc, ps)
    scenario_info = SCENARIOS[scenario_num]
    
    # 상단 메트릭
    st.markdown("### 📊 핵심 지표")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("10년물 금리", f"{latest['DGS10']:.2f}%")
        st.metric("2년물 금리", f"{latest['DGS2']:.2f}%")
    
    with col2:
        st.metric("수익률 곡선", f"{yc:.2f}%p", 
                  help="10Y-2Y 스프레드. 음수면 역전(침체 신호)")
        st.metric("연준 기준금리", f"{latest['FEDFUNDS']:.2f}%")
    
    with col3:
        st.metric("하이일드 스프레드", f"{latest['HY_SPREAD']:.2f}%")
        st.metric("투자등급 스프레드", f"{latest['IG_SPREAD']:.2f}%")
    
    with col4:
        if not pd.isna(latest.get('CC_DELINQ', np.nan)):
            st.metric("신용카드 연체율", f"{latest['CC_DELINQ']:.2f}%")
        if not pd.isna(latest.get('CRE_DELINQ_ALL', np.nan)):
            st.metric("CRE 연체율", f"{latest['CRE_DELINQ_ALL']:.2f}%")
    
    # 종합 위험도
    st.markdown("---")
    st.markdown("### 🚨 종합 위험도 평가")
    
    risk_color_map = {
        "🔴 CRITICAL RISK": "darkred",
        "🔴 HIGH RISK": "red",
        "🟡 MEDIUM RISK": "orange",
        "🟢 LOW RISK": "green"
    }
    
    st.markdown(
        f"""
        <div style='padding: 20px; border-radius: 10px; background-color: {risk_color_map.get(risk['level'], 'gray')}20; border-left: 5px solid {risk_color_map.get(risk['level'], 'gray')}'>
            <h2>{risk['level']}</h2>
            <p style='font-size: 18px;'><strong>리스크 점수:</strong> {risk['score']}/20</p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    if risk['warnings']:
        st.markdown("**⚠️ 경고 신호:**")
        for w in risk['warnings']:
            st.warning(w)
    
    # 시나리오
    st.markdown("---")
    st.markdown("### 🎯 시장 시나리오")
    
    st.markdown(
        f"""
        <div style='padding: 20px; border-radius: 10px; background-color: {scenario_info['color']}20; border-left: 5px solid {scenario_info['color']}'>
            <h3>{scenario_info['title']}</h3>
            <p><strong>의미:</strong> {scenario_info['meaning']}</p>
            <p><strong>위험도:</strong> {scenario_info['risk']}</p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    with st.expander("📋 자산군별 권장 비중 (참고용)", expanded=False):
        for asset, alloc in scenario_info['assets'].items():
            st.markdown(f"- **{asset}**: {alloc}")
    
    # AI 분석 요약 (메인 대시보드)
    if GEMINI_AVAILABLE:
        st.markdown("---")
        st.markdown("### 🤖 AI 시장 분석 요약")
        
        col_ai1, col_ai2 = st.columns([3, 1])
        
        with col_ai1:
            st.info("💡 Gemini 2.5 Flash가 현재 시장 상황을 분석하여 핵심 인사이트를 제공합니다.")
        
        with col_ai2:
            auto_analysis = st.checkbox("자동 분석", value=False, help="체크하면 페이지 로드 시 자동으로 AI 분석 실행")
        
        if auto_analysis or st.button("🚀 AI 분석 실행", type="primary", key="main_ai_analysis_btn"):
            with st.spinner("🧠 Gemini가 시장을 분석하고 있습니다..."):
                try:
                    analysis_summary = generate_market_summary(df, risk, scenario_info)
                    st.session_state['main_ai_analysis'] = analysis_summary
                except Exception as e:
                    st.error(f"AI 분석 중 오류: {str(e)}")
                    st.session_state['main_ai_analysis'] = {
                        'market_status': '오류 발생',
                        'key_risks': str(e),
                        'strategy': '다시 시도하세요',
                        'full_analysis': f'오류: {str(e)}'
                    }
        
        if 'main_ai_analysis' in st.session_state:
            analysis_data = st.session_state['main_ai_analysis']
            
            st.markdown("#### 📊 AI 분석 결과")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**🎯 현재 시장 상황**")
                market_status = analysis_data.get('market_status', '분석 중...')
                st.info(market_status)
            
            with col2:
                st.markdown("**⚠️ 주요 리스크**")
                key_risks = analysis_data.get('key_risks', '분석 중...')
                st.warning(key_risks)
            
            with col3:
                st.markdown("**💡 투자 전략**")
                strategy = analysis_data.get('strategy', '분석 중...')
                st.success(strategy)
            
            with st.expander("📖 상세 AI 분석 보기", expanded=False):
                full_analysis = analysis_data.get('full_analysis', '')
                st.markdown(full_analysis)
        else:
            st.info("👆 위의 'AI 분석 실행' 버튼을 눌러 Gemini AI 분석을 시작하세요.")
    
    else:
        st.markdown("---")
        st.warning("⚠️ Gemini API가 설정되지 않아 AI 분석 기능을 사용할 수 없습니다. Secrets에 GEMINI_API_KEY를 추가하세요.")
    
    # 메인 차트
    st.markdown("---")
    st.markdown("### 📈 위험관리 대시보드")
    
    try:
        main_chart = plot_macro_risk_dashboard(df, inversion_periods, risk, period_name)
        st.plotly_chart(main_chart, use_container_width=True)
    except Exception as e:
        st.error(f"차트 생성 오류: {str(e)}")
        st.exception(e)
    
    # 탭
    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["📊 시나리오 분석", "🤖 AI 분석 & 챗봇", "📖 해석 가이드"])
    
    with tab1:
        st.markdown("### 금리 스프레드 분석")
        
        try:
            scenario_chart = plot_scenario_analysis(df, period_name)
            st.plotly_chart(scenario_chart, use_container_width=True)
        except Exception as e:
            st.error(f"시나리오 차트 오류: {str(e)}")
        
        # 시나리오 통계
        df['Scenario'] = df.apply(lambda row: determine_scenario(row['YIELD_CURVE'], row['POLICY_SPREAD']), axis=1)
        
        st.markdown("### 시나리오 분포")
        scenario_counts = df['Scenario'].value_counts().sort_index()
        
        for sn in [1, 2, 3, 4]:
            count = scenario_counts.get(sn, 0)
            pct = (count / len(df)) * 100 if len(df) > 0 else 0
            st.progress(pct / 100, text=f"{SCENARIOS[sn]['title']}: {count}일 ({pct:.1f}%)")
    
    with tab2:
        st.markdown("### 🤖 AI 분석")
        
        analysis_mode = st.radio("분석 모드", ["종합 분석", "개별 지표 분석"], horizontal=True)
        
        if analysis_mode == "종합 분석":
            if st.button("🚀 종합 AI 분석 실행", type="primary"):
                with st.spinner("🧠 Gemini 분석 중..."):
                    try:
                        analysis = generate_comprehensive_analysis(df, risk)
                        st.session_state['comprehensive'] = analysis
                    except Exception as e:
                        st.error(f"분석 중 오류: {str(e)}")
            
            if 'comprehensive' in st.session_state:
                st.markdown(st.session_state['comprehensive'])
                st.download_button(
                    "📥 분석 다운로드",
                    st.session_state['comprehensive'],
                    f"comprehensive_{datetime.now().strftime('%Y%m%d')}.md",
                    "text/markdown"
                )
        
        else:
            st.markdown("#### 분석할 지표를 선택하세요")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📊 지표 카테고리**")
                indicator_category = st.radio(
                    "카테고리",
                    ["금리", "스프레드", "연체율", "기타"],
                    horizontal=False,
                    label_visibility="collapsed"
                )
            
            with col2:
                if indicator_category == "금리":
                    indicator = st.selectbox(
                        "세부 지표",
                        ["수익률곡선", "10년물금리", "2년물금리", "연준기준금리", "유효연방기금금리"]
                    )
                elif indicator_category == "스프레드":
                    indicator = st.selectbox(
                        "세부 지표",
                        ["금리괴리", "정책스프레드", "하이일드스프레드", "투자등급스프레드"]
                    )
                elif indicator_category == "연체율":
                    indicator = st.selectbox(
                        "세부 지표",
                        ["신용카드연체율", "소비자연체율", "오토연체율", "CRE연체율", "부동산연체율"]
                    )
                else:
                    indicator = st.selectbox(
                        "세부 지표",
                        ["연준총자산", "CRE대출총액"]
                    )
            
            depth = st.select_slider("분석 깊이", ["요약", "기본", "딥다이브"], value="기본")
            
            if st.button("🔍 지표 분석 실행", type="primary"):
                with st.spinner(f"🧠 {indicator} 분석 중..."):
                    try:
                        analysis = generate_indicator_analysis(df, indicator, depth)
                        st.session_state['indicator'] = analysis
                        st.session_state['indicator_name'] = indicator
                    except Exception as e:
                        st.error(f"분석 중 오류: {str(e)}")
            
            if 'indicator' in st.session_state:
                st.markdown(st.session_state['indicator'])
                st.download_button(
                    "📥 개별 분석 다운로드",
                    st.session_state['indicator'],
                    f"{st.session_state.get('indicator_name', 'indicator')}_{datetime.now().strftime('%Y%m%d')}.md",
                    "text/markdown"
                )
        
        # 챗봇
        st.markdown("---")
        st.markdown("### 💬 AI 챗봇")
        
        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = []
        
        if st.session_state["chat_history"]:
            for msg in st.session_state["chat_history"]:
                if msg["role"] == "user":
                    st.markdown(f"**👤 사용자:** {msg['content']}")
                else:
                    st.markdown(f"**🤖 AI:** {msg['content']}")
        
        col_chat1, col_chat2 = st.columns([4, 1])
        with col_chat1:
            user_question = st.text_area(
                "질문 입력",
                key="chat_input",
                placeholder="예: 현재 시장 상황에서 채권과 주식 중 어느 쪽이 유리한가요?",
                height=80
            )
        with col_chat2:
            st.write("")
            st.write("")
            send_btn = st.button("전송", type="primary")
        
        if st.button("대화 초기화"):
            st.session_state["chat_history"] = []
            st.rerun()
        
        if send_btn and user_question.strip():
            st.session_state["chat_history"].append({"role": "user", "content": user_question.strip()})
            
            with st.spinner("🤖 AI 응답 생성 중..."):
                try:
                    answer = generate_chat_response(df, risk, user_question.strip(), st.session_state["chat_history"])
                    st.session_state["chat_history"].append({"role": "assistant", "content": answer})
                except Exception as e:
                    error_msg = f"⚠️ 응답 생성 중 오류: {str(e)}"
                    st.session_state["chat_history"].append({"role": "assistant", "content": error_msg})
            
            st.rerun()
    
    with tab3:
        st.markdown("""
        ### 📖 지표 해석 가이드 (완전판)
        
        ---
        
        ## 📊 금리 지표
        
        ### 1. 수익률 곡선 (10Y-2Y)
        - **역전 (<0)**: 🔴 경기침체 전조 신호. 역사적으로 거의 모든 침체 전 발생
        - **평탄화 (0-0.5)**: 🟡 침체 우려 증가. 역전 임박 가능성
        - **정상 (>0.5)**: 🟢 건강한 경기 상태. 성장 기대 반영
        
        ### 2. 10년물 국채 금리 (DGS10)
        - **>5%**: 🔴 매우 높은 금리. 차입 비용 급등
        - **4-5%**: 🟡 긴축 국면. 성장 압박
        - **3-4%**: ➡️ 중립 구간
        - **<3%**: 🟢 완화적 환경
        
        ### 3. 2년물 국채 금리 (DGS2)
        - **단기 정책 기대 반영**
        - 연준 금리 인상/인하 기대가 직접 반영됨
        - 10년물과의 차이가 수익률 곡선
        
        ### 4. 연준 기준금리 (FEDFUNDS)
        - **>5%**: 🔴 강력한 긴축. 인플레이션 억제 최우선
        - **3-5%**: 🟡 긴축 구간. 경기 둔화 리스크
        - **1-3%**: ➡️ 중립~완화
        - **<1%**: 🟢 초완화. 경기 부양 모드
        
        ### 5. 유효 연방기금금리 (EFFR)
        - 실제 은행 간 거래되는 금리
        - FEDFUNDS의 실제 시장 반영 값
        - 2Y금리와의 차이가 정책 스프레드
        
        ---
        
        ## 📈 스프레드 지표
        
        ### 6. 금리 괴리 (10Y - FEDFUNDS)
        - **>1.5%p**: 🟢 정상적 차이
        - **0.5-1.5%p**: ➡️ 평탄화 진행
        - **<0.5%p**: 🟡 과도한 긴축 우려
        - **음수**: 🔴 역전 상태 (드물지만 심각)
        
        ### 7. 정책 스프레드 (2Y - EFFR)
        - **양수**: 시장이 금리 인상 예상
        - **음수**: 시장이 금리 인하 예상 (완화 기대)
        - 정책 전환점 예측에 핵심 지표
        
        ### 8. 하이일드 스프레드
        - **>7%**: 🔴 위기 수준. 신용 경색
        - **5-7%**: 🟡 높은 신용 리스크
        - **3-5%**: ➡️ 보통
        - **<3%**: 🟢 안정적. 과열 주의
        
        ### 9. 투자등급 스프레드
        - **>2.5%**: 🔴 우량 기업도 부담
        - **1.5-2.5%**: 🟡 스트레스 증가
        - **<1.5%**: 🟢 안정적
        
        ---
        
        ## 🏦 연준 지표
        
        ### 10. 연준 총자산 (WALCL)
        - **증가 추세**: 양적완화(QE). 유동성 공급
        - **감소 추세**: 양적긴축(QT). 유동성 회수
        - **급격한 변화**: 정책 전환 신호
        
        ---
        
        ## 🪳 연체율 지표
        
        ### 11. 신용카드 연체율
        - **>5%**: 🔴 위기 수준. 소비자 스트레스 극심
        - **3.5-5%**: 🟡 급등 구간. 주의 필요
        - **2.5-3.5%**: ➡️ 상승세
        - **<2.5%**: 🟢 양호
        
        ### 12. 소비자 대출 연체율
        - **>2.5%**: 🔴 높은 수준
        - **1.5-2.5%**: 🟡 상승 구간
        - **<1.5%**: 🟢 안정적
        
        ### 13. 오토론 연체율
        - **>3%**: 🔴 저소득층 압박 심각
        - **2.5-3%**: 🟡 상승세
        - **<2.5%**: 🟢 양호
        
        ### 14. CRE 연체율 (상업용 부동산)
        - **>5%**: 🔴 위기. 은행 손실 확대
        - **3-5%**: 🟡 부동산 침체
        - **<3%**: 🟢 안정적
        
        ### 15. 부동산 대출 연체율
        - 전체 부동산 시장 건강도
        - CRE + 주택담보대출 종합
        
        ### 16. CRE 대출 총액
        - **증가**: 부동산 시장 활성화
        - **감소**: 은행 리스크 회피. 시장 위축
        
        ---
        
        ## 🎯 시나리오별 대응 전략
        
        ### 시나리오 1: 🟡 스태그플레이션
        - **특징**: 수익률 곡선 역전 + 긴축 기대
        - **의미**: 인플레이션 지속 + 성장 둔화
        - **전략**: 
          - 성장주 축소 (20-30%)
          - 가치주 유지 (30-40%)
          - 원자재/금 확대 (15-20%)
          - 현금 비중 확대 (10-20%)
        
        ### 시나리오 2: 🚨 침체 경고
        - **특징**: 수익률 곡선 역전 + 완화 기대
        - **의미**: 경기 침체 임박
        - **전략**:
          - 성장주 최소화 (0-10%)
          - 장기 국채 확대 (40-50%)
          - 금/방어자산 핵심 (20-30%)
          - 현금 확보 (20-30%)
        
        ### 시나리오 3: ✅ 건강한 성장
        - **특징**: 정상 수익률 곡선 + 긴축 기대
        - **의미**: 건강한 성장 + 인플레이션 관리
        - **전략**:
          - 성장주 공격적 (40-50%)
          - 기술주 확대 (25-35%)
          - 채권 최소화 (5-10%)
        
        ### 시나리오 4: 🔄 정책 전환점
        - **특징**: 정상 곡선 + 완화 기대
        - **의미**: 긴축 종료. 피벗 기대
        - **전략**:
          - 균형 포트폴리오
          - 장기채 확대 (20-30%)
          - 부동산/리츠 매수 (15-20%)
          - 비트코인 점진 확대 (10-15%)
        
        ---
        
        ## ⚠️ 주의사항
        
        1. **본 가이드는 투자 권유가 아닙니다**
        2. **개인 상황에 맞는 조정 필요**
        3. **전문가 상담 권장**
        4. **지표는 후행성을 가질 수 있음**
        5. **복합적 판단 필요 (단일 지표만 의존 금지)**
        
        ---
        
        ## 📚 추가 학습 자료
        
        - **FRED 공식 문서**: https://fred.stlouisfed.org/
        - **연준 통화정책**: https://www.federalreserve.gov/
        - **수익률 곡선 역전 역사**: 과거 모든 침체 전 발생 (단, 시차 존재)
        """)
    
    # 데이터 다운로드
    st.markdown("---")
    st.markdown("### 💾 데이터 다운로드")
    
    csv_data = df.to_csv()
    st.download_button(
        "📊 전체 데이터 다운로드 (CSV)",
        csv_data,
        f"macro_data_{datetime.now().strftime('%Y%m%d')}.csv",
        "text/csv"
    )
    
    # 푸터
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: gray; padding: 20px;'>
            <p>📊 통합 금융 위험관리 대시보드 v1.0</p>
            <p>데이터 출처: FRED | AI: Gemini 2.5 Flash</p>
            <p>⚠️ 본 분석은 투자 권유가 아니며 참고 목적입니다.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
