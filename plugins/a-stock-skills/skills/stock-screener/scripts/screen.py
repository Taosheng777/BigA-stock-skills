# SENTINEL_SCREEN_C1
"""stock-screener 核心逻辑（stdlib-only）。MVP: 清洗 → rank百分位归一 → 加权 → TopN。
纯逻辑（parse/score/dedup/render）+ 数据访问（fetch 翻页/load_holdings）+ CLI 编排。"""

import json
import os
import re
import subprocess
import sys


CLI_PATH = os.path.expanduser(
    "~/.claude/skills/hithink-market-query/scripts/cli.py"
)
HOLDINGS_PATH = os.path.expanduser(os.environ.get(
    "STOCK_SCREENER_HOLDINGS",
    "~/Documents/投资笔记/03-持仓跟踪/持仓.md",
))
OUT_DIR = os.path.expanduser(os.environ.get(
    "STOCK_SCREENER_OUT_DIR",
    "~/Documents/投资笔记/选股名单",
))


class ScreenError(Exception):
    """取数/编排阶段的可预期错误（额度不足、cli.py 非 JSON 输出等）。"""


def parse_value(v):
    """问财字段值 → float。裸数字直接用；'万/亿' 换算；'%' 保留量级；无法解析 → None。"""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if not isinstance(v, str):
        return None
    s = v.strip().replace(",", "").replace("，", "")
    if not s:
        return None
    mult = 1.0
    if s.endswith("%"):
        s = s[:-1]
    elif s.endswith("万"):
        mult, s = 1e4, s[:-1]
    elif s.endswith("亿"):
        mult, s = 1e8, s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return None


def normalize_field_name(key):
    """剥掉问财字段的 '@' 前缀、'[日期]' 后缀、':子标记'，得到标准字段名。"""
    if not isinstance(key, str):
        return key
    k = key.strip()
    if k.startswith("@"):
        k = k[1:]
    i = k.find("[")
    if i != -1:
        k = k[:i]
    return k.split(":")[0].strip()


def pick_value(record, stdname):
    """在同名多变体（@版/无@版/带子标记）里取第一个非空数值。"""
    for k, v in record.items():
        if normalize_field_name(k) == stdname:
            pv = parse_value(v)
            if pv is not None:
                return pv
    return None


def rank_percentile(values):
    """截面排序百分位 → [0,1]；None 保持 None；并列取平均；单值记 0.5（中性）。"""
    idx = [i for i, v in enumerate(values) if v is not None]
    out = [None] * len(values)
    n = len(idx)
    if n == 0:
        return out
    if n == 1:
        out[idx[0]] = 0.5
        return out
    order = sorted(idx, key=lambda i: values[i])
    j = 0
    while j < n:
        k = j
        while k + 1 < n and values[order[k + 1]] == values[order[j]]:
            k += 1
        pct = ((j + k) / 2.0) / (n - 1)
        for t in range(j, k + 1):
            out[order[t]] = pct
        j = k + 1
    return out


def score(pool, fields):
    """fields: [(stdname, weight, direction)]，direction ∈ {'higher','lower'}。
    返回 [{'record','score','parts'}]；某只缺某字段→按已用权重重归一；整列缺失自然不计。"""
    cols = {}
    for stdname, weight, direction in fields:
        raw = [pick_value(rec, stdname) for rec in pool]
        pct = rank_percentile(raw)
        if direction == "lower":
            pct = [(1.0 - p) if p is not None else None for p in pct]
        cols[stdname] = pct
    results = []
    for i, rec in enumerate(pool):
        wsum = 0.0
        applied = 0.0
        parts = {}
        for stdname, weight, direction in fields:
            p = cols[stdname][i]
            parts[stdname] = p
            if p is not None:
                wsum += p * weight
                applied += weight
        sval = (wsum / applied * 100.0) if applied > 0 else None
        results.append({"record": rec, "score": sval, "parts": parts})
    return results


def _code6(c):
    """取 6 位代码前缀用于匹配：'002415.SZ' → '002415'。"""
    if not isinstance(c, str):
        return None
    return c.split(".")[0].strip()


def dedup(pool, code_key="股票代码"):
    """按 6 位代码去重，保留首次出现。"""
    seen = set()
    out = []
    for rec in pool:
        c = _code6(rec.get(code_key))
        if c in seen:
            continue
        seen.add(c)
        out.append(rec)
    return out


def exclude_holdings(pool, holding_codes, code_key="股票代码"):
    """剔除已持仓（6 位代码匹配，兼容带/不带交易所后缀）。"""
    hold = {_code6(c) for c in (holding_codes or [])}
    return [rec for rec in pool if _code6(rec.get(code_key)) not in hold]


def render_html(results, meta):
    """渲染可排序 HTML 名单。results: [{'record','score','parts'}]；外部值一律 escape。"""
    import html as H

    title = H.escape(str(meta.get("title", "选股名单")))
    date = H.escape(str(meta.get("date", "")))
    sources = H.escape(str(meta.get("sources", "同花顺问财")))
    ordered = sorted(
        results,
        key=lambda r: (r.get("score") is not None, r.get("score") or 0.0),
        reverse=True,
    )
    rows = []
    for rank, item in enumerate(ordered, 1):
        rec = item.get("record", {})
        code = H.escape(str(rec.get("股票代码", "")))
        name = H.escape(str(rec.get("股票简称", "")))
        sc = item.get("score")
        sc_txt = "-" if sc is None else "%.1f" % sc
        tmpl = H.escape(str(rec.get("命中模板", meta.get("title", ""))))
        parts = item.get("parts", {}) or {}
        parts_txt = H.escape(
            " ".join("%s=%.2f" % (k, v) for k, v in parts.items() if v is not None)
        )
        rows.append(
            "<tr><td>%d</td><td>%s</td><td>%s</td><td class='score'>%s</td>"
            "<td>%s</td><td class='parts'>%s</td></tr>"
            % (rank, code, name, sc_txt, tmpl, parts_txt)
        )
    rows_html = "\n".join(rows)
    return """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>%s · 选股名单 %s</title>
<style>
body{font-family:-apple-system,system-ui,sans-serif;margin:24px;color:#1a1a1a}
h1{font-size:20px}
table{border-collapse:collapse;width:100%%;font-size:14px}
th,td{border:1px solid #ddd;padding:6px 10px;text-align:left}
th{background:#f5f5f5;cursor:pointer}
.score{font-weight:600;color:#c0392b}
.parts{color:#666;font-size:12px}
footer{margin-top:16px;color:#888;font-size:12px}
</style></head><body>
<h1>%s · 选股名单 <small>%s</small></h1>
<table id="t">
<thead><tr><th>#</th><th>代码</th><th>名称</th><th>综合分</th><th>命中模板</th><th>分项贡献(rank)</th></tr></thead>
<tbody>
%s
</tbody></table>
<footer>研究分析，非持牌投顾建议，风险自担。数据来源：%s，数据日 %s。</footer>
<script>
document.querySelectorAll('#t th').forEach((th,i)=>th.addEventListener('click',()=>{
 const tb=th.closest('table').tBodies[0], rows=[...tb.rows], num=(i===0||i===3);
 rows.sort((a,b)=>{const x=a.cells[i].innerText,y=b.cells[i].innerText;
  return num?(parseFloat(y)||0)-(parseFloat(x)||0):x.localeCompare(y,'zh');});
 rows.forEach(r=>tb.appendChild(r));
}));
</script>
</body></html>""" % (title, date, title, date, rows_html, sources, date)


# ---- 策略模板库（命名 + 问财问句 + 打分字段权重）。字段名为 normalize 后的标准名 ----

PRESETS = {
    "放量突破": {
        "title": "放量突破",
        # 行情类展示词缀（换手率/市盈率/市净率）已移除：打分列由腾讯 enrichment 覆盖
        "query": (
            "今日放量突破20日新高 近5日涨幅小于15% 近一年归母净利润同比增长 "
            "主力资金流向 净资产收益率 非ST 非创业板 非北交所"
        ),
        "fields": [
            ("最新涨跌幅", 0.20, "higher"),
            ("换手率", 0.15, "higher"),
            ("主力资金流向", 0.25, "higher"),
            ("归母净利润同比增长率", 0.15, "higher"),
            ("净资产收益率", 0.15, "higher"),
            ("最新市盈率ttm", 0.05, "lower"),
            ("最新市净率", 0.05, "lower"),
        ],
    },
    "低位反转": {
        "title": "低位反转",
        "query": (
            "近一年涨跌幅小于-20% 股价站上5日均线 "
            "主力资金流向 非ST 非北交所"
        ),
        "fields": [
            ("最新涨跌幅", 0.30, "higher"),
            ("换手率", 0.20, "higher"),
            ("主力资金流向", 0.30, "higher"),
            ("最新市净率", 0.20, "lower"),
        ],
    },
    "业绩成长": {
        "title": "业绩成长",
        "query": (
            "近一年归母净利润同比增长大于30% 营业收入同比增长 净资产收益率大于10% "
            "市盈率小于40 非ST 非北交所"
        ),
        "fields": [
            ("归母净利润同比增长率", 0.30, "higher"),
            ("营业收入同比增长率", 0.25, "higher"),
            ("净资产收益率", 0.20, "higher"),
            ("最新市盈率ttm", 0.15, "lower"),
            ("最新市净率", 0.10, "lower"),
        ],
    },
    "主力异动": {
        "title": "主力异动",
        "query": (
            "主力资金连续3日净流入 今日放量 "
            "主力资金流向 资金流入 非ST 非北交所"
        ),
        "fields": [
            ("主力资金流向", 0.40, "higher"),
            ("资金流入", 0.20, "higher"),
            ("换手率", 0.20, "higher"),
            ("最新涨跌幅", 0.20, "higher"),
        ],
    },
}

# 自由口述（无模板）时的通用打分字段：动量 + 资金 + 质量
DEFAULT_FIELDS = [
    ("最新涨跌幅", 0.25, "higher"),
    ("换手率", 0.15, "higher"),
    ("主力资金流向", 0.25, "higher"),
    ("归母净利润同比增长率", 0.15, "higher"),
    ("净资产收益率", 0.20, "higher"),
]


def get_preset(name):
    """按名取模板；未知名抛 KeyError 并列出可用模板。"""
    if name not in PRESETS:
        raise KeyError("未知模板：%s。可用：%s" % (name, "、".join(PRESETS)))
    return PRESETS[name]


# ---- 数据访问层 ----

# 6 位 A 股/ETF/北交所代码，可带 .SZ/.SH/.BJ 后缀；前后不接数字、前不接小数点（避免命中小数尾数）
_HOLDING_CODE_RE = re.compile(
    r"(?<![\d.])(\d{6})(?:\.(?:SZ|SH|BJ|sz|sh|bj))?(?!\d)"
)


def load_holdings(path):
    """只读 stock-buddy 的持仓 md，抽出 6 位代码（去重保序）。文件缺失 → []。"""
    try:
        with open(os.path.expanduser(path), encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return []
    seen = set()
    out = []
    for m in _HOLDING_CODE_RE.finditer(text):
        c = m.group(1)
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _brief(doc):
    try:
        return json.dumps(doc, ensure_ascii=False)[:200]
    except (TypeError, ValueError):
        return str(doc)[:200]


def _subprocess_runner(query, page, page_limit, cli_path=None, timeout=45):
    """调 hithink cli.py 取一页，解析其 stdout JSON。API Key 由 cli.py 从 env 读，本层不碰。"""
    cli_path = cli_path or CLI_PATH
    proc = subprocess.run(
        [sys.executable, cli_path, "--query", query,
         "--page", str(page), "--limit", str(page_limit)],
        capture_output=True, text=True, timeout=timeout,
    )
    out = (proc.stdout or "").strip()
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        raise ScreenError(
            "cli.py 未返回 JSON（rc=%d）：%s"
            % (proc.returncode, (proc.stderr or out or "<空>")[:300])
        )


def fetch_pool(query, max_records=100, page_limit=50, runner=None):
    """按 has_more 翻页抓全池子（带上限）。runner 可注入用于离线测试。
    返回 record 列表；某页缺 datas（额度不足等）→ ScreenError。"""
    run = runner or _subprocess_runner
    pool = []
    page = 1
    max_pages = max(1, (max_records + page_limit - 1) // page_limit) + 2
    while len(pool) < max_records and page <= max_pages:
        doc = run(query, page, page_limit)
        if not isinstance(doc, dict) or "datas" not in doc:
            raise ScreenError(
                "问财返回缺少 datas（可能额度不足/查询超限）：%s" % _brief(doc)
            )
        datas = doc.get("datas") or []
        pool.extend(datas)
        if not datas or not doc.get("has_more"):
            break
        page += 1
    return pool[:max_records]


# ---- 行情打分列 enrichment（腾讯批量 · T3 增强层 · 2026-07-15 加）----
# 目的：换手率/涨跌幅/PE/PB 等行情打分列不再依赖问财"词缀下发"（漏列即综合分落空），
# 改由腾讯行情批量覆盖（零额度、全池一两次请求）。腾讯失败→保留问财原值并标记，
# 打分按既有"缺列重归一"口径降级，不熔断、不编数据。资金/财务列仍走问财。

TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q="
# 腾讯 ~ 分隔载荷字段索引 → 打分标准字段名（索引实测校准 2026-07）
TENCENT_FIELD_INDEX = {
    "最新涨跌幅": 32,
    "换手率": 38,
    "最新市盈率ttm": 39,
    "最新市净率": 46,
}
ENRICH_FIELDS = tuple(TENCENT_FIELD_INDEX)
# 腾讯对亏损股/ETF 的比率字段给 0.00 作"无值"哨兵；直接采用会把亏损股按
# 'lower' 方向排成"估值最优"，必须转 None（打分层按缺失重归一）。
TENCENT_ZERO_IS_NONE = ("最新市盈率ttm", "最新市净率")

_TENCENT_CODE_RE = re.compile(r"^(\d{6})(?:\.(SZ|SH|BJ))?$", re.IGNORECASE)


def tencent_prefix(code):
    """'002415.SZ'→'sz002415'。优先用问财返回的交易所后缀；裸码按首位判：
    6/9/5→sh（5 开头是沪市基金/ETF，判 sz 是已知坑）、8/4→bj、其余→sz。无法识别→None。"""
    if not isinstance(code, str):
        return None
    m = _TENCENT_CODE_RE.match(code.strip())
    if not m:
        return None
    six, suf = m.group(1), (m.group(2) or "").lower()
    if suf:
        return suf + six
    if six[0] in "695":
        return "sh" + six
    if six[0] in "84":
        return "bj" + six
    return "sz" + six


def parse_tencent_payload(text):
    """腾讯 GBK 载荷 → {6位代码: {标准字段名: float}}。短行/坏行跳过。"""
    out = {}
    for line in (text or "").strip().split(";"):
        if "=" not in line or '"' not in line:
            continue
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        code6 = vals[2].strip()
        if not code6:
            continue
        row = {}
        for std, idx in TENCENT_FIELD_INDEX.items():
            v = parse_value(vals[idx])
            if v == 0.0 and std in TENCENT_ZERO_IS_NONE:
                v = None
            row[std] = v
        out[code6] = row
    return out


def fetch_tencent_quotes(prefixed_codes, timeout=10, chunk=50):
    """批量拉腾讯行情（stdlib urllib，GBK）。prefixed_codes 为 tencent_prefix 结果。"""
    import urllib.request

    got = {}
    codes = [c for c in prefixed_codes if c]
    for i in range(0, len(codes), chunk):
        url = TENCENT_QUOTE_URL + ",".join(codes[i: i + chunk])
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            got.update(parse_tencent_payload(resp.read().decode("gbk", "replace")))
    return got


def enrich_records(pool, code_key="股票代码", fetcher=None):
    """行情打分列改源：腾讯值覆盖问财同名列（逐列删旧变体再写标准名）。
    腾讯缺某票→该票保留问财原值；整体失败→原样返回并在 info 标记（T3 增强层，降级不熔断）。
    返回 (pool, info)，info={'enriched','hit','note'}。"""
    fetch = fetcher or fetch_tencent_quotes
    prefixed = [tencent_prefix(rec.get(code_key)) for rec in pool]
    try:
        quotes = fetch([p for p in prefixed if p])
    except Exception as e:
        return pool, {"enriched": False, "hit": 0,
                      "note": "腾讯行情获取失败，打分退回问财返回列：%s" % e}
    hit = 0
    for rec in pool:
        row = quotes.get(_code6(rec.get(code_key)))
        if not row:
            continue
        hit += 1
        for std in ENRICH_FIELDS:
            v = row.get(std)
            if v is None:
                continue
            for k in [k for k in list(rec) if normalize_field_name(k) == std]:
                del rec[k]
            rec[std] = v
    return pool, {"enriched": True, "hit": hit,
                  "note": "行情打分列（%s）由腾讯批量覆盖 %d/%d 只"
                          % ("/".join(ENRICH_FIELDS), hit, len(pool))}


# ---- 编排：dedup → 排除持仓 → 打分 → 排序 → TopN ----

def screen_pool(pool, fields, holding_codes=None, top=15):
    pool = dedup(pool)
    pool = exclude_holdings(pool, holding_codes)
    scored = score(pool, fields)
    ordered = sorted(
        scored,
        key=lambda r: (r["score"] is not None, r["score"] or 0.0),
        reverse=True,
    )
    return ordered[: top] if top and top > 0 else ordered


def build_listing(pool, fields, holding_codes=None, top=15, meta=None):
    """跑完整管线，返回 {meta, results(精简投影), html}。results 供对话内回名单。"""
    meta = meta or {}
    ordered = screen_pool(pool, fields, holding_codes, top)
    results = []
    for item in ordered:
        rec = item["record"]
        sc = item["score"]
        parts = {
            k: (round(v, 3) if v is not None else None)
            for k, v in (item.get("parts") or {}).items()
        }
        results.append({
            "code": rec.get("股票代码", ""),
            "name": rec.get("股票简称", ""),
            "score": (round(sc, 1) if sc is not None else None),
            "parts": parts,
        })
    return {"meta": meta, "results": results, "html": render_html(ordered, meta)}


# ---- CLI ----

def _safe_filename(s):
    return re.sub(r"[^\w一-鿿-]+", "", str(s)) or "选股"


def main(argv=None):
    import argparse
    import datetime

    ap = argparse.ArgumentParser(
        description="问财选股：筛池子 + 数据化打分排序（只筛不分析，深度研判交 stock-buddy）"
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--preset", choices=list(PRESETS), help="命中模板名")
    g.add_argument("--query", help="自由口述的问财问句")
    ap.add_argument("--top", type=int, default=15, help="输出 Top-N（默认 15）")
    ap.add_argument("--max-records", type=int, default=100, help="抓取上限（默认 100）")
    ap.add_argument("--page-limit", type=int, default=50, help="每页条数（默认 50）")
    ap.add_argument("--no-enrich", action="store_true",
                    help="跳过腾讯行情打分列覆盖（降级：打分退回问财返回列）")
    ap.add_argument("--no-exclude-holdings", action="store_true", help="不排除已持仓")
    ap.add_argument("--holdings-path", default=HOLDINGS_PATH)
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--date", default=None, help="数据日（默认今天）")
    args = ap.parse_args(argv)

    if args.preset:
        preset = get_preset(args.preset)
        title, query, fields = preset["title"], preset["query"], preset["fields"]
    else:
        title, query, fields = "自选", args.query, DEFAULT_FIELDS

    date = args.date or datetime.date.today().isoformat()
    exclude = not args.no_exclude_holdings
    holdings = load_holdings(args.holdings_path) if exclude else []
    holdings_missing = exclude and not os.path.exists(os.path.expanduser(args.holdings_path))

    try:
        pool = fetch_pool(query, max_records=args.max_records, page_limit=args.page_limit)
    except (ScreenError, subprocess.TimeoutExpired) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1

    if args.no_enrich:
        enrich_info = {"enriched": False, "hit": 0, "note": "--no-enrich 跳过"}
    else:
        pool, enrich_info = enrich_records(pool)
    sources = ("同花顺问财（筛选/资金/财务）+ 腾讯行情（行情打分列）"
               if enrich_info["enriched"] else "同花顺问财")

    listing = build_listing(
        pool, fields, holding_codes=holdings, top=args.top,
        meta={"title": title, "date": date, "sources": sources},
    )

    out_dir = os.path.expanduser(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    html_path = os.path.join(out_dir, "%s-%s.html" % (date, _safe_filename(title)))
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(listing["html"])

    print(json.dumps({
        "ok": True,
        "title": title,
        "query": query,
        "date": date,
        "fetched": len(pool),
        "returned": len(listing["results"]),
        "holdings_excluded": len(holdings),
        "holdings_missing": holdings_missing,
        "enrich": enrich_info,
        "html_path": html_path,
        "top": listing["results"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
