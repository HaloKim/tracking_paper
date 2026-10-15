"""Hugging Face Daily Papers를 받아 한국어 요약(제목/배경/요약/한계)을 data/YYYY-MM-DD.json에 저장한다.

사용법:
  HF_TOKEN=hf_xxx python scripts/fetch.py               # 어제(UTC) 날짜
  HF_TOKEN=hf_xxx python scripts/fetch.py 2026-10-14    # 특정 날짜
환경변수:
  HF_TOKEN     Hugging Face 토큰 (Inference Providers 사용 권한)
  HF_MODEL     사용할 모델 (기본: deepseek-ai/DeepSeek-V4.1-Flash)
  MAX_PAPERS   upvote 상위 N개만 처리 (기본: 0 = 전부)
  DRY_RUN=1    LLM 호출 없이 원문만 저장 (테스트용)
"""
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PAPERS_API = "https://huggingface.co/api/daily_papers?date={date}&limit=100"
CHAT_API = "https://router.huggingface.co/v1/chat/completions"
MODEL = os.environ.get("HF_MODEL") or "deepseek-ai/DeepSeek-V4.1-Flash"
FIELDS = ("title_ko", "background", "summary", "limitations")

PROMPT = """다음은 AI 논문의 제목과 초록입니다. 한국어로 정리해 주세요.

제목: {title}
초록: {abstract}

아래 키를 가진 JSON 객체 하나만 출력하세요. 다른 텍스트는 쓰지 마세요.
- "title_ko": 논문 제목의 자연스러운 한국어 번역
- "background": 이 연구가 나온 배경과 해결하려는 문제 (2~3문장)
- "summary": 제안 방법과 주요 결과 요약 (3~4문장)
- "limitations": 한계점 (2~3문장). 초록에 명시되지 않았다면 초록 내용을 근거로 합리적으로 추정하고, 문장 앞에 "(추정)"을 붙이세요.

전문 용어는 필요하면 영어를 괄호로 병기하세요."""


class FatalError(RuntimeError):
    pass


def http_json(url, body=None, token=None, timeout=120):
    headers = {"User-Agent": "tracking-paper/1.0"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def parse_json(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise ValueError(f"JSON을 찾을 수 없음: {text[:200]}")
    obj = json.loads(m.group(0))
    missing = [k for k in FIELDS if not obj.get(k)]
    if missing:
        raise ValueError(f"누락된 키: {missing}")
    return {k: str(obj[k]).strip() for k in FIELDS}


def summarize(title, abstract, token, retries=6):
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT.format(title=title, abstract=abstract)}],
        "temperature": 0.3,
        # 추론(reasoning) 모델은 생각 토큰도 max_tokens에 포함되므로 넉넉하게 잡는다
        "max_tokens": 8192,
    }
    last = None
    for attempt in range(retries):
        wait = min(10 * 2**attempt, 120)
        try:
            resp = http_json(CHAT_API, body, token, timeout=300)
            choice = resp["choices"][0]
            content = choice["message"].get("content") or ""
            if choice.get("finish_reason") == "length":
                raise ValueError(f"출력이 max_tokens에서 잘림 (content {len(content)}자)")
            return parse_json(content)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read()[:300]!r}"
            if e.code in (401, 402, 403):  # 인증/크레딧 문제는 재시도 무의미
                raise FatalError(last)
            if e.code == 429 and e.headers.get("Retry-After", "").isdigit():
                wait = max(wait, int(e.headers["Retry-After"]))
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        if attempt + 1 < retries:
            time.sleep(wait)
    raise RuntimeError(last)


def save(out, date, papers, rest, existing):
    """중간 저장: 아직 처리하지 않은 논문은 기존 기록을 유지해 타임아웃/중단 시에도 진행분이 남게 한다."""
    pending = [existing[it["paper"]["id"]] for it in rest if it["paper"]["id"] in existing]
    out.write_text(json.dumps({"date": date, "model": MODEL, "papers": papers + pending}, ensure_ascii=False, indent=1))


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)).isoformat()
    dry_run = os.environ.get("DRY_RUN") == "1"
    token = os.environ.get("HF_TOKEN")
    if not token and not dry_run:
        sys.exit("HF_TOKEN 환경변수가 필요합니다.")
    max_papers = int(os.environ.get("MAX_PAPERS") or 0)

    items = http_json(PAPERS_API.format(date=date))
    items.sort(key=lambda x: x["paper"].get("upvotes", 0), reverse=True)
    if max_papers:
        items = items[:max_papers]
    if not items:
        print(f"{date}: 논문 없음")
        return

    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / f"{date}.json"
    existing = {}
    if out.exists():
        existing = {p["id"]: p for p in json.loads(out.read_text())["papers"]}

    papers, failed, fatal = [], 0, None
    for i, item in enumerate(items, 1):
        p = item["paper"]
        rec = {
            "id": p["id"],
            "title": p["title"],
            "abstract": p.get("summary", "").strip(),
            "authors": [a["name"] for a in p.get("authors", [])],
            "upvotes": p.get("upvotes", 0),
            "github": p.get("githubRepo"),
            "project": p.get("projectPage"),
            "organization": (p.get("organization") or {}).get("fullname"),
        }
        prev = existing.get(p["id"], {})
        if all(prev.get(k) for k in FIELDS):
            rec.update({k: prev[k] for k in FIELDS})  # 이미 처리된 논문은 재사용
        elif not dry_run and not fatal:
            try:
                rec.update(summarize(rec["title"], rec["abstract"], token))
                print(f"[{i}/{len(items)}] {rec['id']} OK")
            except FatalError as e:
                fatal = e
                print(f"인증/크레딧 오류로 요약을 중단합니다: {e}", file=sys.stderr)
            except Exception as e:  # noqa: BLE001
                failed += 1
                print(f"[{i}/{len(items)}] {rec['id']} 실패: {e}", file=sys.stderr)
        papers.append(rec)
        save(out, date, papers, items[i:], existing)

    print(f"{date}: {len(papers)}편 저장 (실패 {failed}) -> {out}")
    if fatal:
        sys.exit(1)


if __name__ == "__main__":
    main()
