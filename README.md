# 主题研究仓库

主题名称和说明位于 topics/，启用的主题 ID 在 site.json。这个仓库存放来源、研究记录、文章归档、网站源代码、生成的网页和 RSS。

| 路径 | 内容 |
| --- | --- |
| topics/ | 主题范围、关键词和已验证的上游订阅地址 |
| catalog/ | 按大类、小类整理的完整来源目录，包括需要人工查阅的来源 |
| research/ | 有出处的调研记录、覆盖情况和待查问题 |
| editorial/ | 经核对的公开条目，每条有标题、原文地址、原始发布日期、来源、来源 ID 与短摘要 |
| state/ | 历次获取和精选条目的累计索引，以规范化原文地址去重 |
| public/ | 生成的 index.html、feed.xml、feeds.opml、status.json |
| .github/workflows/research-feed.yml | 每日、手动和默认分支相关改动触发的构建发布流程 |

## 本地检查

使用 Python 3.10+ 和 Linux 或 macOS。先运行 `python3 -B -m unittest discover -s tests`，再运行 `python3 update.py`。离线预览用 `python3 update.py --offline`。在仓库根目录运行 `python3 -m http.server 8000 --directory public`，打开 http://localhost:8000/ 。本地预览地址只供本机使用。线上构建从 Pages 配置读取实际网址及项目路径。

## GitHub 上自动更新

将本仓库的文件提交到 GitHub 默认分支，在 Settings → Pages → Build and deployment → Source 选择 GitHub Actions，并启用仓库的 Actions。工作流需要把 state/ 和 public/ 写回默认分支，仓库的工作流权限及分支规则须允许该写入。首次在 Actions → Update research feed → Run workflow 运行；之后每天 UTC 00:17（北京时间 08:17）触发，实际执行时间由 GitHub 调度。首次部署或故障恢复后，在 Actions 的部署环境或 Settings → Pages 查看真实网址，打开首页并校验其 RSS 链接。公开访问以仓库的 Pages 配置为准。

日常提问可以用「更新今天的订阅」或「调研本周这个主题的新进展，把带证据的摘要写进仓库」。前者抓取配置中的公开 RSS/Atom；后者由你正在使用的 AI 查阅原文、归档并生成精选。无人值守获取使用订阅源提供的标题和摘要，无需模型密钥。手动维护的研究、社交媒体或会议线索可在调研时补入。部分源失败时保留历史；所有已配置订阅源同时失败时构建失败，维持上一次站点。没有订阅源的主题可发布已有人工精选。

读者可以订阅首页提供的 feed.xml 获取最近至多 200 条更新，或将 feeds.opml 导入阅读器单独订阅上游源。历史索引在 state/ 中。订阅条目的原文及第三方作品的权利归相应权利人。

## 可选的 GitHub 托管 AI 调研

仓库持有人可以设置 Actions secret `OPENAI_API_KEY` 和仓库变量 `RESEARCH_MODEL` 启用带网页检索的候选发现。模型 ID 需要支持 Responses API 的 web search，调用计入该 API 账户。在 research/主题/ 下查看带原文链接的每日候选报告，核对后写入 editorial/ 可进入订阅。自动检索只使用本主题配置的来源域名和关键词。
