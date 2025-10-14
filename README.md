# Check Mate

간단한 Streamlit 기반 수행평가 초안 검사 웹 애플리케이션 입니다.

## 요구사항
- Python 3.10+
- `OPENAI_API_KEY` 환경변수 (선택: 없으면 모의 응답)

## 설치
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 실행
- (선택) `.env` 파일 생성: 제공된 `.env.example`을 복사해서 `OPENAI_API_KEY`를 채우세요.
```bash
export OPENAI_API_KEY="sk-..."  # 또는 .env에 설정
streamlit run app.py
```

## 지원 파일 형식
- txt, pdf, docx(간단 파싱)


## 향후 개선
- 이미지 OCR(전처리, 한국어 언어팩 설치 안내)
- 파일 업로드 보안 검증
- 테스트 및 CI
