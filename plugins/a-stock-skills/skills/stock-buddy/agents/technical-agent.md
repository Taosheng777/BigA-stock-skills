# 技术面 agent
`source ~/.zshrc`，对 <代码> <简称> 跑：
`python3 ~/.claude/skills/hithink-market-query/scripts/cli.py --query "<代码> <简称> MACD KDJ RSI 5日均线 10日均线 20日均线 60日均线 最新价 最新涨跌幅" --limit 1`
解析按 `references/parsing.md`（日期后缀模糊匹配）。产出：趋势结构（现价相对 MA5/10/20/60）、MACD/KDJ/RSI 状态、超买超卖、**触发价 + 失效位**、技术评分(-2..+2)。不预测点位之外的走势。
