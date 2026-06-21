# -*- coding: utf-8 -*-
"""每日主程式：聚合各科實務見解／修法，產出申論實務雷達。"""
import os
import json
import time
import datetime

import re
import datetime as _dt

import config
import sources
import report


def _norm_title(t):
    """去掉媒體名後綴與標點，留純文字供相似度比對。"""
    t = re.split(r"\s*[-|｜–—]\s*", t or "")[0]
    return re.sub(r"[^一-鿿A-Za-z0-9]", "", t).lower()


def _trigrams(s):
    return {s[i:i + 3] for i in range(len(s) - 2)} or ({s} if s else set())


def _is_dup(a, b):
    """兩標題是否為同一則新聞（字元三連詞重疊率 ≥ 0.6）。"""
    A, B = _trigrams(a), _trigrams(b)
    if not A or not B:
        return a == b
    return len(A & B) / min(len(A), len(B)) >= 0.6


def _concepts_of(text):
    low = text or ""
    return [name for name, kws in config.GRAPH_CONCEPTS if any(k in low for k in kws)]


def build_graph(subjects, cc_items):
    """Obsidian 風關聯圖：項目 → 科目節點 ＋ 爭點概念節點。"""
    pool = [{**it, "subj": "憲法法庭"} for it in cc_items]
    for s in subjects:
        for col in s["columns"]:
            for it in col["items"]:
                pool.append({**it, "subj": s["name"]})
    # 新到舊，取前 N
    pool.sort(key=lambda x: x.get("_sort", ""), reverse=True)
    pool = pool[:config.GRAPH_ITEMS]

    nodes, edges, have = [], [], set()

    def add_node(nid, **kw):
        if nid not in have:
            have.add(nid)
            nodes.append({"id": nid, **kw})

    for idx, it in enumerate(pool):
        concs = _concepts_of(it.get("title", "") + " " + it.get("summary", ""))
        subj = it.get("subj", "")
        if not concs and not subj:
            continue
        iid = f"i{idx}"
        title = it.get("title", "")
        add_node(iid, label=title[:14], title=title, url=it.get("url", ""), group="item")
        if subj:
            sid = "s_" + subj
            add_node(sid, label=subj, group="subject")
            edges.append({"from": iid, "to": sid})
        for c in concs:
            cid = "c_" + c
            add_node(cid, label=c, group="concept")
            edges.append({"from": iid, "to": cid})
    # 只保留有連到項目的概念/科目節點已自然成立
    return {"nodes": nodes, "edges": edges}


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
    # 先依日期新到舊，再做相似度去重（同案不同媒體只留最新一則）
    cand = []
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
        cand.append(it)
    cand.sort(key=lambda x: x.get("_sort", ""), reverse=True)

    out, kept_norms = [], []
    for it in cand:
        nt = _norm_title(it["title"])
        if any(_is_dup(nt, k) for k in kept_norms):
            continue
        kept_norms.append(nt)
        out.append(it)
        if len(out) >= config.HIGHLIGHT_N:
            break
    return out

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
    # 濾掉國際新聞雜訊 ＋ 去重（同標題前 60 字）＋ 依日期新到舊
    seen, uniq = set(), []
    for it in items:
        if sources.is_foreign(it["title"]):
            continue
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

    graph = build_graph(subjects, cc_items)
    ni = sum(1 for n in graph["nodes"] if n["group"] == "item")
    nc = sum(1 for n in graph["nodes"] if n["group"] == "concept")
    print(f"==> 關聯圖：{ni} 篇 × {nc} 概念、{len(graph['edges'])} 連線")

    html_str = report.build_html(
        today, now, subjects, cc_items, now, moj_law, moj_news,
        config.REF_SITES, config.REF_TIPS, highlights, graph)
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
