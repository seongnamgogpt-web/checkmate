
# app.py
import os
import re
import json
import time
import streamlit as st
from openai import OpenAI
from utils import extract_text_from_uploaded_file

# ==============================
# 초기 설정 / API 키
# ==============================
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

API_KEY = os.getenv("OPENAI_API_KEY", st.secrets.get("OPENAI_API_KEY", None))
if not API_KEY:
    st.error("❌ OpenAI API 키가 설정되지 않았습니다. 환경변수 OPENAI_API_KEY를 설정해주세요.")
    st.stop()

client = OpenAI(api_key=API_KEY)

# ==============================
# 페이지 설정
# ==============================
st.set_page_config(page_title="Check Mate - 수행평가 자동 첨삭기", layout="wide")
st.title("🧠 Check Mate - 수행평가 자동 평가 및 첨삭")

# 설명
st.markdown("""
**Check Mate**는 학생 제출물(초안)이 교사가 제시한 조건을 얼마나 충족하는지 **체크리스트 형식**으로 평가하고,
사실성(명칭/개념/사실 오류)까지 검증하여 **자동 첨삭(수정문 제시)**까지 해주는 웹앱입니다.

특징:
- 검사 수준 선택(1:느슨 / 2:보통 / 3:엄격)
- 조건별 상태(✅/⚠️/❌), 이유, 첨삭 제안(문장 단위)
- JSON 출력으로 안정적 파싱 → 체크리스트 UI 제공
""")

# ==============================
# 유틸 함수들
# ==============================
def _strip_json_from_response(text: str) -> str:
    """
    모델이 응답에서 JSON 객체를 포함해 반환했을 때,
    가장 먼저 등장하는 JSON object/array를 찾아 반환.
    """
    # attempt to find {...} or [...] top-level JSON
    json_like = re.search(r'(\{.*\}|\[.*\])', text, flags=re.DOTALL)
    if json_like:
        return json_like.group(0)
    return text

def safe_parse_json(text: str):
    """
    안전하게 JSON을 파싱 시도. 실패하면 None 반환.
    """
    try:
        return json.loads(text)
    except Exception:
        try:
            # 일부러 작은 따옴표로 오는 경우 교정 시도
            fixed = text.replace("'", '"')
            return json.loads(fixed)
        except Exception:
            return None

@st.cache_data(show_spinner=False)
def call_evaluation_api(prompt: str, model="gpt-4o-mini", temperature=0.3, max_tokens=1400):
    """
    실제 OpenAI API 호출 (캐싱 적용: 동일 입력에 대해 반복 호출 방지)
    """
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "너는 수행평가 첨삭 및 채점 전문가 AI야."},
            {"role": "user", "content": prompt}
        ],
        temperature=temperature,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content

def build_evaluation_prompt(conditions: str, student_text: str, strictness_level: int, require_json_only=True) -> str:
    """
    개선된 프롬프트를 만들고 반환.
    strictness_level: 1,2,3
    require_json_only: True이면 모델에게 'JSON만' 출력하도록 강제
    """
    strict_desc = {
        1: "1단계 (느슨하게): 애매한 경우 관대하게 처리. 가능한 한 ✅을 주되, 명백한 사실 오류만 ❌로 표시.",
        2: "2단계 (보통): 일반적인 기준. 사실/명칭 오류는 ❌, 표현/논리 오류는 ⚠️.",
        3: "3단계 (엄격하게): 엄격한 평가. 사소한 누락·애매함도 ⚠️ 또는 ❌로 처리."
    }[strictness_level]

    # JSON 스키마 명시: 명확한 파싱을 위해 모델에게 JSON만 출력하게 강제
    json_schema = {
        "type": "object",
        "properties": {
            "conditions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "condition_text": {"type": "string"},
                        "status": {"type": "string", "enum": ["✅","⚠️","❌"]},
                        "reason": {"type": "string"},
                        "suggestion": {"type": "string"}
                    }
                }
            },
            "score": {"type": "integer"},
            "summary": {"type": "string"}
        }
    }

    prompt = f"""
너는 수행평가 첨삭 및 채점 전문가이며 사실 검증 능력이 있다.
학생의 글이 아래 [조건 목록]에 얼마나 부합하는지, 사실/명칭/개념 오류까지 검사하여 체크리스트 형태로 평가해라.
평가 기준:
- 조건 충족: ✅
- 문법/표현/논리적 부족 또는 부분 충족: ⚠️
- 사실/명칭/개념 오류 또는 조건 미충족: ❌

검사 엄격도: {strict_desc}

출력 요구사항(반드시 따를 것):
1) **반드시** 아래의 JSON 스키마에 맞춰 **JSON 객체 하나만** 출력하라.
2) 조건들은 입력 순서대로 'conditions' 배열에 넣고 각 항목은 index(1-based), condition_text, status, reason, suggestion 을 포함하라.
3) suggestion은 수정된 문장(또는 문장 예시)을 포함하라. (가능하면 실제 교정 문장 제시)
4) score는 0~100 정수.
5) summary는 1-3문장 내외의 간단 총평.

JSON 스키마(예시):
{json.dumps(json_schema, ensure_ascii=False, indent=2)}

[조건 목록]
{conditions}

[학생 글]
{student_text}

출력: **JSON 하나만** (다른 텍스트 금지).
"""
    return prompt

def build_correction_prompt(conditions: str, original_text: str) -> str:
    """
    전체 문서 자동 수정 요청 프롬프트. 수정된 전체 문장만 출력하도록 지시.
    """
    prompt = f"""
너는 문장 첨삭 전문가야. 아래 학생의 원문을 바탕으로,
- 조건에 어긋나거나 사실이 틀린 문장은 정확한 사실/명칭으로 바꿔라.
- 문법, 표현, 논리 흐름도 자연스럽게 다듬어라.
- 학생의 원래 의도와 톤을 최대한 유지하되, 오류는 바로잡아라.
- 출력은 '수정된 전체 글' 하나의 텍스트로만 출력하라. (설명 금지)

[조건 목록]
{conditions}

[원문]
{original_text}
"""
    return prompt

# ==============================
# 레이아웃: 입력(왼쪽) / 결과(오른쪽)
# ==============================
left, right = st.columns([1, 1])

with left:
    st.header("📋 수행평가 요구조건 입력 (한 줄씩)")
    conditions_text = st.text_area("조건을 한 줄씩 입력하세요:", value=st.session_state.get("conditions_text", ""), height=140)
    st.session_state["conditions_text"] = conditions_text

    st.header("⚙️ 검사 수준 선택")
    strictness_label = st.radio("검사 엄격도", ["1단계 (느슨하게)", "2단계 (보통)", "3단계 (엄격하게)"])
    strictness_map = {"1단계 (느슨하게)":1, "2단계 (보통)":2, "3단계 (엄격하게)":3}
    strictness_level = strictness_map[strictness_label]

    st.header("📝 학생 제출물 입력")
    input_mode = st.radio("입력 방식", ["직접 입력", "파일 업로드"])
    student_text = ""
    if input_mode == "직접 입력":
        student_text = st.text_area("학생 글 입력", value=st.session_state.get("student_text", ""), height=300)
    else:
        uploaded_file = st.file_uploader("파일 업로드 (.txt, .pdf, .docx)")
        if uploaded_file is not None:
            student_text = extract_text_from_uploaded_file(uploaded_file)
            st.success("✅ 파일 업로드 및 추출 완료")
            with st.expander("📄 텍스트 미리보기"):
                st.write(student_text[:2000])

    st.session_state["student_text"] = student_text

    col1, col2 = st.columns([1,1])
    with col1:
        eval_btn = st.button("✳️ AI 자동 평가 실행")
    with col2:
        clear_btn = st.button("🧹 입력 초기화")

    if clear_btn:
        st.session_state["student_text"] = ""
        st.session_state["conditions_text"] = ""
        st.session_state.pop("evaluation_json", None)
        st.experimental_rerun()

    # 실행
    if eval_btn:
        if not conditions_text.strip():
            st.warning("⚠️ 조건을 입력해 주세요.")
        elif not student_text.strip():
            st.warning("⚠️ 학생 글을 입력하거나 파일을 업로드 해 주세요.")
        else:
            # 프롬프트 빌드
            eval_prompt = build_evaluation_prompt(conditions_text, student_text, strictness_level, require_json_only=True)
            # 저장해서 UI 하단에 보여줌
            st.session_state["last_eval_prompt"] = eval_prompt

            with st.spinner("AI가 평가 및 사실검증 중입니다... (잠시만 기다려주세요)"):
                # 실제 API 호출 (캐시 적용)
                raw = call_evaluation_api(eval_prompt)
                # 모델이 JSON을 텍스트 외에도 붙여 반환할 수 있으니 JSON 추출 시도
                json_part = _strip_json_from_response(raw)
                parsed = safe_parse_json(json_part)

                if parsed is None:
                    # 파싱 실패 시 원본 텍스트 함께 저장하고 사용자에게 알림
                    st.error("⚠️ AI가 보낸 응답을 JSON으로 파싱하지 못했습니다. 아래 '원본 응답'을 확인하세요.")
                    st.session_state["evaluation_raw"] = raw
                    st.session_state.pop("evaluation_json", None)
                else:
                    st.success("✅ 평가 결과가 준비되었습니다.")
                    st.session_state["evaluation_json"] = parsed
                    # store raw for debugging if needed
                    st.session_state["evaluation_raw"] = raw
                    # store timestamp
                    st.session_state["eval_time"] = time.time()

with right:
    st.header("📊 평가 결과 (체크리스트 형식)")
    if "evaluation_json" not in st.session_state:
        st.info("왼쪽에서 조건과 학생 글 입력 후 'AI 자동 평가 실행'을 눌러주세요.")
    else:
        eval_json = st.session_state["evaluation_json"]

        # Score & Summary
        score = eval_json.get("score", None)
        summary = eval_json.get("summary", "")

        if score is not None:
            st.metric(label="총점 (100점 만점)", value=f"{score} 점")
        st.write(summary)

        st.markdown("---")
        st.subheader("🔎 조건별 상세 체크리스트")

        conditions = eval_json.get("conditions", [])
        # 렌더링: index | 상태(아이콘) | 조건 텍스트 | 이유 | 제안 | 적용 버튼
        for cond in conditions:
            idx = cond.get("index")
            cond_text = cond.get("condition_text", "")
            status = cond.get("status", "")
            reason = cond.get("reason", "")
            suggestion = cond.get("suggestion", "")

            status_icon = {"✅":"🟢 ✅", "⚠️":"🟡 ⚠️", "❌":"🔴 ❌"}.get(status, status)
            st.markdown(f"**{idx}. {cond_text}**  —  {status_icon}")
            with st.expander(f"세부: 이유 / 첨삭 제안 (조건 {idx})"):
                st.markdown(f"- **이유:** {reason}")
                st.markdown(f"- **첨삭 제안:** {suggestion if suggestion else '없음'}")
                # 개별 적용 버튼: suggestion이 있으면 원문에 반영하여 미리보기 제공
                if suggestion:
                    if st.button(f"➕ 제안 적용: 조건 {idx}의 수정문으로 대체", key=f"apply_{idx}"):
                        # 간단히: 원문 끝에 suggestion을 붙이는 방식 (복잡한 원문 위치 대체는 향후 확장)
                        new_text = st.session_state.get("student_text", "") + "\n\n" + f"/* 수정(조건 {idx}) */\n{suggestion}"
                        st.session_state["student_text"] = new_text
                        st.success(f"조건 {idx}의 제안이 학생 글에 임시 적용되었습니다. 좌측의 입력창에서 확인하세요.")
            st.markdown("---")

        # 자동 전체 수정(Apply All Corrections)
        st.subheader("✏️ 자동 수정 옵션")
        if st.button("🔧 모든 제안 자동 적용(새 수정본 생성)"):
            # Build correction prompt using stored conditions and original text
            correction_prompt = build_correction_prompt(st.session_state["conditions_text"], st.session_state["student_text"])
            with st.spinner("AI가 전체 문서를 기반으로 수정본을 생성 중입니다..."):
                corrected_raw = call_evaluation_api(correction_prompt)
                # 모델에게 "설명금지, 수정된 전체 글만"을 지시했으므로 보통 텍스트가 반환됨.
                # 단, call_evaluation_api 캐시 때문에 동일입력 반복시 캐싱 가능.
                corrected_text = corrected_raw.strip()

                # 안전성: 만약 모델이 JSON을 반환한 경우, 그냥 원본 텍스트로 처리
                # 저장 및 표시
                st.session_state["corrected_text"] = corrected_text
                st.success("✅ 자동 수정본이 생성되었습니다.")
                st.text_area("✏️ 자동 수정된 전체 글", value=corrected_text, height=300)
                st.download_button("💾 수정된 글 다운로드", corrected_text, file_name="corrected_text.txt")

        # raw 응답(디버그용)
        if st.expander("🔬 원본 AI 응답(디버그)"):
            st.write(st.session_state.get("evaluation_raw", "없음"))

# ==============================
# 하단: 프롬프트 공개 및 예시
# ==============================
st.markdown("---")
st.header("🧾 내부 프롬프트 (AI에게 전달되는 실제 프롬프트 — 검토용)")
if "last_eval_prompt" in st.session_state:
    with st.expander("프롬프트 펼치기"):
        st.code(st.session_state["last_eval_prompt"], language="text")
else:
    st.info("평가를 실행하면 여기에 사용된 프롬프트가 표시됩니다.")

st.header("🧩 평가 예시 (미리보기)")
with st.expander("예시 1"):
    st.markdown("""
**조건**
1. 글자 수 800~1200자  
2. 대륙이동설 제안자 언급  
3. 과학적 근거 포함

**학생 글**
베게너는 대륙이 이동한다고 주장했다. 후에 해령과 판 구조론으로 증명되었다.
""")
with st.expander("예시 2"):
    st.markdown("""
**조건**
1. 세종대왕 업적 2가지 이상 언급  
2. 사회적 의미 서술

**학생 글**
세종대왕은 훈민정음을 창제하고 측우기를 만들었다.
""")
