# 2026-11-26：从聚合目录改为每日精选

问题：让读者每天快速理解 AI 自我改进的值得读进展。首页不再按抓取时间排列大量论文，改为 10 篇经过原文核对的中文导读，3 篇论文、7 篇非论文。原始 90 篇候选和 271 个来源入口保留在 archive.html。

## 本期核对的材料

| 首发日期 | 材料与原文 | 类型及阅读角度 |
| --- | --- | --- |
| 2026-11-24 | [METR：Interpreting a Recent Acceleration in Pretraining Loss](https://metr.org/blog/2026-11-24-interpreting-a-recent-acceleration-in-pretraining-loss/) | 评测解读；区分训练损失下降与能力提升，不据单一曲线断言突破 |
| 2026-11-18 | [OpenAI：Research acceleration and the jagged frontier](https://openai.com/index/research-acceleration-jagged-frontier/) | 研究观察；内部研发加速的差异和测量边界，结论来自作者报告 |
| 2026-11-23 | [Google DeepMind：Finding faster quantum algorithms with agents and formal verification](https://deepmind.google/blog/finding-faster-quantum-algorithms-with-agents-and-formal-verification/) | 研究观察；代理搜索与形式验证结合，关注反馈可靠性 |
| 2026-11-24 | [VISE](https://arxiv.org/abs/2611.32480) | 论文；利用工具执行反馈修订技能，实验为作者自报 |
| 2026-11-20 | [METR：Q4 2026 Capability Update](https://metr.org/blog/2026-11-20-q4-2026-capability-update/) | 评测解读；任务反馈、判断与测量方式影响结论 |
| 2026-11-24 | [Sakana AI：Applied Research Lab](https://sakana.ai/applied-research-lab/) | 研究观察；机构发布的研究组织方式，不能视作已验证的自主科研能力 |
| 2026-11-24 | [RecurSciBench](https://arxiv.org/abs/2611.32508) | 论文；递归科研的跨任务改进与退步，注意独立测试 |
| 2026-11-24 | [E2L](https://arxiv.org/abs/2611.32390) | 论文；有用的推理经验与有用的训练数据并不自动等价 |
| 2026-11-06 | [Anthropic：Components of agent memory](https://www.anthropic.com/research/components-of-agent-memory) | 工程实践；记忆结构与维护，比单纯增加记忆更具体 |
| 2026-11-13 | [Anthropic：Building strong safety evaluations](https://www.anthropic.com/research/building-strong-safety-evaluations) | 工程实践；评测的设计、运行与报告，帮助理解可靠反馈 |

所有条目的中文概要和推荐理由保存于 editorial/rsi.json，发布快照在 editions/rsi/2026-11-26.json。日期以原文为准：Sakana 的 feed 日期与正文日期有差异；本期三篇 arXiv 的公布/通知日期也需和原始提交日期区分。

## 覆盖与限制

本期扩展了已有 RSS 候选以外的 Anthropic 和 DeepMind 原文。近两周工程材料不足时，采用近一个月内的两篇工程文章，并明确显示原文日期。没有为填满“观点/播客”配额而编写未读取的内容。本期没有逐一复查整个 271 项目录。

模型撰写的概要是对原文的归纳，不是独立复现实验。自动选稿程序验证日期、质量门槛、类型比例、来源集中度及七天事件去重；不能替代阅读判断。

GitHub 每日抓取候选；本机 Codex 每日编辑新一期。若机器离线或缺乏合格稿件，保留最近一期及其日期。RSS 同步精选，不再把整个原始候选池推给读者。
