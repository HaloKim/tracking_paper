"""data/*.json -> site/ 정적 HTML 생성 (GitHub Pages 배포용)."""
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SITE_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site"

CSS = """
:root{--bg:#f7f7f5;--card:#fff;--fg:#1d1d1f;--muted:#6b6b70;--line:#e4e4e0;--accent:#c2410c;--tag:#f1efe9}
@media (prefers-color-scheme:dark){:root{--bg:#141415;--card:#1d1d20;--fg:#ececee;--muted:#9a9aa2;--line:#2c2c31;--accent:#fb923c;--tag:#26262b}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.7 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Pretendard","Noto Sans KR",sans-serif;word-break:keep-all}
main{max-width:820px;margin:0 auto;padding:32px 16px 80px}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
header h1{font-size:1.6rem;margin:0 0 4px}header p{color:var(--muted);margin:0 0 24px}
nav.pager{display:flex;justify-content:space-between;margin:0 0 24px;font-size:.95rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin:0 0 16px}
.card h2{font-size:1.15rem;margin:0 0 2px;line-height:1.45}
.orig{color:var(--muted);font-size:.9rem;margin:0 0 10px}
.meta{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 12px;font-size:.8rem}
.meta span,.meta a{background:var(--tag);border-radius:6px;padding:2px 8px;color:var(--muted)}
h3{font-size:.85rem;color:var(--accent);margin:14px 0 2px;letter-spacing:.02em}
.card p{margin:0}
details{margin-top:14px;font-size:.88rem;color:var(--muted)}summary{cursor:pointer}
ul.dates{list-style:none;padding:0;margin:0}ul.dates li{border-bottom:1px solid var(--line)}
ul.dates a{display:flex;justify-content:space-between;padding:12px 4px;color:var(--fg)}
ul.dates small{color:var(--muted)}
.pending{color:var(--muted);font-style:italic}
"""

e = html.escape


def page(title, body):
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><style>{CSS}</style></head>
<body><main>{body}</main></body></html>
"""


def card(rank, p):
    hf = f"https://huggingface.co/papers/{p['id']}"
    tags = [f"<span>▲ {p.get('upvotes', 0)}</span>"]
    if p.get("organization"):
        tags.append(f"<span>{e(p['organization'])}</span>")
    tags.append(f'<a href="{hf}">HF</a>')
    tags.append(f'<a href="https://arxiv.org/abs/{p["id"]}">arXiv</a>')
    if p.get("github"):
        tags.append(f'<a href="{e(p["github"])}">GitHub</a>')
    if p.get("project"):
        tags.append(f'<a href="{e(p["project"])}">Project</a>')

    if p.get("summary"):
        body = "".join(
            f"<h3>{label}</h3><p>{e(p[key])}</p>"
            for label, key in (("배경", "background"), ("요약", "summary"), ("한계", "limitations"))
        )
        heading = e(p["title_ko"])
        orig = f'<p class="orig">{e(p["title"])}</p>'
    else:
        body = '<p class="pending">한국어 요약이 아직 생성되지 않았습니다.</p>'
        heading, orig = e(p["title"]), ""

    authors = ", ".join(p.get("authors", [])[:8]) + (" 외" if len(p.get("authors", [])) > 8 else "")
    return f"""<article class="card" id="{e(p['id'])}">
<h2>{rank}. <a href="{hf}" style="color:inherit">{heading}</a></h2>{orig}
<div class="meta">{''.join(tags)}</div>{body}
<details><summary>원문 초록 · 저자</summary><p>{e(authors)}</p><p>{e(p.get('abstract', ''))}</p></details>
</article>"""


def main():
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    days = [json.loads(f.read_text()) for f in sorted(DATA_DIR.glob("*.json"), reverse=True)]
    days = [d for d in days if d["papers"]]

    for i, d in enumerate(days):
        newer = days[i - 1]["date"] if i > 0 else None
        older = days[i + 1]["date"] if i + 1 < len(days) else None
        pager = (
            f'<nav class="pager"><span>{f"<a href={older}.html>← {older}</a>" if older else ""}</span>'
            f'<a href="index.html">목록</a>'
            f'<span>{f"<a href={newer}.html>{newer} →</a>" if newer else ""}</span></nav>'
        )
        cards = "\n".join(card(r, p) for r, p in enumerate(d["papers"], 1))
        body = (
            f'<header><h1>{d["date"]} Daily Papers</h1>'
            f'<p>{len(d["papers"])}편 · upvote 순 · <a href="https://huggingface.co/papers/date/{d["date"]}">원본</a>'
            f' · 요약 모델 {e(d.get("model", ""))}</p></header>{pager}{cards}{pager}'
        )
        (SITE_DIR / f"{d['date']}.html").write_text(page(f"{d['date']} Daily Papers", body))

    items = "".join(
        f'<li><a href="{d["date"]}.html"><span>{d["date"]}</span><small>{len(d["papers"])}편</small></a></li>'
        for d in days
    )
    index = (
        '<header><h1>HF Daily Papers 한국어 요약</h1>'
        '<p>Hugging Face Daily Papers를 매일 한국어로 정리합니다. 한계 항목의 "(추정)"은 초록에 명시되지 않아 모델이 추정한 내용입니다.</p></header>'
        f'<ul class="dates">{items}</ul>'
    )
    (SITE_DIR / "index.html").write_text(page("HF Daily Papers 한국어", index))
    (SITE_DIR / ".nojekyll").write_text("")
    print(f"{len(days)}일치 페이지 생성 -> {SITE_DIR}")


if __name__ == "__main__":
    main()
