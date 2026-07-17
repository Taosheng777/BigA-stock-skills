# 资金面 agent
`source ~/.zshrc`，跑：
`python3 ~/.claude/skills/hithink-market-query/scripts/cli.py --query "<代码> <简称> 主力资金流向 主力净流入 大单净额 超大单净额" --limit 1`（ETF 去掉"超大单"）
另可跑所属板块榜看轮动。产出：主力/大单/超大单净额、是否价涨资金背离、资金多空评分(-2..+2)。
