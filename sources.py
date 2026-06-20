# -*- coding: utf-8 -*-
"""資料源抓取器：Google News、官方 RSS（法務部）、憲法法庭判決（爬蟲）。

全部免金鑰。每個函式回傳 list[dict]，欄位統一：
  {title, url, date, meta, summary, is_new, _sort}
台灣政府網站（cons.judicial / moj）憑證常缺 Subject Key Identifier，
新版 OpenSSL 會驗證失敗，故官方來源一律用「不驗證」的 SSL context 抓取。
"""
import re
import ssl
import html as _html
import datetime
import urllib.parse
import urllib.request

import config

UA = {"User-Agent": "Mozilla/5.0 (exam-radar; legal exam aggregator)"}
TODAY = datetime.date.today()
NEW_DAYS = getattr(config, "NEW_DAYS", 30)

# 略過驗證的 SSL context（給台灣政府網站用）
_LAX = ssl.create_default_context()
_LAX.check_hostname = False
_LAX.verify_mode = ssl.CERT_NONE


def _fetch_bytes(url, lax=False, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    ctx = _LAX if lax else None
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.read()


def _clean(text, limit=None):
    t = _html.unescape(re.sub(r"<[^>]+>", "", text or ""))
    t = re.sub(r"\s+", " ", t).strip()
    return (t[:limit].rstrip() if limit and len(t) > limit else t)


def _parse_date(s):
    if not s:
        return "", None
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            d = datetime.datetime.strptime(s, fmt)
            return d.strftime("%Y-%m-%d"), d.date()
        except ValueError:
            continue
    return s[:10], None


def _is_new(d):
    return bool(d and 0 <= (TODAY - d).days <= NEW_DAYS)


def _entry_date(e):
    for k in ("published_parsed", "updated_parsed"):
        t = e.get(k)
        if t:
            try:
                return datetime.date(t.tm_year, t.tm_mon, t.tm_mday)
            except Exception:
                pass
    _, d = _parse_date(e.get("published", "") or e.get("updated", ""))
    return d


def _mk(title, url, d, meta, summary):
    ds = d.strftime("%Y-%m-%d") if d else ""
    return {"title": _clean(title), "url": url or "", "date": ds,
            "meta": _clean(meta), "summary": _clean(summary, 200), "is_new": _is_new(d),
            "_sort": ds or "0000-00-00"}


def fetch_news(query, lang="zh", limit=8):
    """Google News RSS 搜尋（免金鑰、穩定）。"""
    import feedparser
    q = urllib.parse.quote(query)
    if lang == "zh":
        url = f"https://news.google.com/rss/search?q={q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    else:
        url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url)
    out = []
    for e in feed.entries[:limit]:
        src = e.get("source", {}).get("title", "") if e.get("source") else ""
        out.append(_mk(e.get("title"), e.get("link"), _entry_date(e), src, ""))
    return out


def fetch_rss(url, limit=8, source_name="", lax=False, keywords=None):
    """通用 RSS（官方新聞／法規）。lax＝略過 SSL 驗證；keywords＝標題過濾。"""
    import feedparser
    try:
        raw = _fetch_bytes(url, lax=lax)
    except Exception as e:
        print(f"     RSS 取得失敗 {source_name or url}: {e}")
        return []
    feed = feedparser.parse(raw)
    name = source_name or _clean(feed.feed.get("title", ""))
    out = []
    for e in feed.entries:
        title = e.get("title", "")
        if keywords and not any(k in title for k in keywords):
            continue
        summary = e.get("summary", "") or (e.get("content", [{}])[0].get("value", "")
                                           if e.get("content") else "")
        out.append(_mk(title, e.get("link"), _entry_date(e), name, summary))
        if len(out) >= limit:
            break
    return out


def fetch_constitutional_court(url, limit=15):
    """憲法法庭判決列表（靜態 HTML）：解析日期＋字號＋案由。"""
    try:
        html = _fetch_bytes(url, lax=True).decode("utf-8", "replace")
    except Exception as e:
        print(f"     憲法法庭取得失敗：{e}")
        return []
    pat = re.compile(
        r'class="cont">\s*(\d{4}-\d{2}-\d{2})\s*</div>\s*</li>\s*<li>\s*'
        r'<span>判決字號</span>\s*<div class="cont"[^>]*>\s*'
        r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', re.S)
    base = "https://cons.judicial.gov.tw/"
    out, seen = [], set()
    for ds, href, text in pat.findall(html):
        text = _html.unescape(text).strip()
        if text in seen:
            continue
        seen.add(text)
        link = href if href.startswith("http") else base + href.lstrip("/")
        # 拆「115年憲判字第5號【案由】」→ 標題用案由、字號放 meta
        m = re.match(r"(.+?號)\s*【(.+?)】", text)
        no = m.group(1) if m else text
        title = m.group(2) if m else text
        _, d = _parse_date(ds)
        out.append(_mk(title, link, d, no, ""))
        if len(out) >= limit:
            break
    return out
