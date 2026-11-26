# 维护这个研究仓库

使用 github-research-feed 技能。先读 site.json、topics/、editorial/、editions/ 和 research/。

首页是每日精选，原始采集进入候选归档。只刷新 RSS 时运行 python3 update.py；它不会生成新一期或编造中文概要。

每日编辑需从完整 catalog/ 发现线索，不限于七个 RSS 端点；优先近期一手文章、工程实践、独立评测、观点访谈，再补论文。打开原文，核对日期，写入 editorial/ 中的 headline、summary、why_read、kind、score、event_id 和 reviewed_at。概要写文章具体说了什么，阅读理由说明读者能带走什么，两者不要重复。

默认每日 10 条，论文目标 30%、硬上限 40%，同类不足自动让给其他非论文类型；不为数量牺牲相关性。普通候选限最近 30 天，过去七天已选文章和同一事件不重复。

用 python3 digest.py --date YYYY-MM-DD --lead '本期导读' 生成带明确日期的 editions/rsi/YYYY-MM-DD.json，再运行测试和 python3 update.py --site-url https://syq777.github.io/rsi-research-feed/。未形成新一期则保留旧一期日期。不得把自动抓取时间当作精选更新时间。

发布已获用户授权。修改前在干净工作树 git pull --ff-only；只提交本轮编辑及生成物，推送 main 并跟到 Pages 部署完成，核验首页及 feed.xml。保留研究记录和原始来源，不把候选数量当作读者价值。
