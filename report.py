# -*- coding: utf-8 -*-
"""把每日聚合結果組成 HTML 申論實務雷達。"""
import html
import json
import datetime

import config

GRAPH_JS = r"""
const GRAPH = /*GRAPH*/;
function buildExamGraph(){
  if (window._examG || !window.vis) return; window._examG = true;
  const el = document.getElementById('exam-graph');
  if (!el || !GRAPH || !GRAPH.nodes.length) return;
  const nodes = GRAPH.nodes.map(function(n){
    if (n.group === 'concept') return {id:n.id, label:n.label, shape:'box',
      color:{background:'#2a1f3a', border:'#9a6cff'}, font:{color:'#d6c8ff', size:15}};
    if (n.group === 'subject') return {id:n.id, label:n.label, shape:'ellipse', margin:8,
      color:{background:'#3a2a12', border:'#ffce85'}, font:{color:'#ffe3b0', size:17}};
    return {id:n.id, label:n.label, shape:'dot', size:8,
      color:{background:'#7fb5ff', border:'#3a6ea5'}, font:{color:'#aeb6c2', size:11},
      url:n.url, title:n.title};
  });
  const data = {nodes:new vis.DataSet(nodes),
    edges:new vis.DataSet(GRAPH.edges.map(function(e){return {from:e.from, to:e.to, color:'#2a3340'};}))};
  const net = new vis.Network(el, data, {
    physics:{stabilization:true, barnesHut:{springLength:130, gravitationalConstant:-5000}},
    interaction:{hover:true}, nodes:{borderWidth:1}});
  net.on('click', function(p){ if (p.nodes.length){ const n = data.nodes.get(p.nodes[0]);
    if (n && n.url) window.open(n.url, '_blank'); }});
}
document.querySelectorAll('details.graphbox').forEach(function(d){
  d.addEventListener('toggle', function(){ if (d.open) buildExamGraph(); });
});
"""


def _new7(items):
    """近 NEW7_DAYS 天的項目數。"""
    today = datetime.date.today()
    n = 0
    for it in items:
        try:
            if (today - datetime.date.fromisoformat(it.get("date", ""))).days <= config.NEW7_DAYS:
                n += 1
        except ValueError:
            pass
    return n

NAV = """<nav class="topnav">
  <a href="https://elainechi-art.github.io/">🏠 首頁</a>
  <a href="https://elainechi-art.github.io/taiwan-stock-dashboard/">📈 股市儀表板</a>
  <a href="https://elainechi-art.github.io/research-radar/">📡 研究雷達</a>
  <a href="https://elainechi-art.github.io/judicial/">📚 司法官・律師複習</a>
  <a class="active" href="https://elainechi-art.github.io/exam-radar/">⚖️ 申論實務雷達</a>
</nav>"""


def _item(it):
    new = '<span class="new">🆕 NEW</span>' if it.get("is_new") else ""
    date = f'<span class="date">{html.escape(it["date"])}</span>' if it.get("date") else ""
    meta = f'<span class="src">{html.escape(it["meta"])}</span>' if it.get("meta") else ""
    summary = f'<p class="sum">{html.escape(it["summary"])}…</p>' if it.get("summary") else ""
    url = html.escape(it.get("url", "#"))
    return (f'<li><a href="{url}" target="_blank" rel="noopener">{html.escape(it["title"])}</a>'
            f'<div class="m">{new}{date}{meta}</div>{summary}</li>')


def _feed(items, empty="今日無新項目"):
    if not items:
        return f'<p class="empty">{empty}</p>'
    return f'<ul class="feed">{"".join(_item(i) for i in items)}</ul>'


def _cc_section(items, updated):
    """憲法法庭最新判決（整段，命題熱區）。"""
    if not items:
        body = '<p class="empty">暫無資料（每日自動更新）</p>'
    else:
        cards = "".join(
            f'<li><div class="jhead"><b>{html.escape(it["title"])}</b>'
            f'<span class="src">{html.escape(it["meta"])}　{html.escape(it["date"])}'
            f'{"　🆕" if it.get("is_new") else ""}</span></div>'
            f'<a class="more" href="{html.escape(it["url"])}" target="_blank" rel="noopener">看判決全文 →</a></li>'
            for it in items)
        body = f'<ul class="ccfeed">{cards}</ul>'
    return (f'<section class="topic cc" id="cons-court">'
            f'<h2><span class="tag hot">命題熱區</span>🏛️ 憲法法庭最新判決 '
            f'<span class="desc">違憲審查近年最常入題；點進看判決全文（更新 {html.escape(updated)}）</span></h2>'
            f'{body}</section>')


def _moj_section(law_items, news_items):
    cols = (
        f'<div class="col"><h3>📑 考科法律最新異動（全國法規）</h3>'
        f'{_feed(law_items, "近期無考科相關法律修正／公布（各科法律級修法另見下方各科「修法」欄）")}</div>'
        f'<div class="col"><h3>📰 法務部修法・政策新聞</h3>{_feed(news_items, "暫無相關新聞")}</div>'
    )
    return (f'<section class="topic" id="new-law">'
            f'<h2><span class="tag tw">官方</span>📋 新法規・修法動態 '
            f'<span class="desc">法務部官方 RSS · 剛修正／施行的條文＝命題熱點</span></h2>'
            f'<div class="cols cols2">{cols}</div></section>')


def _exam_tags(exams):
    out = ""
    for e in exams:
        cls = "t-mjib" if e.startswith("調查局") else "t-judge"
        out += f'<span class="etag {cls}">{html.escape(e)}</span>'
    return out


def _subject_section(s):
    def _h3(c):
        n = _new7(c["items"])
        badge = f'<span class="n7">🆕 {n}</span>' if n else ""
        return f'<h3>{html.escape(c["label"])}{badge}</h3>'
    cols = "".join(
        f'<div class="col">{_h3(c)}{_feed(c["items"])}</div>'
        for c in s.get("columns", []))
    return (f'<section class="topic" id="{html.escape(s["id"])}">'
            f'<h2>{html.escape(s["name"])} <span class="etags">{_exam_tags(s.get("exams", []))}</span>'
            f'<span class="desc">{html.escape(s["desc"])}</span></h2>'
            f'<div class="cols">{cols}</div></section>')


def _graph_section(graph):
    ni = sum(1 for n in graph.get("nodes", []) if n.get("group") == "item")
    nc = sum(1 for n in graph.get("nodes", []) if n.get("group") == "concept")
    if not ni:
        return ""
    return (f'<section class="topic gr" id="graph">'
            f'<h2><span class="tag hot">視覺化</span>🕸 申論關聯圖 '
            f'<span class="desc">{ni} 篇情報 × {nc} 個爭點概念；連線越多的爭點＝越熱。'
            f'點藍點開原文、拖曳可移動</span></h2>'
            f'<details class="graphbox"><summary>▶ 展開關聯圖（橘＝科目、紫＝爭點概念、藍＝新聞/判決）</summary>'
            f'<div class="graph" id="exam-graph"></div></details></section>')


def _highlights_section(items):
    if not items:
        body = '<p class="empty">近 14 天暫無新動態（每日自動更新）</p>'
    else:
        lis = "".join(
            f'<li><span class="schip">{html.escape(it.get("subj",""))}</span>'
            f'<a href="{html.escape(it.get("url","#"))}" target="_blank" rel="noopener">{html.escape(it["title"])}</a>'
            f'<span class="date">{html.escape(it.get("date",""))}</span></li>'
            for it in items)
        body = f'<ul class="hlfeed">{lis}</ul>'
    return (f'<section class="topic hl" id="highlights">'
            f'<h2><span class="tag hot">每日精選</span>🔥 近 14 天跨科最新動態 '
            f'<span class="desc">六科＋憲法法庭，依日期新到舊；先看這裡掌握本週命題熱訊</span></h2>'
            f'{body}</section>')


def _guide_section(sites, tips):
    tip_html = "".join(f"<li>{t}</li>" for t in tips)
    site_html = "".join(
        f'<li><a href="{html.escape(u)}" target="_blank" rel="noopener">{html.escape(n)}</a>'
        f'<span class="sum">{html.escape(d)}</span></li>'
        for n, u, d in sites)
    return (f'<section class="topic guide" id="guide">'
            f'<h2>📚 申論準備指南 <span class="desc">怎麼準備＋具參考價值的免費官方來源</span></h2>'
            f'<div class="cols cols2">'
            f'<div class="col"><h3>✍️ 申論高分重點（綜合上榜心得）</h3><ul class="tips">{tip_html}</ul></div>'
            f'<div class="col"><h3>🔗 推薦網站（找實務見解／查法規）</h3><ul class="sites">{site_html}</ul></div>'
            f'</div></section>')


def build_html(date_str, generated_at, subjects, cc_items, cc_updated,
               moj_law, moj_news, ref_sites, ref_tips, highlights=None, graph=None):
    graph = graph or {"nodes": [], "edges": []}
    toc = [("highlights", "🔥 近 14 天精選"), ("graph", "🕸 申論關聯圖"),
           ("guide", "📚 申論準備指南"), ("cons-court", "🏛️ 憲法法庭判決"),
           ("new-law", "📋 新法規動態")]
    toc += [(s["id"], s["name"]) for s in subjects]
    toc_html = "".join(
        f'<a href="#{html.escape(i)}">{html.escape(n)}</a>' for i, n in toc)

    sections = [_highlights_section(highlights or []),
                _graph_section(graph),
                _guide_section(ref_sites, ref_tips),
                _cc_section(cc_items, cc_updated),
                _moj_section(moj_law, moj_news)]
    sections += [_subject_section(s) for s in subjects]
    body = "\n".join(sections)

    graph_scripts = ""
    if any(n.get("group") == "item" for n in graph.get("nodes", [])):
        graph_scripts = (
            '<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>'
            "<script>" + GRAPH_JS.replace("/*GRAPH*/", json.dumps(graph, ensure_ascii=False)) + "</script>")

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>申論實務雷達 · 調查局／司法官律師二試 · {date_str}</title>
<style>
  * {{ box-sizing:border-box; }}
  html {{ scroll-behavior:smooth; }}
  body {{ font-family:-apple-system,"PingFang TC","Microsoft JhengHei",sans-serif;
         margin:0; background:#0c0e13; color:#e6e6e6; }}
  body::before {{ content:""; position:fixed; inset:0; z-index:-1; pointer-events:none;
    background:radial-gradient(1100px 560px at 75% -8%, rgba(180,120,70,.12), transparent 60%),
               radial-gradient(900px 520px at -5% 105%, rgba(70,110,160,.11), transparent 60%); }}
  .topnav {{ display:flex; gap:6px; background:#0b0d12; padding:8px 16px;
            border-bottom:1px solid #262b36; position:sticky; top:0; z-index:10; overflow-x:auto; }}
  .topnav a {{ color:#9aa4b2; text-decoration:none; font-size:14px; font-weight:600;
              padding:7px 16px; border-radius:8px; white-space:nowrap; }}
  .topnav a:hover {{ background:#161922; color:#e6e6e6; }}
  .topnav a.active {{ background:#2e2618; color:#ffce85; }}
  header {{ padding:26px 22px; background:linear-gradient(135deg,#241f17,#15161d 70%);
           border-bottom:1px solid #262b36; }}
  header h1 {{ margin:0; font-size:23px; letter-spacing:.5px;
             background:linear-gradient(90deg,#ffe3b0,#ffd0a8); -webkit-background-clip:text;
             background-clip:text; color:transparent; }}
  header p {{ margin:6px 0 0; color:#9aa4b2; font-size:13px; }}
  header .cd {{ display:inline-block; margin-top:8px; background:#2a2012; color:#ffce85;
              font-size:13px; font-weight:700; padding:4px 12px; border-radius:8px; }}
  .wrap {{ max-width:1320px; margin:0 auto; padding:18px 22px; }}
  .toc-trigger {{ position:fixed; left:0; top:50%; transform:translateY(-50%); z-index:40;
                 background:#161922; border:1px solid #2a3140; border-left:none;
                 border-radius:0 12px 12px 0; padding:16px 7px; cursor:pointer; color:#9aa4b2;
                 writing-mode:vertical-rl; letter-spacing:3px; font-size:12px; font-weight:600;
                 transition:.25s; box-shadow:4px 0 16px rgba(0,0,0,.3); }}
  .toc-trigger:hover {{ color:#fff; background:#1f2937; }}
  .toc {{ position:fixed; left:0; top:48px; height:calc(100vh - 48px); width:240px; z-index:41;
         background:rgba(17,20,27,.96); backdrop-filter:blur(12px); border-right:1px solid #2a3140;
         padding:16px 14px; overflow:auto; transform:translateX(-100%);
         transition:transform .32s cubic-bezier(.4,0,.2,1); box-shadow:10px 0 40px rgba(0,0,0,.5); }}
  .toc-trigger:hover + .toc, .toc:hover {{ transform:translateX(0); }}
  .toc a {{ display:block; color:#c3cad6; text-decoration:none; font-size:13.5px;
           padding:9px 10px; border-radius:9px; transition:.16s; }}
  .toc a:hover {{ background:#1f2937; color:#fff; transform:translateX(3px); }}
  .topic {{ background:linear-gradient(180deg,#171b24,#13161d); border:1px solid #262b36;
           border-radius:14px; padding:20px; margin-bottom:18px; scroll-margin-top:64px;
           animation:rise .5s both; }}
  .topic:hover {{ border-color:#39455f; }}
  @keyframes rise {{ from {{ opacity:0; transform:translateY(10px); }} to {{ opacity:1; transform:none; }} }}
  .topic.cc {{ border-color:#5a4626; background:linear-gradient(180deg,#1d1a12,#15161d); }}
  .topic.guide {{ border-color:#2a4a40; background:linear-gradient(180deg,#121d1a,#13161d); }}
  .topic.hl {{ border-color:#6a4a1e; background:linear-gradient(180deg,#211a10,#15161d); }}
  .topic.gr {{ border-color:#3a2a5a; background:linear-gradient(180deg,#161126,#13161d); }}
  .graphbox {{ margin-top:6px; }}
  .graphbox summary {{ cursor:pointer; color:#c79cff; font-size:14px; font-weight:600; padding:6px 0; }}
  .graph {{ height:560px; border:1px solid #262b36; border-radius:10px;
           background:#0c0f14; margin-top:10px; }}
  .hlfeed {{ list-style:none; margin:0; padding:0; display:grid;
            grid-template-columns:repeat(2,1fr); gap:8px 22px; }}
  .hlfeed li {{ font-size:13.5px; line-height:1.4; padding:6px 0;
               border-bottom:1px solid #221c10; display:flex; align-items:flex-start;
               gap:8px; flex-wrap:wrap; }}
  .hlfeed a {{ color:#ffe3b0; text-decoration:none; flex:1; min-width:60%; }}
  .hlfeed a:hover {{ text-decoration:underline; }}
  .schip {{ flex:none; font-size:11px; font-weight:700; padding:1px 8px; border-radius:999px;
           background:#2a2012; color:#ffce85; }}
  .topic h2 {{ margin:0 0 14px; font-size:18px; display:flex; align-items:center;
              flex-wrap:wrap; gap:8px; }}
  .desc {{ color:#7c8696; font-size:13px; font-weight:normal; flex-basis:100%; }}
  .tag {{ font-size:11px; font-weight:600; padding:2px 8px; border-radius:6px; }}
  .tag.tw {{ background:#1f2e3a; color:#7fb5ff; }}
  .tag.hot {{ background:#3a2a12; color:#ffce85; }}
  .etags {{ display:inline-flex; gap:5px; flex-wrap:wrap; }}
  .etag {{ font-size:11px; font-weight:600; padding:2px 8px; border-radius:999px; }}
  .etag.t-mjib {{ background:#2a1d2e; color:#e0a0ff; }}
  .etag.t-judge {{ background:#16302a; color:#6fe0b0; }}
  .cols {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }}
  .cols.cols2 {{ grid-template-columns:repeat(2,1fr); }}
  .col h3 {{ font-size:14px; color:#9aa4b2; margin:0 0 8px;
            border-bottom:1px solid #262b36; padding-bottom:6px;
            display:flex; align-items:center; justify-content:space-between; gap:6px; }}
  .n7 {{ flex:none; background:#3a2a12; color:#ffce85; font-size:10.5px; font-weight:700;
        padding:1px 7px; border-radius:999px; }}
  .feed {{ list-style:none; margin:0; padding:0 8px 0 0; max-height:430px; overflow-y:auto; }}
  .feed li {{ margin:0 0 14px; font-size:13.5px; line-height:1.45; transition:transform .15s; }}
  .feed li:hover {{ transform:translateX(2px); }}
  .feed::-webkit-scrollbar, .ccfeed::-webkit-scrollbar, .toc::-webkit-scrollbar {{ width:8px; }}
  .feed::-webkit-scrollbar-thumb, .ccfeed::-webkit-scrollbar-thumb,
  .toc::-webkit-scrollbar-thumb {{ background:#2a3340; border-radius:5px; }}
  .feed a {{ color:#ffce85; text-decoration:none; }}
  .feed a:hover {{ color:#ffe3b0; text-decoration:underline; }}
  .m {{ margin-top:3px; }}
  .new {{ background:#3a2a12; color:#ffce85; font-size:10px; font-weight:700;
         padding:1px 6px; border-radius:5px; margin-right:6px; }}
  .date {{ color:#8a93a3; font-size:11px; margin-right:8px; }}
  .src {{ color:#7c8696; font-size:11px; }}
  .sum {{ color:#aeb6c2; font-size:12.5px; margin:5px 0 0; display:block; }}
  .empty {{ color:#6b7280; font-size:13px; }}
  .ccfeed {{ list-style:none; margin:0; padding:0; display:grid;
            grid-template-columns:repeat(3,1fr); gap:12px; max-height:none; }}
  .ccfeed li {{ background:#161922; border:1px solid #2a2417; border-radius:10px; padding:12px; }}
  .ccfeed .jhead b {{ font-size:14px; color:#ffe3b0; }}
  .ccfeed .src {{ display:block; margin-top:4px; }}
  .ccfeed .more {{ display:inline-block; margin-top:8px; color:#ffce85; font-size:12px;
                  text-decoration:none; }}
  .ccfeed .more:hover {{ text-decoration:underline; }}
  .tips {{ margin:0; padding-left:18px; font-size:13.5px; line-height:1.6; color:#cdd5e0; }}
  .tips li {{ margin-bottom:9px; }}
  .tips b {{ color:#9ee6c0; }}
  .sites {{ list-style:none; margin:0; padding:0; }}
  .sites li {{ margin-bottom:12px; font-size:13.5px; }}
  .sites a {{ color:#7fd0ff; text-decoration:none; font-weight:600; }}
  .sites a:hover {{ text-decoration:underline; }}
  footer {{ text-align:center; color:#6b7280; font-size:12px; padding:24px; }}
  @media (max-width:980px) {{ .cols, .cols.cols2, .ccfeed, .hlfeed {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
{NAV}
<header>
  <h1>⚖️ 申論實務雷達 · 調查局法律實務組 ／ 司法官・律師第二試</h1>
  <p>每天自動抓「最新實務見解（大法庭／最高法院／憲法法庭）＋新法規／修法」＝申論命題熱區</p>
  <p>資料日期：{date_str}　·　產生時間：{generated_at}　·　🆕 = 近 30 天</p>
  <div class="cd" id="countdown">倒數計算中…</div>
</header>
<div class="toc-trigger" aria-hidden="true">☰ 目錄</div>
<aside class="toc"><div style="font-size:12px;color:#7c8696;margin-bottom:10px;font-weight:600">章節目錄</div>{toc_html}</aside>
<div class="wrap">
{body}
</div>
<footer>聚合 Google News、法務部官方 RSS、憲法法庭判決 · 供考試準備參考，引用前請以官方全文為準</footer>
<script>
  // 考試倒數：調查局 2026-08-08、律師司法官二試（二試約 2026-12 月，暫以一試 08-01 提示）
  (function(){{
    var targets=[["調查局","2026-08-08"],["司法官律師一試","2026-08-01"]];
    var now=new Date(); var out=[];
    targets.forEach(function(t){{
      var d=Math.ceil((new Date(t[1])-now)/864e5);
      if(d>=0) out.push(t[0]+" 倒數 "+d+" 天");
    }});
    document.getElementById('countdown').textContent = out.join("　·　") || "考試已開始，加油！";
  }})();
</script>
{graph_scripts}
</body>
</html>"""
