import os
import streamlit as st
from openai import OpenAI
from utils import extract_text_from_uploaded_file

# ==============================
# 초기 설정
# ==============================
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

API_KEY = os.getenv("OPENAI_API_KEY", st.secrets.get("OPENAI_API_KEY", None))
if not API_KEY:
    st.error("❌ OpenAI API 키가 설정되지 않았습니다.")
    st.stop()

client = OpenAI(api_key=API_KEY)

# ==============================
# Streamlit UI
# ==============================
st.set_page_config(page_title="Check Mate - 자동 수행평가 첨삭기", layout="wide")
st.title("🧠 Check Mate - 수행평가 자동 평가 및 첨삭 도우미")

st.markdown("""
**Check Mate**는 수행평가 초안이 제시된 요구조건에 얼마나 부합하는지 AI가 자동으로 평가하고, 
사실성 검증과 문장 첨삭까지 수행합니다.

- ✅ 조건 충족
- ❌ 조건 불충족 (사실 오류 포함)
- ⚠️ 일부 부족 또는 문장 오류
""")

# 좌우 레이아웃
left, right = st.columns([1, 1])

# ==============================
# 왼쪽: 입력 영역
# ==============================
with left:
    st.header("📋 수행평가 요구조건 입력")
    conditions = st.text_area(
        "조건을 한 줄씩 입력하세요:",
        placeholder="예: 1. 글자 수 800~1200자\n2. 대륙이동설 제안자 언급\n3. 과학적 근거 포함"
    )

    st.header("📝 학생 제출물 입력")
    text_input_method = st.radio("입력 방식", ["직접 입력", "파일 업로드"])

    student_text = ""
    if text_input_method == "직접 입력":
        student_text = st.text_area("학생 글 입력", height=250)
    else:
        uploaded = st.file_uploader("파일 업로드 (.txt, .pdf, .docx)")
        if uploaded:
            student_text = extract_text_from_uploaded_file(uploaded)
            st.success("✅ 파일 업로드 성공")
            with st.expander("📄 텍스트 미리보기"):
                st.write(student_text[:1000])

    if st.button("✳️ AI 자동 평가 및 첨삭 실행"):
        if not conditions or not student_text:
            st.warning("⚠️ 조건과 학생 글을 모두 입력해주세요.")
        else:
            with st.spinner("AI가 평가 중입니다..."):
                prompt = f"""
                너는 수행평가 전문 AI 채점관이야.

                아래 요구조건과 학생 글을 보고 다음을 수행해:
                1. 각 조건 충족 여부 판단 (✅ 충족, ❌ 사실 오류 포함 불충족, ⚠️ 일부 부족)
                2. 사실 오류, 명칭 오류, 개념 오류가 있으면 자동으로 ❌ 처리
                3. 문법, 표현, 구조 등을 자동 첨삭 (원문 의미 최대한 유지)
                4. 조건별 평가와 이유, 첨삭 문장 제안 포함
                5. 최종 점수 및 간략 총평 제공 (100점 만점)

                [조건 목록]
                {conditions}

                [학생 글]
                {student_text}
                """

                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "너는 수행평가 채점과 첨삭 전문가 AI야."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3
                )

                result = response.choices[0].message.content
                st.session_state['evaluation_result'] = result

# ==============================
# 오른쪽: 결과 영역
# ==============================
with right:
    st.header("📊 평가 및 첨삭 결과")
    if 'evaluation_result' in st.session_state:
        st.markdown(st.session_state['evaluation_result'])
    else:
        st.info("왼쪽에서 조건과 학생 글 입력 후 버튼을 눌러주세요.")

# ==============================
# 하단: 평가 예시
# ==============================
st.markdown("---")
st.header("🧩 평가 예시")
with st.expander("예시 1"):
    st.markdown("""
**조건**
1. 글자 수 800~1200자
2. 대륙이동설 제안자 언급
3. 과학적 근거 포함

**학생 글**
베게너는 대륙이 이동한다고 주장했다. 후에 해령과 판 구조론으로 증명되었다.

**평가 예시**
1. 글자 수 → ⚠️ 일부 부족
2. 제안자 언급 → ✅ 충족
3. 근거 제시 → ✅ 충족

총점: 85점 / 총평: 일부 조건 부족 있으나 과학적 타당성은 높음.
""")
with st.expander("예시 2"):
    st.markdown("""
**조건**
1. 세종대왕 업적 2가지 이상 언급
2. 사회적 의미 서술

**학생 글**
세종대왕은 훈민정음을 창제하고 측우기를 만들었다.

**평가 예시**
1. 업적 언급 → ✅ 충족
2. 사회적 의미 → ❌ 사실 오류 (측우기는 장영실 제작)

총점: 80점 / 총평: 일부 사실 오류 존재.
""")
with st.expander("예시 3"):
    st.markdown("""
**조건**
1. 실험 과정 정확 제시
2. 결과 원인 분석

**학생 글**
온도에 따라 용해도 변화를 관찰했으나 순서 불명확.

**평가 예시**
1. 실험 순서 → ❌ 부족
2. 결과 분석 → ✅ 충족

총점: 75점 / 총평: 분석력은 우수하지만 절차 구체성 부족.
""")

