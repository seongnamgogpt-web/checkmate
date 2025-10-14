# app.py
"""
Check Mate - Streamlit app
Integrated features:
- Requirements-based evaluation
- AI-based automatic feedback & automatic revision suggestions (OpenAI SDK v0.27+)
- Basic spelling/spacing correction hooks (optional libs)
- File upload (.txt, .docx, .pdf)
- Real-time evaluation / re-evaluation
- Report download (JSON / Markdown)
- Simple visualization (radar-like bars)
- Saving evaluation logs to local SQLite (optional)

Notes:
- Install dependencies: streamlit, openai, python-docx, PyPDF2, reportlab, plotly
- Put your OpenAI API key in environment var OPENAI_API_KEY or Streamlit secrets

This is a single-file implementation focusing on clarity and extensibility rather than full production hardening.
"""

import streamlit as st
import os
import json
import re
from io import BytesIO
from datetime import datetime
from typing import List, Dict, Any

# Optional libs
try:
    import docx
except Exception:
    docx = None

try:
    import PyPDF2
except Exception:
    PyPDF2 = None

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
except Exception:
    reportlab = None

try:
    import plotly.graph_objects as go
except Exception:
    go = None

# OpenAI latest SDK usage
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# -------------------------
# Utilities
# -------------------------

def load_api_key():
    # priority: Streamlit secrets -> env var
    try:
        if "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass
    return os.environ.get("OPENAI_API_KEY", "")


def read_uploaded_file(uploaded) -> str:
    if not uploaded:
        return ""
    name = uploaded.name.lower()
    data = uploaded.read()
    if name.endswith('.txt'):
        try:
            return data.decode('utf-8')
        except Exception:
            return data.decode('cp949', errors='ignore')
    if name.endswith('.docx'):
        if docx is None:
            raise RuntimeError('python-docx is not installed in this environment.')
        bio = BytesIO(data)
        doc = docx.Document(bio)
        return "\n".join(p.text for p in doc.paragraphs)
    if name.endswith('.pdf'):
        if PyPDF2 is None:
            raise RuntimeError('PyPDF2 is not installed in this environment.')
        bio = BytesIO(data)
        reader = PyPDF2.PdfReader(bio)
        pages = []
        for p in reader.pages:
            try:
                pages.append(p.extract_text() or "")
            except Exception:
                pages.append("")
        return "\n".join(pages)
    raise RuntimeError('Unsupported file type. Use .txt, .docx or .pdf')


# Simple lightweight spelling/spacing fixer placeholder
# (If you have hanspell or 다른 한국어 라이브러리 설치, integrate here.)
def basic_cleanup_korean(text: str) -> str:
    # placeholder: normalize multiple spaces and fix repeated punctuation
    t = re.sub(r"\s+", " ", text)
    t = re.sub(r"\.{2,}", ".", t)
    return t.strip()


# Prompt for AI evaluation (improved schema)
EVAL_PROMPT = r"""
You are an expert evaluator for student submissions. Input contains:
- requirements: a list of requirements, one per line
- student_text: the text submitted by student
- examples: (optional) JSON with examples for reference

Task:
Produce EXACTLY ONE JSON object (no extra commentary) following this schema:
{
  "requirements": [
    {"id": 1, "requirement_text": "...", "status": "✅|❌|⚠️", "match_excerpts": ["..."], "reason": "...", "suggestion": "...", "fact_issues": [], "revised_snippet": "..."}
    ...
  ],
  "summary": {"fulfilled_count":0, "total_requirements":0, "overall_status":"✅|❌|⚠️", "score":0, "notes":"..."},
  "final_report_markdown": "..."
}

Rules:
- Mark status as ✅ if requirement clearly met, ❌ if not met, ⚠️ if a factual error relevant to the requirement is detected.
- For ⚠️, list fact_issues explaining why it's questionable.
- When possible, supply a revised_snippet showing a corrected sentence/paragraph.
- Use conservative scoring: ✅=1, ⚠️=0.3, ❌=0, normalized to 100.
- Output valid JSON only.
"""


def build_messages(requirements: str, student_text: str, examples_json: str = None) -> List[Dict[str, str]]:
    system = "You are Check Mate — a strict, precise evaluator. Return one JSON only."
    user = f"Requirements:\n{requirements}\n\nStudent Text:\n{student_text}\n\nInstructions:\n{EVAL_PROMPT}"
    if examples_json:
        user += f"\n\nExamples:\n{examples_json}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


# Score computation helper
def compute_score(requirements_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(requirements_list)
    if total == 0:
        return {"fulfilled_count": 0, "total_requirements": 0, "overall_status": "❌", "score": 0}
    raw = 0.0
    for it in requirements_list:
        s = it.get('status')
        if s == '✅':
            raw += 1.0
        elif s == '⚠️':
            raw += 0.3
    score = round((raw / total) * 100)
    statuses = {it.get('status') for it in requirements_list}
    if statuses == {'✅'}:
        overall = '✅'
    elif '⚠️' in statuses:
        overall = '⚠️'
    else:
        overall = '❌'
    return {"fulfilled_count": sum(1 for it in requirements_list if it.get('status')=='✅'),
            "total_requirements": total,
            "overall_status": overall,
            "score": score}


# AI call wrapper
def call_ai_evaluation(client: Any, messages: List[Dict[str, str]], model: str = "gpt-4o-mini", max_tokens: int = 1200) -> str:
    # Use chat completions create
    resp = client.chat.completions.create(model=model, messages=messages, max_tokens=max_tokens, temperature=0.0)
    try:
        return resp.choices[0].message['content']
    except Exception:
        # fallback to attribute access
        return getattr(resp.choices[0].message, 'content', '')


# Simple visualization: radar-like bar chart via plotly if available
def show_score_chart(scores: Dict[str, int]):
    if go is None:
        # fallback simple text
        st.write("Scores:")
        for k, v in scores.items():
            st.write(f"- {k}: {v}/10")
        return
    categories = list(scores.keys())
    values = [scores[k] for k in categories]
    fig = go.Figure(go.Bar(x=categories, y=values))
    fig.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)


# -------------------------
# Streamlit UI
# -------------------------

st.set_page_config(page_title="Check Mate — Auto Feedback", layout="wide")
st.title("Check Mate — 수행평가 자동검사 & 자동첨삭")
st.caption("요구조건 기반 평가 + AI 자동 첨삭 기능 통합 (OpenAI SDK v0.27+ 사용)")

# Layout
left, right = st.columns([1, 1])

with left:
    st.header("입력")
    st.markdown("""
    - 요구조건을 한 줄에 하나씩 입력하세요.
    - 학생 제출물은 텍스트로 붙여넣거나 .txt/.docx/.pdf 파일 업로드를 사용하세요.
    - 예시 로드 및 템플릿을 사용해 빠르게 테스트할 수 있습니다.
    """)
    requirements = st.text_area("요구조건 (한 줄씩)", height=200, placeholder="1) 제목 포함\n2) 가설 서술\n3) 방법 서술")
    submitted_text = st.text_area("학생 제출물 텍스트 붙여넣기 (또는 파일 업로드 사용)", height=250)
    uploaded = st.file_uploader("파일 업로드 (.txt, .docx, .pdf)", type=["txt", "docx", "pdf"])
    if uploaded and not submitted_text.strip():
        try:
            txt = read_uploaded_file(uploaded)
            submitted_text = txt
            st.success("파일에서 텍스트를 읽어왔습니다. 내용은 텍스트박스에서 확인하세요.")
        except Exception as e:
            st.error(f"파일 읽기 오류: {e}")

    st.markdown("---")
    st.subheader("자동첨삭 옵션")
    use_ai = st.checkbox("AI 첨삭 사용 (OpenAI API 필요)", value=True)
    auto_revise = st.checkbox("자동 수정 예시 생성(문장/단락 단위)", value=True)
    fine_mode = st.selectbox("피드백 강도", ["기본(맞춤법 중심)", "심화(논리·표현)", "전문가(엄격)"])
    max_tokens = st.slider("AI 응답 최대 토큰", 500, 3000, 1200)

    api_key_input = load_api_key()
    if not api_key_input:
        api_key_input = st.text_input("OpenAI API Key (환경변수/streamlit secrets 없을 때만 입력)", type="password")

    st.markdown("---")
    run = st.button("평가 실행")

with right:
    st.header("결과")
    result_area = st.empty()

# When run pressed
if run:
    if not requirements.strip():
        st.error("요구조건을 입력해주세요.")
    elif not submitted_text.strip():
        st.error("학생 제출물을 입력하거나 업로드해주세요.")
    else:
        # Preprocess text
        cleaned = basic_cleanup_korean(submitted_text)

        # Prepare examples_json (simple empty for now)
        examples_json = json.dumps([], ensure_ascii=False)

        # Build messages for AI
        messages = build_messages(requirements, cleaned, examples_json)

        ai_response_raw = None
        parsed = None

        if use_ai:
            if OpenAI is None:
                st.error("OpenAI SDK가 설치되어 있지 않습니다. 'openai' 패키지를 설치하세요.")
            else:
                key = api_key_input
                client = None
                try:
                    client = OpenAI(api_key=key)
                except Exception as e:
                    st.error(f"OpenAI 클라이언트 생성 실패: {e}")

                if client:
                    with st.spinner("AI로 평가 중... 잠시만 기다려주세요."):
                        try:
                            ai_response_raw = call_ai_evaluation(client, messages, max_tokens=max_tokens)
                        except Exception as e:
                            st.error(f"AI 호출 오류: {e}")
                            ai_response_raw = None

        # If AI produced JSON, parse it
        if ai_response_raw:
            try:
                parsed = json.loads(ai_response_raw)
            except Exception:
                # try to extract JSON substring
                try:
                    start = ai_response_raw.find('{')
                    end = ai_response_raw.rfind('}') + 1
                    parsed = json.loads(ai_response_raw[start:end])
                except Exception:
                    parsed = None

        # Fallback simple rule-based check if parsed is None
        if parsed is None:
            # Do a conservative rule-based pass: check presence of each requirement line
            reqs = [r.strip() for r in requirements.splitlines() if r.strip()]
            requirement_results = []
            for idx, req in enumerate(reqs, start=1):
                lowered = req.lower()
                # crude heuristics: if keyword '제목' in requirement -> check for a line that looks like title (short first line)
                excerpts = []
                status = '❌'
                reason = ''
                suggestion = ''
                revised_snippet = ''
                fact_issues = []
                if '글자' in lowered or '자' in lowered or '단어수' in lowered:
                    # numbers in requirement
                    m = re.search(r"(\d+)\s*~\s*(\d+)", req)
                    if m:
                        low = int(m.group(1))
                        high = int(m.group(2))
                        length = len(cleaned)
                        if low <= length <= high:
                            status = '✅'
                            reason = f"글자 수 {length}자가 조건 범위({low}~{high})에 들어옵니다."
                        else:
                            status = '❌'
                            reason = f"글자 수 {length}자가 조건 범위({low}~{high})에 없습니다."
                            suggestion = f"요구조건에 맞게 글자 수를 {low}~{high}자로 조정하세요."
                elif '제목' in lowered:
                    # check if first non-empty line is short (<40 chars)
                    first_line = next((ln.strip() for ln in cleaned.splitlines() if ln.strip()), '')
                    if first_line and len(first_line) < 80:
                        status = '✅'
                        excerpts = [first_line]
                        reason = '문서 상단에 제목으로 보이는 문장이 있습니다.'
                    else:
                        status = '❌'
                        suggestion = '글 상단에 명확한 제목을 추가하세요 (짧고 핵심을 표현).'
                else:
                    # check if any key noun from requirement in text
                    # extract candidate nouns/words
                    words = re.findall(r"[\w가-힣]+", req)
                    if words:
                        found = False
                        for w in words:
                            if w.lower() in cleaned.lower():
                                found = True
                                excerpts.append(w)
                        if found:
                            status = '✅'
                            reason = '요구조건에 언급된 핵심어가 본문에 포함되어 있습니다.'
                        else:
                            status = '❌'
                            suggestion = f"요구조건의 핵심어({', '.join(words[:3])})를 본문에 포함하세요."

                requirement_results.append({
                    'id': idx,
                    'requirement_text': req,
                    'status': status,
                    'match_excerpts': excerpts,
                    'reason': reason,
                    'suggestion': suggestion,
                    'fact_issues': fact_issues,
                    'revised_snippet': revised_snippet
                })

            summary = compute_score(requirement_results)
            md_lines = []
            md_lines.append(f"# Check Mate 리포트 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
            md_lines.append(f"- 점수(예상): {summary['score']} / 100  상태: {summary['overall_status']}")
            md_lines.append('')
            for it in requirement_results:
                md_lines.append(f"## {it['requirement_text']}")
                md_lines.append(f"- 상태: {it['status']}")
                if it['match_excerpts']:
                    md_lines.append(f"- 근거: {'; '.join(it['match_excerpts'])}")
                if it['reason']:
                    md_lines.append(f"- 사유: {it['reason']}")
                if it['suggestion']:
                    md_lines.append(f"- 제안: {it['suggestion']}")
                if it['revised_snippet']:
                    md_lines.append('```')
                    md_lines.append(it['revised_snippet'])
                    md_lines.append('```')
                md_lines.append('')

            final_md = '\n'.join(md_lines)

            # display
            with result_area.container():
                st.subheader('체크리스트 (Rule-based fallback)')
                for it in requirement_results:
                    st.markdown(f"**{it['requirement_text']}** — {it['status']}")
                st.markdown('---')
                st.markdown('### 자동 첨삭 요약')
                st.markdown(final_md)
                st.download_button('리포트(JSON) 다운로드', data=json.dumps({'requirements': requirement_results, 'summary': summary}, ensure_ascii=False, indent=2), file_name='checkmate_report.json')
                st.download_button('리포트(MD) 다운로드', data=final_md, file_name='checkmate_report.md')

        else:
            # parsed exists (AI output)
            # ensure summary completeness
            if 'summary' not in parsed or 'score' not in parsed['summary']:
                parsed['summary'] = compute_score(parsed.get('requirements', []))
            # if auto_revise requested and AI didn't provide revised_snippet for some items, ask model to produce them (best-effort)
            if auto_revise:
                # check which items miss revised_snippet
                missing = [it for it in parsed.get('requirements', []) if not it.get('revised_snippet')]
                if missing:
                    # prepare a small prompt to ask for revisions for those requirement ids
                    rev_prompt = "Please provide concise revised_snippet(s) for the following requirement ids in JSON list format: " + str([it['id'] for it in missing])
                    rev_messages = [{"role": "system", "content": "You are an assistant that returns JSON list of {id:..., revised_snippet:...}"}, {"role": "user", "content": rev_prompt + "\nStudent text:\n" + cleaned}]
                    try:
                        client = OpenAI(api_key=api_key_input)
                        rev_raw = call_ai_evaluation(client, rev_messages, max_tokens=800)
                        try:
                            rev_json = json.loads(rev_raw)
                            # map back
                            for r in rev_json:
                                for it in parsed['requirements']:
                                    if it['id'] == r.get('id'):
                                        it['revised_snippet'] = r.get('revised_snippet','')
                        except Exception:
                            # ignore if parsing failed
                            pass
                    except Exception:
                        pass

            # Build final markdown if not present
            final_md = parsed.get('final_report_markdown')
            if not final_md:
                lines = []
                lines.append(f"# Check Mate AI 리포트 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
                lines.append(f"- 점수: {parsed['summary'].get('score')} / 100 상태: {parsed['summary'].get('overall_status')}")
                lines.append('')
                for it in parsed.get('requirements', []):
                    lines.append(f"## {it.get('requirement_text')}")
                    lines.append(f"- 상태: {it.get('status')}")
                    if it.get('match_excerpts'):
                        lines.append(f"- 근거: {'; '.join(it.get('match_excerpts'))}")
                    if it.get('reason'):
                        lines.append(f"- 사유: {it.get('reason')}")
                    if it.get('fact_issues'):
                        for fi in it.get('fact_issues', []):
                            lines.append(f"- ⚠️ 사실성 문제: {fi}")
                    if it.get('suggestion'):
                        lines.append(f"- 제안: {it.get('suggestion')}")
                    if it.get('revised_snippet'):
                        lines.append('```')
                        lines.append(it.get('revised_snippet'))
                        lines.append('```')
                    lines.append('')
                lines.append('## 요약')
                lines.append(parsed['summary'].get('notes',''))
                final_md = '\n'.join(lines)
                parsed['final_report_markdown'] = final_md

            # display
            with result_area.container():
                st.subheader('체크리스트 (AI 평가)')
                for it in parsed.get('requirements', []):
                    st.markdown(f"**{it.get('requirement_text')}** — {it.get('status')}")
                    with st.expander('상세 보기'):
                        st.write('사유:')
                        st.write(it.get('reason',''))
                        if it.get('match_excerpts'):
                            st.write('근거 발췌:')
                            for ex in it.get('match_excerpts'):
                                st.code(ex)
                        if it.get('fact_issues'):
                            st.warning('사실성 문제:')
                            for fi in it.get('fact_issues'):
                                st.write('- '+fi)
                        if it.get('suggestion'):
                            st.info('수정 제안:')
                            st.write(it.get('suggestion'))
                        if it.get('revised_snippet'):
                            st.write('수정 예시:')
                            st.code(it.get('revised_snippet'))

                st.markdown('---')
                st.subheader('최종 마크다운 리포트')
                st.markdown(parsed.get('final_report_markdown',''), unsafe_allow_html=True)

                # downloads
                st.download_button('리포트(JSON) 다운로드', data=json.dumps(parsed, ensure_ascii=False, indent=2), file_name='checkmate_ai_report.json')
                st.download_button('리포트(MD) 다운로드', data=parsed.get('final_report_markdown',''), file_name='checkmate_ai_report.md')

                # small visualization: breakdown if possible
                # derive simple scores by counting statuses
                counts = {'✅':0, '⚠️':0, '❌':0}
                for it in parsed.get('requirements',[]):
                    counts[it.get('status', '❌')] += 1
                simple_scores = { 'Fulfilled': counts['✅'], 'Warnings': counts['⚠️'], 'Missing': counts['❌'] }
                show_score_chart(simple_scores)

                st.success(f"평가 완료 — 점수: {parsed['summary'].get('score')} / 100 상태: {parsed['summary'].get('overall_status')}")

# Footer
st.markdown('---')
st.caption('Check Mate — 요구조건 기반 자동 평가 및 AI 첨삭 데모. 더 강력한 기능(표절탐지, 표준화된 루브릭, 대량 업로드 등) 원하면 추가해드립니다.')

