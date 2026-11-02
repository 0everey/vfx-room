# 内置静态站点构建工具

Python 3.10+，只需标准库。三个 Python 文件完整内置，可从本仓库独立使用，无需安装原 Skill、访问来源仓库、pip 或 Node。图片尺寸读取可选使用已安装的 Pillow；未安装也能构建，工具不负责转码或优化。

支持 `build`、`verify`、`pack`、`diff`。本副本移除了依赖展厅模板的 `init` 与邀请分支；不提供自动目录建站或专用资源预览器。`catalog.json` 是收录台账，不能当作下面的 `site.json`。

## 第一次使用

在仓库根目录打开终端，先运行：

```text
python -X utf8 tools/static_web.py --help
```

需要建站时，自行在仓库旁新建 `site-author` 目录，写 UTF-8 的 `index.html` 与 `site.json`。本仓库没有生成或部署站点。下面只是最小调用示例，内容应由后续作者替换。

`../site-author/index.html`：

```html
<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><title>我的内容</title><h1>我的内容</h1></html>
```

`../site-author/site.json`：

```json
{
  "schema": "static-web-bake.config.v1",
  "title": "我的内容",
  "entry": "index.html",
  "files": [{"source": "index.html", "path": "index.html"}],
  "libraryId": "my-resource-library",
  "resources": []
}
```

保持 `libraryId` 稳定；`source` 相对 `site.json`，`path` 是公开输出中的相对 POSIX 路径。每个 CSS、JS、字体、媒体等依赖也须明确列入 `files`，工具不解析 HTML、不自动打包或改写链接。

在仓库根目录依次运行：

```text
python -X utf8 tools/static_web.py build --config ../site-author/site.json --out ../site-release-v1
python -X utf8 tools/static_web.py verify --site ../site-release-v1
python -X utf8 tools/static_web.py pack --site ../site-release-v1 --out ../site-release-v1.zip
```

作者目录和发行目录必须分离；输出目录／ZIP 必须尚不存在。再次构建用 `../site-release-v2` 和新的 ZIP 名，保留已有文件。

## 原件与预览

后续可在作者配置的 `resources` 中加入条目。示意：

```json
{
  "id": "resource-01",
  "name": "资源名称",
  "category": "分类",
  "tags": ["标签"],
  "credit": "作者、来源与许可说明",
  "original": {"source": "source/file.txt", "path": "materials/file.txt", "include": true}
}
```

只有 `original.include: true` 才把本地原件字节加入下载输出；预览本身也是公开字节。`original.path` 不能填写本机绝对位置。公开哪些文件仍须作者逐项决定；常见凭据文件名拦截不是脱密器。外链原件仅支持无凭据 HTTPS 且需内容 SHA／大小，工具不会检查外链可达性。图片／音频／视频／文本预览只建立媒体描述，浏览器是否能消费及交互界面由站点作者另行实现。

## 验证、打包与版本比较

`verify` 对照 `RELEASE.json` 检查文件集合、大小与 SHA-256，拒绝缺失、额外文件、链接或篡改。清单不是签名或合法性证明，也不检查页面视觉与运行时链接。

`pack` 只打包已校验发行物，包含 `site/` 和 `run.py`。解压后运行 `python -X utf8 run.py --no-browser`，用终端给出的 localhost 地址打开。它仅监听 `127.0.0.1`，不是公网网站；服务可用 Ctrl+C 停止。可用 `--port 8010` 换端口。不要用 `file://` 代替 HTTP。外链、CDN 和在线字体不会因打包变成离线资源。

生成第二个新发行目录后，只读比较：

```text
python -X utf8 tools/static_web.py diff --before ../site-release-v1 --after ../site-release-v2
```

工具不会上传、建远端、部署 Pages、自动更新或清理旧输出。构建把显式内容读入内存，适合中小型投影；大媒体库应先评估容量。来源及此次适配见 [PROVENANCE.json](PROVENANCE.json)，权利状态见 [RIGHTS.md](../RIGHTS.md)。
