
import os
import streamlit as st
from utils import extract_text_from_uploaded_file

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

# OpenAI API Key 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    try:
        OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    except:
        OPENAI_API_KEY = None

# 페이지 설정
st.set_page_config(page_title="Check Mate — 수행평가 검사", page_icon="🧠", layout="wide")
st.markdown("<h1 style='text-align: center;'>🧠 Check Mate — 수행평가 초안 검사 도우미</h1>", unsafe_allow_html=True)

# API 키 확인
if not OPENAI_API_KEY:
    st.warning("❗ OPENAI_API_KEY가 설정되지 않았습니다. .env 또는 Streamlit Secrets에서 설정하세요.")

# 사용법
with st.expander("📘 사용법 안내", expanded=True):
    st.markdown("""
    1. **수행평가 요구조건**을 입력하거나 예시를 선택하세요.  
    2. **결과물**을 직접 입력하거나 파일로 업로드하세요.  
    3. ✅ **검사 시작**을 누르면, 오른쪽에 조건별 평가와 피드백이 표시됩니다.
    """)

# 예시 입력
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

# 좌/우 컬럼 구성
left_col, right_col = st.columns([1, 1])

with left_col:
    st.header("✍️ 입력")

    selected_example = st.selectbox("📂 예시 선택", list(examples.keys()))
    requirements_text = st.text_area("📌 요구조건 (줄바꿈으로 구분)", height=180, value=examples[selected_example]["requirements"])
    uploaded_file = st.file_uploader("📎 제출물 파일 업로드 (txt, pdf, docx)")
    submission_text = st.text_area("📄 결과물 텍스트", height=250, value=examples[selected_example]["submission"])

    if uploaded_file and not submission_text:
        with st.spinner("파일에서 텍스트 추출 중..."):
            submission_text = extract_text_from_uploaded_file(uploaded_file)

    run_check = st.button("✅ 검사 시작")

with right_col:
    st.header("📋 검사 결과")
    report_placeholder = st.empty()

# AI 평가 함수
def summarize_match(requirements, submission_text, openai_api_key):
    from openai import OpenAI
    client = OpenAI(api_key=openai_api_key)

    prompt = f"""
너는 수행평가 글을 평가하는 첨삭 전문가입니다.

다음은 학생이 작성한 글과 수행평가 요구조건입니다:

📄 학생의 글:
{submission_text}

📌 요구조건:
{chr(10).join(f"- {r}" for r in requirements)}

---

💡 아래 기준으로 각 조건을 평가하세요:

1. 해당 조건을 충족했는지 (✅ 충족 / ❌ 부족)
2. 글의 표현이 명확하고 논리적인지
3. 사실과 맞지 않는 주장이나 정보가 있는지 (명칭 오류, 잘못된 정보 포함)
4. 용어나 개념이 틀리거나 부정확하게 사용된 부분은 없는지
5. 개선이 필요한 경우, 어떻게 수정하면 좋을지 조언

---

📝 결과 출력 형식 (Markdown 체크리스트):

- ✅ **[요구조건]**: 충족 — [간단한 이유]
- ❌ **[요구조건]**: 부족 — [부족한 이유 설명]
- ⚠️ **사실 오류 또는 용어 오류**: "[문장 또는 용어]" → 올바른 표현 또는 오류 설명

가능한 한 명확하고 객관적인 피드백을 작성하세요.
"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.4
    )

    return response.choices[0].message.content.strip()

# 검사 실행
if run_check:
    if not requirements_text.strip():
        right_col.error("❗ 요구조건을 입력해주세요.")
    elif not submission_text.strip():
        right_col.error("❗ 결과물을 입력하거나 파일을 업로드해주세요.")
    else:
        requirements = [r.strip() for r in requirements_text.splitlines() if r.strip()]
        with st.spinner("AI가 글을 평가 중입니다..."):
            try:
                report = summarize_match(requirements, submission_text, OPENAI_API_KEY)
                report_placeholder.markdown(report)
            except Exception as e:
                st.error(f"❌ 오류 발생: {e}")
