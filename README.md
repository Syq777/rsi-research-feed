# RSI 每日精选

每天读几篇值得读的 AI 自我改进进展：先看中文概要，再看一句“为什么读”，感兴趣时打开原文。首页默认最多 10 篇，论文三成作为滚动参考、每天最多四成，其他名额在工程、研究观察、评测和观点访谈中调整；内容不足就少选。

[阅读网站](https://syq777.github.io/rsi-research-feed/) · [订阅精选 RSS](https://syq777.github.io/rsi-research-feed/feed.xml) · [候选与来源目录](https://syq777.github.io/rsi-research-feed/archive.html) · [可复用 Skill](https://github.com/Syq777/github-research-feed)

[来源 Top 20 与访问实测](https://syq777.github.io/rsi-research-feed/sources.html) · [完整表格 CSV](https://syq777.github.io/rsi-research-feed/sources.csv)

先轮询完整动态来源池，再选十条。六个领域各有 Top 20，合并后 112 个重点入口；完整目录去重 270 项，其中 185 个动态公开入口每天尝试。没有具体公开地址的 9 项单列，经典文章、书籍和工具不冒充日更来源。每个源记录重要性、本轮抓取结果、登录/付费限制；HTTP 可达不等于读到文章全文。

每日先运行 `python3 poll_sources.py --date YYYY-MM-DD`，保存来源检查及候选入选/落选理由到 research/reviews，通常比较至少 30 个候选，实际不足需说明。每期另有自然名字与 3–5 个关键词：digest.py 使用 `--name '本期名字' --keywords 词一 词二 词三`。轮询未覆盖全池或仅凭列表入围时，程序拒绝生成新一期。

| 路径 | 用途 |
| --- | --- |
| topics/ | 研究范围、关键词、已验证 RSS 和 daily_brief 选稿规则 |
| catalog/ | 完整来源目录，供主动检索使用，不要求每天逐个展示 |
| editorial/ | 原文资料、中文标题、概要、阅读理由、类型及核对日期 |
| editions/ | 带明确日期的每日精选快照 |
| research/ | 有出处的研究笔记及未覆盖限制 |
| state/ | 原始抓取和人工条目的候选索引 |
| public/ | 精选首页、issues/ 往期、archive.html 候选目录、精选 RSS 和抓取状态 |

## 每日运行

GitHub Actions 每天 UTC 00:17（北京时间 08:17）刷新原始候选。本机 Codex 每天北京时间 08:30 按 Skill 阅读原文、编写中文概要与推荐理由、生成新一期、提交并发布。无需额外模型 API，电脑需在线；错过执行时网站保留最近一期的真实日期。GitHub 调度可能延迟，本机任务也会刷新候选。

模型从完整来源池寻找材料，不限于已接通的 7 个 RSS 端点。优先近 14 天，必要时回看 30 天；同一事件和过去七天已选文章不重复。论文形式按内容判断，不能通过改成“研究观察”绕过比例。RSS 只发布精选，目录中的 271 个入口不等于 271 个自动订阅。

## 编辑与检查

使用 Python 3.10+。先读 AGENTS.md 和主题配置，打开原文核实并更新 editorial；必需字段见 Skill 的数据约定。reviewed_at 取实际核对日，date 保留首次发表日。

```bash
python3 digest.py --date YYYY-MM-DD --lead '本期导读'
python3 -B -m unittest discover -s tests
python3 update.py --site-url https://syq777.github.io/rsi-research-feed/
```

update.py 只抓取和渲染，不自动生成中文或新一期。--offline 用于离线构建；python3 -m http.server 8000 --directory public 可预览。发布前在干净工作树 fast-forward 同步远端，只提交本轮改动；推送 main 后跟到 Pages 部署成功并检查首页和 feed.xml。

feed.xml 提供最近至多 200 篇精选，概要包含阅读理由与原文日期。feeds.opml 提供未经精选的上游订阅，二者用途不同。全部已配置源失败时保留上一次站点；没有新稿时不伪造今日更新。

可选 research_ai.py 需要另配 OPENAI_API_KEY 和 RESEARCH_MODEL，当前未启用。它仅产出待复核候选报告，不等价于完整编辑发布。第三方文章及作品权利归原作者。

按周看均衡：每天通过 balance.py 查看近七天的领域、文章形式与来源、近四周的覆盖；weeks/ 保存有依据的当周重点。每天不设固定分类名额，质量接近时补近期缺少的视角，重要进展可以连续关注。周重点不缩小全池轮询范围，也不允许为了补配额选低质量稿。
