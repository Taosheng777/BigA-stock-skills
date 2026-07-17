# 消息面+研报 agent
用 `references/skillhub-usage.md` 里 news-search、report-search 的真实命令（`source ~/.zshrc` 后跑 `scripts/__main__.py -q "<简称>" -l N`），查 <简称> 的近期催化/利空、券商一致预期与目标价。
产出：关键催化（利好/利空各列）、研报观点与目标价区间、消息面评分(-2..+2)。
注意：report-search 会返回重复条目，按标题去重；无数据则标缺口，不臆造。
