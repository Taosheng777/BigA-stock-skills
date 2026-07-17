#!/usr/bin/env python3
"""stock-buddy 常规档 · 个股危险信号扫描(五项:解禁/公告/融资融券/互动易/新闻)

用法:
    python3 danger_scan.py 002049 600036 [--date 2026-07-15] [--json out.json]

- 仅扫 A 股个股(0/3/6 开头 6 位代码);ETF/指数自动跳过(五项情报不适用)。
- 数据源均为 T3(东财/巨潮爬取,a-stock-data V3.4 口径):数字不入台账,
  与 T1(hithink-finance)冲突时以 T1 为准;引用须标注来源+日期。
- 新闻端点存在东财间歇风控(#18):失败输出"未跑",禁止当"无新闻"或推断补数。
- 东财请求内置 ≥1s 串行节流,勿并发改造。
"""
import argparse
import json
import random
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta

import requests

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
RISK_KW = ["减持", "质押", "冻结", "问询", "关注函", "监管", "立案", "处罚",
           "辞职", "离任", "预亏", "下修", "诉讼", "仲裁", "违规", "警示", "退市"]

EM_SESSION = requests.Session()
EM_SESSION.headers.update({"User-Agent": UA})
try:
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    _adapter = HTTPAdapter(max_retries=Retry(
        total=3, connect=3, backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"]))
    EM_SESSION.mount("https://", _adapter)
    EM_SESSION.mount("http://", _adapter)
except Exception:
    pass
EM_MIN_INTERVAL = 1.0
_last = [0.0]


def em_get(url, params=None, headers=None, timeout=15):
    wait = EM_MIN_INTERVAL - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.5))
    try:
        return EM_SESSION.get(url, params=params, headers=headers, timeout=timeout)
    finally:
        _last[0] = time.time()


def datacenter(report, filter_str="", page_size=50, sort_columns="", sort_types="-1"):
    r = em_get(DATACENTER_URL, params={
        "reportName": report, "columns": "ALL", "filter": filter_str,
        "pageNumber": "1", "pageSize": str(page_size),
        "sortColumns": sort_columns, "sortTypes": sort_types,
        "source": "WEB", "client": "WEB"})
    d = r.json()
    return d["result"]["data"] if d.get("result") and d["result"].get("data") else []


def lockup(code, trade_date, forward_days=90):
    end = (datetime.strptime(trade_date, "%Y-%m-%d")
           + timedelta(days=forward_days)).strftime("%Y-%m-%d")
    rows = datacenter("RPT_LIFT_STAGE",
        f'(SECURITY_CODE="{code}")(FREE_DATE>=\'{trade_date}\')(FREE_DATE<=\'{end}\')',
        20, "FREE_DATE", "1")
    return [{"date": str(r.get("FREE_DATE", ""))[:10],
             "type": r.get("FREE_SHARES_TYPE", ""),
             "shares_wan": r.get("FREE_SHARES", 0),
             "ratio_pct": (r.get("FREE_RATIO") or 0) * 100} for r in rows]


_ORGID = {}


def _orgid(code):
    global _ORGID
    if not _ORGID:
        try:
            r = requests.get("http://www.cninfo.com.cn/new/data/szse_stock.json",
                             headers={"User-Agent": UA}, timeout=15)
            _ORGID = {s["code"]: s["orgId"] for s in r.json().get("stockList", [])}
        except Exception as e:
            print(f"[WARN] 巨潮 orgId 映射失败,回退硬编码: {e}", file=sys.stderr)
    if code in _ORGID:
        return _ORGID[code]
    return ("gssh0" if code.startswith("6") else
            "gsbj0" if code.startswith(("8", "4")) else "gssz0") + code


def announcements(code, since_date, page_size=30):
    r = requests.post("https://www.cninfo.com.cn/new/hisAnnouncement/query",
        data={"stock": f"{code},{_orgid(code)}", "tabName": "fulltext",
              "pageSize": str(page_size), "pageNum": "1", "column": "", "category": "",
              "plate": "", "seDate": "", "searchkey": "", "secid": "",
              "sortName": "", "sortType": "", "isHLtitle": "true"},
        headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded",
                 "Referer": "https://www.cninfo.com.cn/new/disclosure",
                 "Origin": "https://www.cninfo.com.cn"}, timeout=15).json()
    out = []
    for i in r.get("announcements", []) or []:
        ts = i.get("announcementTime")
        date = (datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
                if isinstance(ts, (int, float)) else str(ts)[:10])
        if date < since_date:
            continue
        title = i.get("announcementTitle", "")
        out.append({"date": date, "title": title,
                    "flags": [k for k in RISK_KW if k in title]})
    return out


def margin(code, page_size=25):
    rows = datacenter("RPTA_WEB_RZRQ_GGMX", f'(SCODE="{code}")',
                      page_size, "DATE", "-1")
    rows = [{"date": str(r.get("DATE", ""))[:10], "rzye": r.get("RZYE", 0)} for r in rows]
    if len(rows) < 21 or not rows[5]["rzye"] or not rows[20]["rzye"]:
        return {"rows": rows[:3], "trend": None}
    return {"rows": rows[:3], "trend": {
        "date": rows[0]["date"], "rzye_yi": rows[0]["rzye"] / 1e8,
        "chg5_pct": (rows[0]["rzye"] - rows[5]["rzye"]) / rows[5]["rzye"] * 100,
        "chg20_pct": (rows[0]["rzye"] - rows[20]["rzye"]) / rows[20]["rzye"] * 100}}


def irm(code, since_date, page_size=15):
    try:
        d1 = requests.post("https://irm.cninfo.com.cn/newircs/index/queryKeyboardInfo",
            data={"keyWord": code}, headers={"User-Agent": UA}, timeout=10
            ).json().get("data") or []
        if not d1:
            return []
        rows = requests.post("https://irm.cninfo.com.cn/newircs/company/question",
            params={"_t": 1, "stockcode": code, "orgId": d1[0].get("secid"),
                    "pageSize": page_size, "pageNum": 1, "keyWord": "",
                    "startDay": "", "endDay": ""},
            headers={"User-Agent": UA}, timeout=10).json().get("rows") or []
    except Exception as e:
        print(f"[WARN] 互动易 {code}: {e}", file=sys.stderr)
        return None
    out = []
    for it in rows:
        ts = it.get("pubDate")
        t = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d") if ts else ""
        if t and t < since_date:
            continue
        out.append({"t": t, "q": (it.get("mainContent") or "")[:90],
                    "a": (it.get("attachedContent") or "")[:130] or None})
    return out


def news(code, page_size=8):
    inner = json.dumps({"uid": "", "keyword": code, "type": ["cmsArticleWebOld"],
        "client": "web", "clientType": "web", "clientVersion": "curr",
        "param": {"cmsArticleWebOld": {"searchScope": "default", "sort": "default",
                  "pageIndex": 1, "pageSize": page_size, "preTag": "", "postTag": ""}}},
        separators=(',', ':'))
    r = em_get("https://search-api-web.eastmoney.com/search/jsonp",
               params={"cb": "cb", "param": inner},
               headers={"User-Agent": UA, "Referer": "https://so.eastmoney.com/"})
    try:
        d = json.loads(r.text[r.text.index("(") + 1: r.text.rindex(")")])
    except Exception:
        return None
    arts = d.get("result", {}).get("cmsArticleWebOld", []) or []
    if not arts:
        return None  # 间歇风控与真无新闻无法区分,统一按"未跑"处理
    return [{"time": a.get("date", "")[:10],
             "title": re.sub(r"<[^>]+>", "", a.get("title", "")),
             "source": a.get("mediaName", "")} for a in arts]


def scan_stock(code, trade_date):
    since60 = (datetime.strptime(trade_date, "%Y-%m-%d")
               - timedelta(days=60)).strftime("%Y-%m-%d")
    since90 = (datetime.strptime(trade_date, "%Y-%m-%d")
               - timedelta(days=90)).strftime("%Y-%m-%d")
    item, red = {}, []

    try:
        lk = lockup(code, trade_date)
        item["解禁_未来90天"] = lk
        if lk:
            red.append(f"未来90天解禁 {len(lk)} 批(最近 {lk[0]['date']},"
                       f"占总股本 {lk[0]['ratio_pct']:.1f}%)")
    except Exception as e:
        item["解禁_未来90天"] = f"未跑({e})"

    try:
        anns = announcements(code, since60)
        flagged = [a for a in anns if a["flags"]]
        item["公告_60天"] = {"总数": len(anns), "命中": flagged[:8],
                             "近3条": [f"{a['date']} {a['title'][:40]}" for a in anns[:3]]}
        for a in flagged[:5]:
            red.append(f"公告[{'/'.join(a['flags'])}] {a['date']} {a['title'][:44]}")
    except Exception as e:
        item["公告_60天"] = f"未跑({e})"

    try:
        mg = margin(code)
        item["两融"] = mg["trend"] or {"说明": "样本不足或非两融标的", "rows": mg["rows"]}
        t = mg["trend"]
        if t and abs(t["chg5_pct"]) >= 8:
            red.append(f"融资余额5日 {t['chg5_pct']:+.1f}%(急变,{t['date']})")
    except Exception as e:
        item["两融"] = f"未跑({e})"

    got = irm(code, since90)
    if got is None:
        item["互动易_90天"] = "未跑(请求失败)"
    else:
        unanswered = sum(1 for x in got if not x["a"])
        item["互动易_90天"] = {"条数": len(got), "未回复": unanswered, "样例": got[:5]}
        if len(got) >= 5 and unanswered / len(got) > 0.6:
            red.append(f"互动易近90天 {len(got)} 问仅回复 {len(got) - unanswered}(沟通弱)")

    n = news(code)
    item["新闻"] = ([{"t": x["time"], "title": x["title"][:44]} for x in n[:6]]
                    if n else "未跑(东财间歇风控#18,非无新闻)")

    item["红字信号"] = red
    return item


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="+", help="6位A股个股代码")
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--json", help="结果另存 JSON 路径")
    args = ap.parse_args()

    results = {"meta": {"trade_date": args.date,
                        "executed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "source_tier": "T3(东财/巨潮爬取);数字不入台账,与T1冲突以T1为准"},
               "stocks": {}}
    for code in args.codes:
        if not (len(code) == 6 and code.isdigit() and code[0] in "036"):
            print(f"[SKIP] {code}: 非 A 股个股代码(ETF/指数不适用五项情报)")
            continue
        print(f"== 扫描 {code} ==")
        results["stocks"][code] = scan_stock(code, args.date)
        for r in results["stocks"][code]["红字信号"]:
            print(f"  🔴 {r}")
        if not results["stocks"][code]["红字信号"]:
            print("  (无红字信号)")

    print("\n" + json.dumps(results, ensure_ascii=False, indent=1))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=1)
        print(f"\nSAVED {args.json}")


if __name__ == "__main__":
    main()
