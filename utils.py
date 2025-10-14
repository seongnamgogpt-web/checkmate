import io
import os
from typing import List

try:
	import docx
except Exception:
	docx = None

try:
	import PyPDF2
except Exception:
	PyPDF2 = None

try:
	from PIL import Image
except Exception:
	Image = None

try:
	import easyocr
	import numpy as np
except Exception:
	easyocr = None
	np = None


def extract_text_from_uploaded_file(uploaded_file) -> str:
	"""간단한 파일 텍스트 추출기: txt, docx, pdf 지원

	uploaded_file: Streamlit UploadedFile 객체
	returns: 추출된 텍스트
	"""
	filename = uploaded_file.name.lower()
	data = uploaded_file.read()

	if filename.endswith('.txt'):
		try:
			return data.decode('utf-8')
		except Exception:
			return data.decode('latin-1')

	if filename.endswith('.docx') and docx is not None:
		try:
			doc = docx.Document(io.BytesIO(data))
			return '\n'.join(p.text for p in doc.paragraphs)
		except Exception:
			return ''

	if filename.endswith('.pdf') and PyPDF2 is not None:
		try:
			reader = PyPDF2.PdfReader(io.BytesIO(data))
			texts = []
			for p in reader.pages:
				texts.append(p.extract_text() or '')
			return '\n'.join(texts)
		except Exception:
			return ''

	# 이미지 파일인 경우 OCR 시도
	if filename.endswith(('.png', '.jpg', '.jpeg')):
		try:
			return extract_text_from_image_bytes(data)
		except Exception:
			return ''

	# 그 외: 바이너리로 디코드 시도
	try:
		return data.decode('utf-8')
	except Exception:
		return ''


def extract_text_from_image_bytes(image_bytes: bytes) -> str:
	"""이미지 바이트에서 OCR을 시도합니다. `easyocr`가 설치되어 있으면 사용합니다.
	설치되어 있지 않으면 빈 문자열을 반환합니다.
	"""
	if Image is None or easyocr is None or np is None:
		return ''
	try:
		img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
		arr = np.array(img)
		# easyocr Reader 초기화는 비용이 있으므로 라이브러리가 제공되면 Reader를 생성
		try:
			reader = easyocr.Reader(['ko', 'en'], gpu=False)
			results = reader.readtext(arr, detail=0, paragraph=True)
			if isinstance(results, list):
				return '\n'.join(results)
			return str(results)
		except Exception:
			return ''
	except Exception:
		return ''


def summarize_match(requirements: List[str], submission_text: str, openai_api_key: str) -> str:
	"""간단한 프롬프트 생성 및 OpenAI 호출 래퍼.

	주의: 실제 OpenAI SDK를 설치하고 API 키를 설정해야 합니다. 여기서는
	키가 없을 때 로컬 모의 응답을 반환합니다.
	"""
	# 프롬프트 빌드
	prompt = "당신은 숙련된 교육 평가자입니다. 아래 수행평가 요구조건과 학생 제출물을 비교하여 항목별로 만족 여부를 판단하고, 개선점을 제안하세요.\n\n"
	prompt += "요구조건:\n"
	for i, r in enumerate(requirements, 1):
		prompt += f"{i}. {r}\n"
	prompt += "\n학생 제출물:\n" + submission_text[:4000] + "\n\n"
	prompt += "출력 형식: 마크다운으로 각 항목별 결과(만족/부분/미흡), 근거, 개선 제안\n"

	# 실제 OpenAI 호출
	if not openai_api_key:
		# 로컬 모의 응답
		lines = ["- 요약: OpenAI API 키가 설정되어 있지 않아 모의 결과를 반환합니다.\n"]
		for i, r in enumerate(requirements, 1):
			lines.append(f"### {i}. {r}\n- 상태: 부분\n- 근거: 제출물에서 관련 문장이 일부 확인됨.\n- 개선 제안: 요구조건을 명확히 포함시키고 예시를 추가하세요.\n")
		return '\n'.join(lines)

	try:
		# openai>=1.0.0 migration: use OpenAI client
		from openai import OpenAI
		client = OpenAI(api_key=openai_api_key)
		resp = client.chat.completions.create(
			model="gpt-4o-mini",
			messages=[{"role": "user", "content": prompt}],
			max_tokens=800,
			temperature=0.2,
		)
		# new response shape: choices -> each has a message
		return resp.choices[0].message.content
	except Exception as e:
		return f"OpenAI 호출 중 오류가 발생했습니다: {e}"
