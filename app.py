import os
import streamlit as st
from utils import extract_text_from_uploaded_file, summarize_match

# .env 파일이 있으면 로드 (선택적)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # python-dotenv가 없으면 넘어감
    pass

# 환경변수에서 OpenAI API 키 로드 (로컬: .env or env var, 배포: Streamlit secrets)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    # Streamlit Cloud에선 st.secrets에 값을 넣어 사용합니다.
    try:
        OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        # st.secrets가 없거나 접근 불가하면 무시
        OPENAI_API_KEY = None

st.set_page_config(page_title="Check Mate", page_icon="🧠", layout="wide")

st.title("Check Mate — 수행평가 초안 검사")

if not OPENAI_API_KEY:
    st.warning("OPENAI_API_KEY 환경변수가 설정되어 있지 않습니다. 로컬에서 실행하려면 설정하세요.")

with st.expander("도움말 / 사용법", expanded=True):
    st.write("""
    1. 수행평가 요구조건을 입력하세요 (리스트 형식 권장).
    2. 결과물(텍스트 또는 파일)을 업로드하거나 텍스트 박스에 붙여넣으세요.
    3. '검사 시작'을 누르면 오른쪽 패널에 항목별 검사 보고서가 표시됩니다.
    """)

# 좌우 컬럼 생성: 왼쪽 입력, 오른쪽 보고서
left_col, right_col = st.columns([1, 1])

with left_col:
    st.header("입력")
    requirements_text = st.text_area("요구조건 (항목별로 줄바꿈)", height=220)

    uploaded_file = st.file_uploader("제출물 파일 업로드 (txt, pdf, docx 등)")
    submission_text = st.text_area("결과물 텍스트", height=300)



    if uploaded_file is not None and not submission_text:
        with st.spinner("파일에서 텍스트 추출 중..."):
            submission_text = extract_text_from_uploaded_file(uploaded_file)

    run_check = st.button("검사 시작")

with right_col:
    st.header("검사 보고서")
    report_placeholder = st.empty()

if run_check:
    if not requirements_text.strip():
        with right_col:
            st.error("요구조건을 입력하세요.")
    elif not submission_text.strip():
        with right_col:
            st.error("결과물을 입력하거나 파일을 업로드하세요.")
    else:
        requirements = [r.strip() for r in requirements_text.splitlines() if r.strip()]
        with st.spinner("AI 검사 중... 잠시만 기다려주세요."):
            report = summarize_match(requirements, submission_text, OPENAI_API_KEY)
        report_placeholder.markdown(report)
