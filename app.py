import os
import streamlit as st
from utils import extract_text_from_uploaded_file
import openai

# .env 파일 로드 (옵션)
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

# OpenAI API 키 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    try:
        OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY")
    except:
        OPENAI_API_KEY = None

st.set_page_config(page_title="Check Mate", page_icon="🧠", layout="wide")
st.title("Check Mate — 수행평가 초안 검사")

if not OPENAI_API_KEY:
    st.warning("OPENAI_API_KEY 환경변수가 설정되어 있지 않습니다. .env 또는 Streamlit Secrets에 설정하세요.")

with st.expander("도움말 / 사용법", expanded=True):
    st.markdown("""
    1. 수행평가 요구조건을 입력하거나 예시를 선택하세요.
    2. 결과물(텍스트 또는 파일)을 입력하세요.
    3. '검사 시작'을 누르면 오른쪽에 항목별 검사 보고서가 표시됩니다.
    """)

# -------------------------------
# ✅ 예시 목록
# -------------------------------

examples = {
    "직접 입력": {
        "requirements": "",
        "submission": ""
    },
    "예시 1: 스마트폰 사용 제한": {
        "requirements": """- 주제 문장을 명확히 제시할 것
- 서론, 본론, 결론의 구조를 갖출 것
- 논리적인 근거를 제시할 것
- 500자 이상 작성할 것
- 맞춤법과 문법이 정확할 것""",
        "submission": """스마트폰은 좋기도 하고 나쁘기도 하다. 사람들이 너무 많이 쓰면 집중이 안 된다. 그래서 적당히 써야 한다. 부모님이 말려야 한다."""
    },
    "예시 2: 독서의 중요성": {
        "requirements": """- 주제를 명확하게 설명할 것
- 독서와 관련된 실제 경험을 포함할 것
- 400자 이상 작성할 것
- 글의 흐름이 자연스러울 것""",
        "submission": """나는 책을 좋아한다. 책을 읽으면 기분이 좋다. 학교에서 책 읽는 시간을 늘리면 좋겠다."""
    },
    "예시 3: 환경 보호의 필요성": {
        "requirements": """- 환경 문제 중 하나를 선택하여 설명할 것
- 구체적인 해결 방안을 제시할 것
- 500자 이상 작성할 것
- 논리적인 구조를 따를 것""",
        "submission": """요즘 환경이 안 좋아지고 있다. 쓰레기도 많고 더럽다. 사람들이 덜 버려야 한다."""
    },
    "예시 4: 나의 꿈": {
        "requirements": """- 자신의 꿈에 대해 구체적으로 설명할 것
- 꿈을 이루기 위한 계획을 포함할 것
- 450자 이상 작성할 것
- 긍정적인 태도가 드러나야 함""",
        "submission": """나는 커서 선생님이 되고 싶다. 아이들을 좋아하고 가르치는 것도 좋다. 열심히 노력하면 될 것이다."""
    }
}

# -------------------------------
# 좌/우 컬럼 레이아웃
# -------------------------------

left_col, right_col = st.columns([1, 1])

with left_col:
    st.header("입력")

    # ✅ 예시 선택
    selected_example = st.selectbox("예시 선택", list(examples.keys()))

    requirements_text = st.text_area(
        "요구조건 (항목별로 줄바꿈)",
        height=200,
        value=examples[selected_example]["requirements"]
    )

    uploaded_file = st.file_uploader("제출물 파일 업로드 (txt, pdf, docx 등)")

    submission_text = st.text_area(
        "결과물 텍스트",
        height=300,
        value=examples[selected_example]["submission"]
    )

    if uploaded_file and not submission_text:
        with st.spinner("파일에서 텍스트 추출 중..."):
            submission_text = extract_text_from_uploaded_file(uploaded_file)

    run_check = st.button("검사 시작")

with right_col:
    st.header("검사 보고서")
    report_placeholder = st.empty()

# -------------------------------
# 🔍 검사 로직
# -------------------------------

def summarize_match(requirements, submission_text, openai_api_key):
    openai.api_key = openai_api_key

    prompt = f"""
당신은 학생의 글을 평가하는 첨삭 도우미입니다.

다음은 학생이 작성한 수행평가 결과물입니다:

--- 결과물 ---
{submission_text}
---------------

요구조건 목록:
{chr(10).join(f"- {r}" for r in requirements)}

각 요구조건마다 아래 형식에 따라 평가해주세요:

형식 예시:
- ✅ **요구조건**: 충족함 — 간단한 이유 설명
- ❌ **요구조건**: 부족함 — 부족한 이유 설명

결과를 체크리스트 형태로 작성해주세요.
"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )

    return response.choices[0].message.content.strip()


if run_check:
    if not requirements_text.strip():
        with right_col:
            st.error("요구조건을 입력하거나 예시를 선택하세요.")
    elif not submission_text.strip():
        with right_col:
            st.error("결과물을 입력하거나 파일을 업로드하세요.")
    else:
        requirements = [r.strip() for r in requirements_text.splitlines() if r.strip()]
        with st.spinner("AI 검사 중..."):
            report = summarize_match(requirements, submission_text, OPENAI_API_KEY)
        report_placeholder.markdown(report)

