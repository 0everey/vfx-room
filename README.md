# vfx-room · 特效／特效素材

公开分类仓库的初始骨架，用于后续收录与维护高品质特效／特效素材。

| 当前已收录 | 后续收录目标 |
| --- | --- |
| **0 条** | **严格大于 20 条，最低 21 条** |

数量是后续目标，当前没有已完成的资源或“极品”评级。动作不属于本仓库范围。

## 从哪里开始

- [catalog.json](catalog.json)：空收录台账，`items` 当前为 `[]`，记录本分类和后续数量目标。
- [CONTRIBUTING.md](CONTRIBUTING.md)：后续条目的来源、权利与可用性记录方法。
- [tools/README.md](tools/README.md)：可直接运行的站点构建、校验、打包与版本比较工具及完整命令。
- [RIGHTS.md](RIGHTS.md)：当前许可状态与未来资源的权利边界。

需要构建时，Python 3.10+ 在仓库根目录执行 `python -X utf8 tools/static_web.py --help`。三个必要脚本已内置，不依赖原 Skill、私有源仓库或 npm/pip。HTML、显式 `site.json` 由后续站点作者按工具文档准备。

## 当前状态与后续方向

本次只建立分类骨架和真实可用工具；没有收录素材、制作真实展厅或上线 GitHub Pages。仓库地址是源码入口。工具不会自动把台账渲染成网站，也不代表已经支持专用特效／特效素材预览。

后续以效果表达、时序、渲染条件、性能成本和复用方式作为核查方向，达到品质要求后再增加真实条目；按 [CONTRIBUTING.md](CONTRIBUTING.md) 记录证据。公开原件与预览前逐项核权利，未获可公开依据的字节不得提交。

## 参与与 PR 历史

欢迎小修、外链线索或 Draft；在自己的 Fork 提 PR，按 [贡献说明](CONTRIBUTING.md) 自愿参与。AI 接手与可调用检查见 [AGENTS.md](AGENTS.md)；没有常驻 AI 或自动云审查。

- [全部 PR（含关闭与合并）](https://github.com/0everey/vfx-room/pulls?q=is%3Apr+sort%3Aupdated-desc)
- [待处理](https://github.com/0everey/vfx-room/pulls?q=is%3Apr+is%3Aopen)
- [已合并](https://github.com/0everey/vfx-room/pulls?q=is%3Apr+is%3Amerged)
- [已关闭未合并](https://github.com/0everey/vfx-room/pulls?q=is%3Apr+is%3Aclosed+is%3Aunmerged)

关闭和未合并也是有效历史，不要求贡献者继续处理。维护者的检查、未测和接纳理由留在对应 PR；完整分页命令见 AI 入口。
