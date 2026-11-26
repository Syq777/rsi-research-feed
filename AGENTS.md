# 维护这个研究仓库

先读 site.json 取得主题，查看 topics/、catalog/、editorial/、research/ 和 state/。用户提出研究问题时，按 github-research-feed Skill 调研，优先打开一手来源，维护目录，将新发现及证据写入 research/ 和 editorial/。用户只想刷新订阅时，运行 python3 update.py。核对 public/status.json 的错误、RSS 与网页再报告结果。开发环境预览可用 python3 update.py --offline。发布用默认分支的 Update research feed 工作流；线上订阅地址取自 GitHub Pages。
