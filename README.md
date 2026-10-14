# tracking_paper

[Hugging Face Daily Papers](https://huggingface.co/papers)를 매일 받아 논문별 **한국어 제목 · 배경 · 요약 · 한계**를 정리하고 GitHub Pages로 게시합니다.
요약은 Hugging Face Inference Providers(`router.huggingface.co`)로 생성합니다. HF Pro 계정의 월간 크레딧을 사용합니다.

## 설정

1. **HF 토큰 발급**: https://huggingface.co/settings/tokens 에서 fine-grained 토큰을 만들고 *Make calls to Inference Providers* 권한을 켭니다.
2. **Secret 등록**: 저장소 Settings → Secrets and variables → Actions → `HF_TOKEN` 추가.
3. **(선택) Variables**: 같은 화면의 Variables 탭에서
   - `HF_MODEL`: 사용할 모델 (기본 `deepseek-ai/DeepSeek-V4.1-Flash`)
   - `MAX_PAPERS`: upvote 상위 N편만 처리 (기본: 전부)
4. **Pages 활성화**: Settings → Pages → Source를 **GitHub Actions**로 선택.
5. Actions 탭 → *Daily Papers* → *Run workflow*로 첫 실행 (날짜 입력 가능, 예: `2026-10-14`).

이후 매일 09:30 KST에 전날 논문이 자동으로 추가됩니다.

## 로컬 실행

```bash
HF_TOKEN=hf_xxx python scripts/fetch.py 2026-10-14   # data/2026-10-14.json 생성
python scripts/build.py                              # site/ 생성
```

외부 패키지는 필요 없습니다(Python 3.10+ 표준 라이브러리만 사용).
같은 날짜를 다시 실행하면 이미 요약된 논문은 건너뛰고 실패했거나 새로 추가된 논문만 처리합니다.

## 참고

- 요약 근거는 초록뿐입니다. 초록에 한계가 명시되지 않은 경우 모델이 추정하며 `(추정)`으로 표시됩니다.
- 하루 약 50~100편 × 1회 호출입니다. 크레딧이 부족하면 `MAX_PAPERS`를 줄이거나 더 저렴한 모델을 쓰세요.
