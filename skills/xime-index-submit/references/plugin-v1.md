# 旧版插件 v1 上架

## 适用范围

`src/plugins/v1/` 只用于**旧版 App（< 3.0.0）**的插件：

- 运行时是旧版 Lua / DEX 插件架构（v2.6 使用 `main.lua`、`getEmojis()`、`host.json`）；
- 产物仍是 `.xipk`，但**不是** v3 的 `manifest.json` + `main.js` 结构；
- 生成的 `plugins/index.yaml` 是旧 App 硬编码读取的稳定地址，路径和键名不能改。

新插件一律使用 [plugin-v2.md](plugin-v2.md)。v3 宿主无法加载 Lua 插件，把 v2 包放进 v1 索引
或反过来都会导致安装后无法运行。

v1 条目与 v2 条目可以共用同一个 `id`，分别放在两个目录，生成两个独立索引。旧条目不要删除：
仍在使用旧 App 的用户需要它。

## 字段

源文件：`src/plugins/v1/<id>.yaml`，文件名必须等于 `id`。
生成结果：`plugins/index.yaml`，`index_version: 1`，键为 `plugins`。

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | ✅ | 插件唯一标识；与文件名一致；可与 v2 条目同名 |
| `name` | ✅ | 展示名 |
| `author` | ✅ | 作者 |
| `description` | ✅ | 描述 |
| `type` | ✅ | 固定 `remote`（商店下载） |
| `tags` | ✅ | 搜索标签，如 `[表情]`、`[语音]` |
| `pluginType` | ✅ | `tool` / `emoji` / `speech` / `clipboard_sync` / `backup` / `prediction` / `unknown` |
| `homepage` |  | 项目主页 |
| `license` |  | 许可证，必须允许再分发 |
| `appVersion` |  | 兼容的旧版 App，如 `">=2.6.0"` |
| `warning` |  | 安装前警告 |
| `currentVersion` | ✅ | 当前版本，必须出现在 `versions` 中 |
| `versions` | ✅ | 版本历史，新的在上 |

`versions[]` 字段：

| 字段 | 必填 | 说明 |
|---|---|---|
| `version` | ✅ | 版本号，与 `currentVersion` 对应 |
| `date` | ✅ | `YYYY-MM-DD` |
| `changelog` | ✅ | 更新说明 |
| `downloadUrl` | ✅ | 非空列表 |
| `downloadUrl[].url` | ✅ | **GitHub Release 附件**地址 |
| `downloadUrl[].sha256` | ✅ | 64 位十六进制；客户端强校验 |
| `downloadUrl[].size` | ✅ | 人类可读大小 |
| `downloadUrl[].sizeBytes` | 建议 | 精确字节数 |

v1 条目**不要**写 v2 专有字段：`icon`、`activation`、`minHostVersion`、`platforms`、
`capabilities`、`network`。技能会对这些字段给出警告；它们不会让旧 App 获得新能力。

示例：

```yaml
id: com.example.legacy_emoji
name: 旧版表情包
author: you
description: 兼容 Xime 2.x 的 Lua 表情插件
type: remote
tags: [表情]
pluginType: emoji
homepage: https://github.com/you/legacy-emoji
license: GPL-3.0
appVersion: ">=2.6.0"
currentVersion: "2.1.0"
versions:
  - version: "2.1.0"
    date: "2026-08-07"
    changelog: 旧版最后一个版本
    downloadUrl:
      - url: https://github.com/you/legacy-emoji/releases/download/v2.1.0/legacy-emoji-2.1.0.xipk
        sha256: "<64 位十六进制>"
        size: "3.2 KB"
        sizeBytes: 3277
```

更新版本与其它类型一致：`versions` 顶部新增记录、更新 `currentVersion`、新 tag + 新 Release、
保留旧附件。校验值用 `asset_meta.py` 计算：

```bash
python3 scripts/asset_meta.py \
  https://github.com/you/legacy-emoji/releases/download/v2.1.0/legacy-emoji-2.1.0.xipk
```

本地检查：

```bash
python3 scripts/validate_entry.py src/plugins/v1/<id>.yaml --repo-root /path/to/xime-index
```

技能会给出 `legacy plugin index; new plugins should use v2` 警告——这是预期行为，
只要没有 error 即可。v1 条目同样只改 `src/`，不要提交 `plugins/index.yaml`。

## 迁移到 v2

推荐做法是**新增 v2 条目，保留 v1 条目**，让两代 App 各取所需：

1. 用 `xipm init` 新建 TypeScript 项目，按 v3 契约重写插件逻辑；
   参考 [plugin-v2.md](plugin-v2.md) 的包结构和 manifest 字段。
2. 在 `manifest.json` 里声明 `type`、`version`、`platforms`、`minHostVersion: "3.0.0"`、
   `capabilities`、`network` 等；`xipm check`、`xipm test`、`xipm pack` 全部通过。
3. 打新 tag、建新 Release，上传 v2 `.xipk`；计算 `sha256` / `size` / `sizeBytes`。
4. 在 `src/plugins/v2/<id>.yaml` 新增条目，`appVersion: ">=3.0.0"`，
   `pluginType` 与 manifest `type` 一致。`id` 可以与 v1 相同。
5. **不要删除或改写 v1 条目**，也不要把 v1 的 `downloadUrl` 指向 v2 的 `.xipk`；
   旧 App 无法加载 v3 包。
6. 两个索引都跑一遍本地校验，PR 只提交 `src/` 下的新增/修改。

版本号可以延续（如 v1 `2.1.0` → v2 `3.0.0`），也可以独立编号（如 kaomoji 的
v1 `2.1.0` 与 v2 `4.0.0`）；关键是每个索引内部的 `currentVersion` 与附件一致。

迁移检查表：

| 检查项 | v1 | v2 |
|---|---|---|
| 源目录 | `src/plugins/v1/` | `src/plugins/v2/` |
| 生成索引 | `plugins/index.yaml` | `plugins/v2/index.yaml` |
| 兼容 App | `< 3.0.0` | `>= 3.0.0` |
| 包内容 | 旧版 Lua/DEX `.xipk` | `manifest.json` + `main.js` + `resources/` |
| 索引 `appVersion` | 如 `">=2.6.0"` | `">=3.0.0"` |
| 是否保留 | 保留，供旧 App | 新增，供 v3 |

常见迁移错误：

- 只把 v1 条目复制到 v2 目录，却没改 `appVersion` / `pluginType` 对应的 manifest；
- 用 v2 的 `.xipk` 覆盖 v1 的 Release 附件，导致旧 App 下载后无法加载；
- 迁移完就删除 v1 条目，旧 App 的商店列表直接消失；
- v2 版本号与 manifest 不一致，或忘了给 v2 条目补 `sha256`。
