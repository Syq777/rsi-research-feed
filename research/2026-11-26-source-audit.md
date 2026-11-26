# 2026-11-26 来源全池检查与第二轮选稿

用户要求按研究方法、工程与开源、自动科研、评测安全、产业动态、观点访谈六个内容领域各选 Top 20。已建立 sources/rsi.json：120 个分组位置对应 112 个去重重点入口，所有动态来源均纳入每日轮询，不能找到十篇就结束。

## 本次实测

原目录 271 条合并同一 Dwarkesh 地址后为 270 项。其中 185 个动态公开入口、76 个固定背景/工具入口、9 个缺少固定地址的项目。本次对全部 261 个有地址项目发起实际请求，其余 9 项明确记录未配置。

| 范围 | 公开页面/RSS可读 | PDF可读 | 检测到订阅提示 | 需浏览器复查 | 拒绝/限流 | 未配置 |
| --- | --- | --- | --- | --- | --- | --- |
| 全部 270 项 | 222 | 1 | 1 | 32 | 5 | 9 |
| 185 个日常公开入口 | 161 | 0 | 1 | 19 | 4 | 0 |

可读是入口级检查，不等于成功提取文章列表，更不等于全部全文免费。动态页面或过少正文记录 needs_browser，HTTP 403 记录 blocked，不推断付费。现有七个 RSS 仍是已验证的结构化采集；新增 HTML 轮询用于发现候选，不能冒充全站全文抓取。

The Information 本机 HTTP 请求为 403，网页检索工具能显示公开列表；两种结果均保留。Interconnects 的[官方说明](https://www.interconnects.ai/about)明确有部分付费文章。SemiAnalysis、Latent Space 的公开入口和付费服务并存，未测试会员全文。没有登录、购买订阅或绕过访问限制。

完整表格在 public/sources.html、sources.csv 和 sources.md，每个源单列重要性、访问状态、权限说明、检查时间与证据。重要性表示本主题的监测优先级，不代表客观学术排名；访问失败不会自动降低重要性。

## 比较与选稿

全池轮询后做链接关键词机器初筛；候选比较保存于 research/reviews/2026-11-26-rsi.json。共有 34 篇候选，其中 12 篇已读原文、论文摘要或访谈文字稿，另 22 篇根据列表日期、主题和证据不足等因素排除。未把初筛计作精读。

新增精读：

- [Prime Intellect：Introducing Model Factory](https://www.primeintellect.ai/blog/introducing-model-factory)，2026-11-18。厂商说明如何连接训练、推理、运行记录和独立评测，作为工程流程材料，不把产品宣传当独立效果证明。
- [The Cognitive Revolution：Agents That Think Together](https://www.cognitiverevolution.ai/agents-that-think-together-cisco-s-vijoy-pandey-on-semantic-alignment-scope-accord-concord/)，2026-11-11。读到公开文字稿；访谈讨论多智能体的目标对齐、交接和整体验收。文字稿可能有转录误差，避免依赖未经核对的精确数值。

本期调整为 2 篇研究观察、2 篇评测、2 篇工程、1 篇访谈、3 篇论文。Sakana 应用实验室公告和较早的 Anthropic 记忆文章留在候选归档；新加入的工程流程和访谈更适合当前阅读组合。

名字：RSI 十条｜模型进步了，工作变好了吗？关键词：研发效率、训练反馈、多智能体、评测。该修改保留同一天的期刊日期，未伪造新一期。
