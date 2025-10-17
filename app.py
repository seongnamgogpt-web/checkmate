
import os
import streamlit as st
from openai import OpenAI
from utils import extract_text_from_uploaded_file

# ============================================================
#  🧠 Check Mate: 수행평가 자동 평가 & 첨삭 시스템
#  Version: Final Release
#  Author: GPT-5 (World-Class Developer)
# ============================================================

# -----------------------------
# 1️⃣ 환경 변수 설정
# -----------------------------
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

# -----------------------------
# 2️⃣ 페이지 설정 및 제목
# -----------------------------
st.set_page_config(
    page_title="Check Mate - 수행평가 자동 평가 시스템",
    page_icon="🧠",
    layout="wide"
)

st.markdown(
    """
    <style>
    body { font-family: 'Pretendard', sans-serif; }
    .main-title { text-align:center; font-size: 42px; font-weight:700; color:#2F80ED; margin-top:-20px; }
    .sub-title { text-align:center; font-size:18px; color:#4F4F4F; margin-bottom:40px; }
    .section-header { font-size:22px; font-weight:600; color:#333; margin-top:20px; }
    .note { color:#888; font-size:13px; }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown("<p class='main-title'>🧠 Check Mate</p>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>AI 기반 수행평가 조건 검증 · 사실 오류 감지 · 자동 첨삭 플랫폼</p>", unsafe_allow_html=True)

st.divider()

# -----------------------------
# 3️⃣ 좌우 레이아웃
# -----------------------------
left, right = st.columns([1, 1])

# -----------------------------
# 4️⃣ 입력 영역 (왼쪽)
# -----------------------------
with left:
    st.markdown("<p class='section-header'>📋 수행평가 조건 입력</p>", unsafe_allow_html=True)
    conditions = st.text_area(
        "수행평가 조건을 한 줄씩 입력하세요:",
        placeholder="예: 1. 베게너의 대륙이동설을 언급한다\n2. 과학적 근거를 제시한다\n3. 글자 수 800자 이상 작성한다",
        height=180
    )

    st.markdown("<p class='section-header'>🧾 학생 글 입력</p>", unsafe_allow_html=True)
    input_method = st.radio("입력 방법 선택", ["직접 입력", "파일 업로드"])

    student_text = ""
    if input_method == "직접 입력":
        student_text = st.text_area("학생 글을 입력하세요", height=280)
    else:
        uploaded_file = st.file_uploader("파일 업로드 (.txt, .pdf, .docx)")
        if uploaded_file:
            student_text = extract_text_from_uploaded_file(uploaded_file)
            st.success("✅ 파일 업로드 성공")
            with st.expander("📄 업로드된 글 미리보기"):
                st.write(student_text[:1000])

    st.markdown("<p class='section-header'>⚙️ 검사 강도 설정</p>", unsafe_allow_html=True)
    level = st.select_slider(
        "검사 수준 (1=관대 / 2=보통 / 3=엄격)",
        options=[1, 2, 3],
        value=2
    )

    st.markdown("<p class='note'>※ 검사 강도가 높을수록 사실/명칭 오류와 조건 미충족을 더 엄격히 판단합니다.</p>", unsafe_allow_html=True)

    # 평가 실행 버튼
    run_evaluation = st.button("🚀 AI 평가 시작")

# -----------------------------
# 5️⃣ 평가 실행 로직
# -----------------------------
if run_evaluation:
    if not conditions.strip() or not student_text.strip():
        st.warning("⚠️ 조건과 학생 글을 모두 입력하세요.")
        st.stop()

    with st.spinner("AI가 글을 분석 중입니다... 잠시만 기다려주세요."):

        # 🔹 프롬프트 설계: 프롬프트 엔지니어링 원칙 기반
        prompt = f"""
        너는 수행평가 첨삭 및 평가 전문가 AI이자, 
        사실 검증 능력을 갖춘 교육 평가 모델이야.

        목표:
        - 학생의 글이 주어진 조건을 얼마나 충족하는지 조건별로 평가.
        - 각 조건에 대해 사실, 명칭, 개념, 논리, 문법을 모두 점검.
        - 검사 수준({level})에 따라 평가 기준을 조정.

        [검사 수준 설명]
        - 1단계(관대): 조건 일부라도 언급되면 ⚠️, 명백한 오류만 ❌
        - 2단계(보통): 조건 불완전/모호 시 ⚠️, 틀린 사실/명칭은 ❌
        - 3단계(엄격): 조건 완전 일치만 ✅, 근거 불명확·명칭 틀림·논리 불완전은 ❌

        [평가 방식]
        1️⃣ 각 조건을 해석하고 학생 글에서 관련 내용 확인.
        2️⃣ 해당 내용의 사실/명칭/개념/논리 오류 판단.
        3️⃣ 조건별로 ✅(충족), ⚠️(부분 충족·불명확), ❌(불충족·오류) 판정.
        4️⃣ 각 조건마다 '이유'와 '수정 제안' 작성.
        5️⃣ 마지막에 총평(3줄 이내) 작성.

        [출력 형식: 반드시 아래 표 형식으로 출력]
        | 조건 | 판정 | 이유 | 수정 제안 |
        |------|------|------|------------|
        | 조건1 내용 | ✅ / ⚠️ / ❌ | ... | ... |
        | 조건2 내용 | ✅ / ⚠️ / ❌ | ... | ... |
        ...
        **총평:** ...

        [조건 목록]
        {conditions}

        [학생 글]
        {student_text}
        """

        # 🔸 ChatGPT API 호출
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "너는 수행평가 첨삭 및 평가 전문가야."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.25
        )

        result = response.choices[0].message.content.strip()
        st.session_state["evaluation_result"] = result

# -----------------------------
# 6️⃣ 결과 표시 (오른쪽)
# -----------------------------
with right:
    st.markdown("<p class='section-header'>📊 조건별 평가 결과</p>", unsafe_allow_html=True)

    if "evaluation_result" in st.session_state:
        st.markdown(
            """
            <style>
            table {
                width:100%;
                border-collapse: collapse;
                margin-bottom: 20px;
            }
            th, td {
                border: 1px solid #ccc;
                padding: 10px;
                text-align: left;
                font-size: 15px;
            }
            th {
                background-color: #f7f9fb;
                font-weight: 700;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
        st.markdown(st.session_state["evaluation_result"], unsafe_allow_html=True)

        # 자동 수정 버튼
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("<p class='section-header'>🔧 조건 기반 자동 수정</p>", unsafe_allow_html=True)
        if st.button("AI가 자동으로 글 수정하기 ✨"):
            with st.spinner("AI가 조건에 맞게 글을 수정 중입니다..."):
                correction_prompt = f"""
                너는 수행평가 글쓰기 첨삭 전문가야.
                아래 학생의 글을 교사가 제시한 조건에 최대한 부합하도록 수정하되,
                학생의 표현 스타일과 문체는 유지하라.
                틀린 명칭이나 사실은 반드시 교정하고, 논리적 연결이 자연스럽게 이어지게 만들어라.

                [조건 목록]
                {conditions}

                [원문]
                {student_text}
                """

                correction = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "너는 글쓰기 및 첨삭 전문가야."},
                        {"role": "user", "content": correction_prompt}
                    ],
                    temperature=0.35
                )

                corrected_text = correction.choices[0].message.content.strip()
                st.markdown("### ✨ 수정된 글 제안")
                st.write(corrected_text)
                st.download_button(
                    "💾 수정된 글 다운로드",
                    corrected_text,
                    file_name="corrected_text.txt",
                    mime="text/plain"
                )
    else:
        st.info("왼쪽에서 조건과 학생 글을 입력 후 [AI 평가 시작]을 눌러주세요.")

# -----------------------------
# 7️⃣ 하단 푸터
# -----------------------------
st.divider()
st.markdown(
    """
    <p style='text-align:center; color:#999; font-size:13px;'>
    © 2025 Check Mate | Developed by GPT-5 — World's Leading AI Developer 🚀
    </p>
    """,
    unsafe_allow_html=True
)
