# app.py
"""
Check Mate - 수행평가 자동 평가 및 첨삭 (개선판)
- 강화된 명칭/사실 검증 프롬프트 포함
- UI 단순화 및 체크리스트형 결과 표시
- 검사 엄격도 3단계, 자동 수정 기능 포함
"""

import os
import re
import json
import time
import streamlit as st
from openai import OpenAI
from utils import extract_text_from_uploaded_file

# ==============================
# 초기 설정
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
# 페이지 설정 (UI/접근성 고려)
# ==============================
st.set_page_config(page_title="Check Mate", layout="wide", initial_sidebar_state="expanded")
st.markdown(
    """
    <style>
      .big-title { font-size:32px; font-weight:700; }
      .subtle { color: #6c6c6c; }
      .cond-card { background: #f8f9fa; padding: 12px; border-radius: 8px; }
    </style>
    """,
    unsafe_allow_html=True
)
st.markdown('<div class="big-title">🧠 Check Mate - 수행평가 자동 평가 및 첨삭</div>', unsafe_allow_html=True)
st.markdown("수행평가 초안을 **조건 체크리스트**로 자동 평가하고, **명칭/사실 오류**까지 엄격히 검증하여 첨삭안을 제시합니다.", unsafe_allow_html=True)
st.markdown("---")

# ==============================
# 유틸 함수
# ==============================
def _extract_json_block(text: str):
    """모델 응답 안에서 JSON 블록(가장 첫번째)을 찾아 반환."""
    m = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text)
    return m.group(0) if m else text

def _safe_json_load(text: str):
    try:
        return json.loads(text)
    except Exception:
        try:
            return json.loads(text.replace("'", '"'))
        except Exception:
            return None

@st.cache_data(show_spinner=False)
def call_openai(prompt: str, model="gpt-4o-mini", temperature=0.25, max_tokens=1400):
    """
    OpenAI 호출 래퍼 (단일 메시지). 동일 프롬프트에 대한 반복 호출은 캐싱됩니다.
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

def build_eval_prompt(conditions: str, student_text: str, strictness: int) -> str:
    """
    강화된 평가 프롬프트.
    핵심 포인트: '명칭/인명/용어' 검증을 엄격히 수행하라.
    - 학생 글에 등장하는 인물/용어가 실제 역사지식/과학 지식과 다르면 반드시 ❌로 표시하고
      '정확한 명칭'을 제시하라. (오타/혼동/잘못된 인물명 모두 포함)
    - 출력은 JSON 하나만 반환.
    """
    strict_map = {
        1: "1단계 (느슨하게): 애매한 부분에는 관대하게 평가. 명백한 사실 오류만 ❌로 표시.",
        2: "2단계 (보통): 일반적인 기준. 사실/명칭 오류는 ❌, 표현/논리 오류는 ⚠️.",
        3: "3단계 (엄격하게): 매우 엄격. 오탈자나 잘못된 인명/용어도 ❌로 처리하고 정확한 정정안을 제시."
    }
    strict_text = strict_map.get(strictness, strict_map[2])

    # JSON 스키마(명확한 파싱을 위해)
    schema_example = {
        "conditions": [
            {
                "index": 1,
                "condition_text": "string",
                "status": "✅|⚠️|❌",
                "reason": "string",
                "suggestion": "string (수정문 또는 문장 예시)"
            }
        ],
        "score": 0,
        "summary": "short text"
    }

    prompt = f"""
당신은 '수행평가 채점 및 첨삭 전문가'입니다.
학생 글이 아래 [조건 목록]을 얼마나 충족하는지 평가하되, 특히 **명칭(인물/지명/전문용어)** 검증을 엄격히 수행하세요.

- 만약 학생이 어떤 '인물'을 특정했다면 (예: '홈스가 주장했다'),
  그 인물이 해당 주장/사건의 실제 제안자·관련자가 맞는지 **검증**하세요.
  - 만약 '홈스'가 잘못된 명칭(오타 또는 다른 인물)이라면, 해당 조건은 ❌로 표시하시오.
  - 그리고 '정확한 명칭'을 반드시 제시하시오 (예: '베게너').
  - 오타인지 혼동인지 명확히 구분하여 'reason'에 1문장으로 설명.

- 사실/개념 오류(예: 과학적 사실, 역사적 사건)도 ❌로 표시하고, 그 이유와 올바른 진술(한 문장)을 'suggestion'에 제시하세요.

- 문법·표현·논리적 흐름의 문제는 ⚠️로 표기하고, 간단한 문장 교정 예시를 'suggestion'에 제시하세요.

- 조건 충족 시 ✅.

출력 형식(반드시 준수): **JSON 객체 하나만** 출력하세요. 다른 텍스트는 허용되지 않습니다.
아래 스키마 예시처럼 출력하십시오:
{json.dumps(schema_example, ensure_ascii=False, indent=2)}

[검사 엄격도 설명] {strict_text}

[조건 목록]
{conditions}

[학생 글]
{student_text}
"""
    return prompt

def build_correction_prompt(conditions: str, original_text: str) -> str:
    """
    전체 문서 자동 수정 프롬프트
    - 명칭 오류가 있으면 올바른 명칭으로 교정
    - 문장 흐름 자연스럽게 정리
    - 출력은 수정된 전체 글(텍스트)만
    """
    prompt = f"""
당신은 문장 첨삭 전문가입니다.
아래 원문을 바탕으로 다음을 수행하세요:
1) 사실/명칭 오류(인물/지명/용어)가 있으면 정확한 명칭으로 바꿉니다.
2) 문법·표현·논리 흐름을 자연스럽게 다듬습니다.
3) 학생의 원래 의도와 톤을 유지하세요.
4) 출력은 '수정된 전체 글' 하나의 텍스트만 (설명 금지).

[조건 목록]
{conditions}

[원문]
{original_text}
"""
    return prompt

# ==============================
# UI: 좌측(입력) / 우측(결과)
# ==============================
left, right = st.columns([1, 1.2])

with left:
    st.subheader("1) 요구조건 입력")
    conditions = st.text_area("조건을 한 줄씩 입력하세요 (예: 1. 글자 수 800~1200자)", value=st.session_state.get("conditions", ""), height=120)
    st.session_state["conditions"] = conditions

    st.subheader("2) 검사 엄격도")
    strict_choice = st.selectbox("검사 수준을 선택하세요", ["1단계 (느슨하게)", "2단계 (보통)", "3단계 (엄격하게)"], index=1)
    strict_map = {"1단계 (느슨하게)":1, "2단계 (보통)":2, "3단계 (엄격하게)":3}
    strictness = strict_map[strict_choice]

    st.subheader("3) 학생 제출물")
    input_mode = st.radio("입력 방식", ["직접 입력", "파일 업로드"], index=0)
    student_text = ""
    if input_mode == "직접 입력":
        student_text = st.text_area("학생 글 입력", value=st.session_state.get("student_text", ""), height=300)
    else:
        uploaded = st.file_uploader("파일 업로드 (.txt, .pdf, .docx)")
        if uploaded:
            student_text = extract_text_from_uploaded_file(uploaded)
            st.success("✅ 파일 업로드/추출 완료")
            with st.expander("미리보기"):
                st.write(student_text[:2000])

    st.session_state["student_text"] = student_text

    st.markdown("")
    col_a, col_b = st.columns([1,1])
    with col_a:
        if st.button("▶ 평가 실행 (AI)"):
            # 입력 검증
            if not conditions.strip():
                st.warning("⚠️ 조건을 입력하세요.")
            elif not student_text.strip():
                st.warning("⚠️ 학생 글을 입력하거나 파일을 업로드하세요.")
            else:
                # 빌드 및 저장
                eval_prompt = build_eval_prompt(conditions, student_text, strictness)
                st.session_state["eval_prompt"] = eval_prompt

                # API 호출
                with st.spinner("AI가 평가 중입니다 — 명칭/사실검증을 엄격히 수행합니다..."):
                    raw_resp = call_openai(eval_prompt)
                    # 추출 및 파싱
                    json_block = _extract_json_block(raw_resp)
                    parsed = _safe_json_load(json_block)
                    if parsed is None:
                        st.error("⚠️ AI 응답을 파싱하지 못했습니다. (원본 응답을 디버그에 남깁니다.)")
                        st.session_state["eval_raw"] = raw_resp
                        st.session_state.pop("eval_json", None)
                    else:
                        st.success("✅ 평가 완료 — 결과를 오른쪽에서 확인하세요.")
                        st.session_state["eval_json"] = parsed
                        st.session_state["eval_raw"] = raw_resp
                        st.session_state["eval_time"] = time.time()

    with col_b:
        if st.button("✖️ 초기화"):
            for k in ["conditions", "student_text", "eval_json", "eval_raw", "corrected_text", "eval_prompt"]:
                st.session_state.pop(k, None)
            st.experimental_rerun()

    # 간단 도움말 / 접근성
    st.markdown("---")
    st.markdown("도움: 검사 엄격도를 높일수록 인물명·용어의 정확성에 더 엄격하게 체크합니다. 오타·혼동으로 인한 잘못된 명칭은 ❌로 표시됩니다.")
    st.markdown("접근성: 텍스트 크기는 브라우저 줌으로 쉽게 확대하세요. 필요한 경우 TTS(음성 읽기) 추가 연동 가능.")

with right:
    st.subheader("평가 결과 (체크리스트)")
    if "eval_json" not in st.session_state:
        st.info("왼쪽에서 평가를 실행하면 결과가 여기에 체크리스트 형식으로 표시됩니다.")
    else:
        res = st.session_state["eval_json"]
        # Score / summary
        score = res.get("score", None)
        summary = res.get("summary", "")
        if score is not None:
            st.metric("총점 (100점 만점)", f"{score} 점")
        if summary:
            st.markdown(f"**총평:** {summary}")

        st.markdown("")
        st.markdown("### 조건별 체크리스트")
        st.markdown("각 항목을 펼쳐 이유와 AI의 수정 제안을 확인하세요. (녹:충족 / 황:부분 / 적:불충족)")

        conditions_list = res.get("conditions", [])
        # 시각적으로 보기 좋게 표시
        for item in conditions_list:
            idx = item.get("index", "")
            cond_text = item.get("condition_text", "")
            status = item.get("status", "")
            reason = item.get("reason", "")
            suggestion = item.get("suggestion", "")

            # 카드 스타일: color by status
            if status == "✅":
                header = f"🟢 {idx}. {cond_text}"
            elif status == "⚠️":
                header = f"🟡 {idx}. {cond_text}"
            else:
                header = f"🔴 {idx}. {cond_text}"

            st.markdown(f"**{header}**")
            with st.expander("세부 보기: 이유 및 첨삭 제안"):
                st.markdown(f"- **상태:** {status}")
                st.markdown(f"- **이유:** {reason if reason else '없음'}")
                st.markdown(f"- **첨삭 제안 (수정 문장 예시):**")
                if suggestion:
                    st.code(suggestion, language="text")
                else:
                    st.markdown("`(제안 없음)`")

                # 개별 적용: 제안이 있을 때만 활성화
                if suggestion:
                    apply_key = f"apply_{idx}"
                    if st.button(f"▶ 이 제안 적용 (조건 {idx})", key=apply_key):
                        # 간단 적용: 원문 말미에 주석 형태로 덧붙이는 임시 적용 방식
                        current = st.session_state.get("student_text", "")
                        new_text = current + f"\n\n/* 자동 적용: 조건 {idx} 제안 */\n{suggestion}"
                        st.session_state["student_text"] = new_text
                        st.success("✅ 제안이 학생 글에 임시 적용되었습니다. (좌측 입력창에서 확인 가능)")

            st.markdown("---")

        # 전체 자동 적용(수정본 생성)
        st.markdown("")
        st.markdown("### 자동 수정 (전체 적용)")
        if st.button("🔧 자동으로 전체 수정본 생성"):
            # Build correction prompt
            corr_prompt = build_correction_prompt(st.session_state.get("conditions", ""), st.session_state.get("student_text", ""))
            with st.spinner("AI가 전체 문서를 기반으로 수정본을 생성합니다..."):
                corr_raw = call_openai(corr_prompt)
                # 모델은 텍스트만 반환하도록 지시했으므로 그대로 사용
                corrected = corr_raw.strip()
                st.session_state["corrected_text"] = corrected
                st.success("✅ 수정본 생성 완료")
                st.text_area("✏️ 자동 수정된 전체 글", value=corrected, height=300)
                st.download_button("💾 수정본 다운로드", corrected, file_name="corrected_text.txt")

        # 디버그: 원본 응답(숨김형)
        if st.checkbox("디버그: 원본 AI 응답 보기"):
            st.markdown("**원본 AI 응답(파싱 전)**")
            st.write(st.session_state.get("eval_raw", "(없음)"))

# ==============================
# 하단: 운영/비용/스케일 권장 사항
# ==============================
st.markdown("---")
st.header("운영 고려사항 (권장)")
st.markdown(
    """
- 대규모 트래픽(수십만~100만 사용자)을 목표로 한다면 Streamlit 단독 운용 대신:
  - 요청 큐(예: Redis + 작업 큐) + 비동기 백엔드(FastAPI 등)로 OpenAI 호출을 분리할 것을 권장합니다.
  - 캐시 정책(동일 입력 재사용), 로컬 사전검사(키워드/문법 기반)와 AI 검사를 결합해 비용을 절감하세요.
- 개인정보: 학생 제출물은 민감할 수 있으니 익명화·암호화 저장과 명확한 동의 절차 필요.
"""
)

# ==============================
# 끝
# ==============================

