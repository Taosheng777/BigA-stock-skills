# a-stock-skills

A curated set of four Claude Code skills for China A-share market research: free-source market data fetching, natural-language stock screening, two-tier analysis, and a post-market routine. Docs are Chinese-first. Research tooling only — **not investment advice**.

> ## ⚠️ 免责声明（先读这个）
>
> 本仓库全部内容是**个人研究工具与方法论分享，不构成任何投资建议**（作者非持牌投顾）。行情与数据来自第三方公开接口，准确性、完整性、及时性均不作保证；据此操作，盈亏自负。所有 skill 内置铁律：**不下单、不碰交易、不编数据**，每份分析输出自带非投顾声明。

## 包含的 4 个 skill

| skill | 干什么 | 依赖 |
|---|---|---|
| **a-stock-data** | A 股数据获取：行情/K线、研报、龙虎榜、资金面、公告、打板、ETF 期权、舆情等，十层免费数据源 + 内嵌全部可运行代码 | **零依赖，开箱即用** |
| **stock-screener** | 问财自然语言选股：筛池子 → 透明加权打分 → Top-N 名单（HTML + 对话版），只筛不分析 | 问财 API Key |
| **stock-buddy** | 双档分析。常规档：持仓体检 + 纪律护栏 + 危险信号，不喊买入；专家模式（须当轮确认）：多 agent 并发做纯市场分析 | 问财 CLI + Key（取数）；投资 vault 可选 |
| **stock-daily** | 盘后例行六步编排：git 快照 → 刷新持仓 → 净值绩效 → 选股台账 T+N → 复盘骨架 → 次日清单 | 同上 + 自己的 Obsidian vault |

设计上四个 skill 相互解耦、软提示交接（screener 出名单 → 用户自己点名让 buddy 深度研判），共守三条铁律：不下单、不编数据、断数据必熔断。

## 安装

**方式一 · 插件市场（推荐，可随仓库更新）**

在 Claude Code 里执行：

```
/plugin marketplace add Taosheng777/a-stock-skills
/plugin install a-stock-skills@a-stock-skills
```

**方式二 · 手动复制**

Clone 本仓库，把 `plugins/a-stock-skills/skills/` 下的四个目录复制到 `~/.claude/skills/`。

## 依赖分层（装之前看清楚）

1. **零配置**：`a-stock-data` 装好即用（通达信/腾讯/东财等免费公开源）。
2. **需要同花顺问财 API Key**：`stock-screener`、`stock-buddy`（取数）、`stock-daily`。
   - Key 获取：iwencai.com/skillhub → 登录 → 安装方式-Agent用户-复制 Key；写入 `~/.zshrc`：`export IWENCAI_API_KEY=...`
   - 同时需要安装同花顺问财行情 CLI（`hithink-market-query` 等厂商组件，**本仓库不包含**，以厂商官方渠道为准）。
3. **需要自己的 Obsidian 投资 vault**：`stock-daily`（必需，且 vault 需 `git init`）、`stock-buddy` 常规档纪律护栏（可选）。
   - Vault 目录结构示例与纪律文件模板：见 `stock-buddy/references/discipline.md` 和 `stock-daily/SKILL.md` 配置段；两处的路径与示例数值均为占位模板，装好后改成你自己的。

## 快速上手

```
「600519 最近主力资金什么情况」        → a-stock-data（零依赖）
「选几只放量突破的票」                  → stock-screener（需 Key）
「用 stock-buddy 分析 600519」          → stock-buddy 常规档
「盘后例行」                            → stock-daily（需 vault）
```

## License

MIT
