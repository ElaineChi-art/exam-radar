# -*- coding: utf-8 -*-
"""每日主程式：聚合各科實務見解／修法，產出申論實務雷達。"""
import os
import json
import time
import datetime

import datetime as _dt

import config
import sources
import report


def build_highlights(subjects, cc_items):
    """跨科彙整近 HIGHLIGHT_DAYS 天最新項目，依日期新到舊取前 N。"""
    today = _dt.date.today()
    pool = []
    for it in cc_items:
        pool.append({**it, "subj": "憲法法庭"})
    for s in subjects:
        for col in s["columns"]:
            for it in col["items"]:
                pool.append({**it, "subj": s["name"]})
    out, seen = [], set()
    for it in pool:
        d = it.get("date", "")
        if not d:
            continue
        try:
            dd = _dt.date.fromisoformat(d)
        except ValueError:
            continue
        if (today - dd).days > config.HIGHLIGHT_DAYS:
            continue
        key = it["title"][:50]
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    out.sort(key=lambda x: x.get("_sort", ""), reverse=True)
    return out[:config.HIGHLIGHT_N]

ROOT = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(ROOT, "docs")
REPORTS = os.path.join(ROOT, "reports")


def gather_column(col):
    items = []
    try:
        if col.get("news_zh"):
            items += sources.fetch_news(col["news_zh"], "zh", 8)
        if col.get("news_en"):
            items += sources.fetch_news(col["news_en"], "en", 6)
        for rss in col.get("rss", []):
            items += sources.fetch_rss(rss[0], 6, rss[1] if len(rss) > 1 else "")
            time.sleep(0.2)
    except Exception as e:
        print(f"    欄位來源失敗：{e}")
    # 去重（同標題前 60 字）＋ 依日期新到舊
    seen, uniq = set(), []
    for it in items:
        key = it["title"][:60]
        if key and key not in seen:
            seen.add(key)
            uniq.append(it)
    uniq.sort(key=lambda x: x.get("_sort", ""), reverse=True)
    return uniq[:config.COL_LIMIT]


def run():
    os.makedirs(DOCS, exist_ok=True)
    os.makedirs(REPORTS, exist_ok=True)
    today = datetime.date.today().isoformat()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # 各科欄位
    subjects = []
    for s in config.SUBJECTS:
        print(f"==> {s['name']}")
        cols = []
        for col in s.get("columns", []):
            items = gather_column(col)
            print(f"    {col['label']}: {len(items)}")
            cols.append({"label": col["label"], "items": items})
        subjects.append({**s, "columns": cols})

    # 憲法法庭判決
    print("==> 憲法法庭判決")
    cc_items = sources.fetch_constitutional_court(config.CONS_COURT_URL, 15)
    print(f"    {len(cc_items)} 筆")

    # 法務部官方 RSS（法規異動＋修法新聞，皆過 SSL 略過驗證）
    print("==> 法務部 RSS")
    moj_law = sources.fetch_rss(config.MOJ_LAW_RSS[0], 8, config.MOJ_LAW_RSS[1],
                                lax=True, keywords=config.EXAM_STATUTES)
    moj_news = sources.fetch_rss(config.MOJ_NEWS_RSS[0], 8, config.MOJ_NEWS_RSS[1],
                                 lax=True, keywords=config.AMEND_KW)
    print(f"    法規 {len(moj_law)}、新聞 {len(moj_news)}")

    highlights = build_highlights(subjects, cc_items)
    print(f"==> 跨科精選：{len(highlights)} 則")

    html_str = report.build_html(
        today, now, subjects, cc_items, now, moj_law, moj_news,
        config.REF_SITES, config.REF_TIPS, highlights)
    with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_str)

    snapshot = {"date": today, "subjects": subjects, "cons_court": cc_items,
                "moj_law": moj_law, "moj_news": moj_news}
    with open(os.path.join(REPORTS, f"{today}.json"), "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    total = sum(len(c["items"]) for s in subjects for c in s["columns"])
    print(f"\n完成：{len(subjects)} 科、憲判 {len(cc_items)}、"
          f"法務部 {len(moj_law)+len(moj_news)}、各科 {total} 則 → docs/index.html")


if __name__ == "__main__":
    run()
