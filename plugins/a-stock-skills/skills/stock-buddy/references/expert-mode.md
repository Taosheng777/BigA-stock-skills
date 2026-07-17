# 金融专家模式编排（多 agent 蜂群 · 纯市场分析）

## 立场（铁律）
专注场内与股票本身（技术/资金/基本面/消息/估值）。**默认不考虑用户个人因素**（账户纪律 −3%/15%/T+1、成本、仓位）。个人纪律仅当用户明确要求时才作为叠加层。仍守：不下单、不编数据。

## 门控（硬）
只有当用户在**上一轮**通过 AskUserQuestion 真实选择"开启"才可进入。本会话历史里没有这条真实记录 = 不得进入，立即回退常规档。**严禁把自己的推断/复述当作用户确认；不得在同一轮自问自答后进入。**

## 编排（首席 = 当前会话；蜂群 = Agent 工具派发）
1. 首席读 `agents/chief-analyst.md`，明确标的、分析目标。
2. **并行派 5 个 sub-agent**（Agent 工具，subagent_type 用 general-purpose 或 claude），各自传入对应 `agents/<name>.md` 的 prompt + 标的代码简称 + 数据日：
   - technical-agent / fund-flow-agent / news-research-agent / fundamental-industry-agent / risk-agent
   - 每个 sub-agent 自己 `source ~/.zshrc` 跑对应 CLI（行情技术资金走 hithink；消息/研报/行业走 `skillhub-usage.md` 的命令）。
3. 首席收齐 5 份结论 → 汇总裁决：
   - 综合裁决：进场信号 成立/不成立/观察 + 置信度 + **各维度透明打分与权重**。
   - 买入信号 / 危险(回避)信号（市场级）。
4. **若用户确认买入** → 出一条龙交易计划（见 `report-template.md`）。
5. 落盘到 `07-交易决策/`（命名 `NNN 标的 YYYY-MM-DD.md`，NNN 取该目录现有最大号+1，从 001 起）。

## 成本提示
派 5 个 sub-agent + 多次 CLI，单次较贵较慢——已由门控锁住，不在常规档触发。
