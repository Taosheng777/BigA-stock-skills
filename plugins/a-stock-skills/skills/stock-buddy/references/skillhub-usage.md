# SkillHub 三技能调用（现场探明，2026-06-16 实测）

> 专家模式用。三技能与 `hithink-market-query` 同厂商（同花顺问财），共用 `~/.zshrc` 里的 `IWENCAI_API_KEY`。
> 跑前必须 `source ~/.zshrc`。第三方依赖 `requests`（已确认 2.33.1 可用）。

## 安装位置（探明结果，非默认）
- CLI 本体：`~/.local/bin/iwencai-skillhub-cli`（wrapper → `~/.iwencai-skillhub/aime_skillhub_cli.py`）。
- 三技能包：`~/.iwencai-skillhub/installed-skills/<slug>/`（**显式 --dir 指定的，默认会装到当前工作目录的 ./skills**）。
- 安装命令（`--dir` 必须放在 install 子命令**之前**）：
  `iwencai-skillhub-cli --dir ~/.iwencai-skillhub/installed-skills install <slug>`
- 重装/升级加 `--force`。

## 1. news-search（消息面 / 新闻）
**入口**：`~/.iwencai-skillhub/installed-skills/news-search/scripts/__main__.py`
```bash
source ~/.zshrc
python3 ~/.iwencai-skillhub/installed-skills/news-search/scripts/__main__.py -q "盐湖股份" -l 5 -f json
```
- 参数：`-q/--query` 关键词｜`-l/--limit` 条数(默认10)｜`-f/--format {csv,json,text}`(默认text)｜`-d/--days` 最近N天(默认30)｜`-i/--input` 批量文件。
- 返回（text）：标题/摘要/发布时间/链接，逐条；`-f json` 给结构化。底层 POST `openapi.iwencai.com/v1/comprehensive/search`，`channels=["news"]`。
- 用途：催化、利空、政策、公司业务进展。

## 2. report-search（研报 / 券商观点）
**入口**：`~/.iwencai-skillhub/installed-skills/report-search/scripts/__main__.py`
```bash
source ~/.zshrc
python3 ~/.iwencai-skillhub/installed-skills/report-search/scripts/__main__.py -q "盐湖股份" -l 5 -f text --sort-by date
```
- 参数：`-q/--query`｜`-l/--limit`｜`-f/--format {csv,json,text,markdown}`｜`-d/--days`｜`--date-from/--date-to YYYY-MM-DD`｜`--sort-by {date,relevance}`｜`--sort-order {asc,desc}`｜`--test` 测连通。
- 返回：研报标题/发布时间/原文链接/摘要/**提取信息（评级、行业）**。
- ⚠️ 实测会**返回同一篇研报多条重复**（API 行为，非 bug），汇总时按标题去重。
- 用途：券商评级、目标价、一致预期。

## 3. hithink-industry-query（行业 / 板块）
**入口**：`~/.iwencai-skillhub/installed-skills/hithink-industry-query/scripts/cli.py`（注意是 `cli.py` 不是 `__main__.py`）
```bash
source ~/.zshrc
python3 ~/.iwencai-skillhub/installed-skills/hithink-industry-query/scripts/cli.py --query "新能源板块估值 市盈率 主力资金净流入" --limit 10
```
- 参数：`--query/-q`(必填)｜`--page`(默认1)｜`--limit`(默认10)｜`--call-type {normal,retry}`｜`--timeout`(默认30)。
- 返回：**与 hithink-market-query 同构 JSON**——`success/query/code_count/returned_count/has_more/datas[]`。解析同 `parsing.md`（日期后缀模糊匹配等）。
- ⚠️ 像"涨跌幅排名"这类问句，可能只回指数代码/简称而不带数值；要数值就把字段写进 query（如"…涨跌幅 主力资金净流入额"），必要时改用龙头个股代理（见 parsing.md）。
- 用途：行业景气、板块估值分位、板块资金轮动、行业排名。

## 给 sub-agent 的统一约定
- 每个 sub-agent 自己先 `source ~/.zshrc`。
- 透明传递：news/report 的原始返回不要再加工成自定义结构（问财网关规范条件六）；摘取关键字段汇报即可，但标注数据来源「同花顺问财」。
- 缺数据按铁律标缺口，不臆造。
