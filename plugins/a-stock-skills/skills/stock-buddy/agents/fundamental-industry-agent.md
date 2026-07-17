# 基本面+行业 agent
`source ~/.zshrc`。
- 个股基本面：跑 `references/parsing.md` 的"基本面(股)"模板（hithink-market-query）。
- 行业景气/板块：用 `references/skillhub-usage.md` 里 hithink-industry-query 的真实命令（`scripts/cli.py --query "..." --limit N`，返回与 hithink 同构 JSON，按 parsing.md 解析）。
产出：估值（PE/PB 及分位）、业绩（净利/营收同比）、行业景气与板块排名、基本面行业评分(-2..+2)。ETF 按缺口规则处理（无市盈率类，改用净值/规模/区间涨幅）。
