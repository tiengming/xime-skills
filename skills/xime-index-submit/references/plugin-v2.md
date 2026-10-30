# 插件 v2 上架

插件 v2 是 Xime **v3.0.0+** 的 TypeScript / QuickJS 插件：源码编译成单文件 `main.js`，
与 `manifest.json`、`resources/` 一起打包为 `.xipk`。旧版 Lua/DEX 插件见
[plugin-v1.md](plugin-v1.md)；索引通用规则见 [index-rules.md](index-rules.md)。

## 包结构

```text
my-plugin/
├── main.ts            # 源码：definePlugin + export default
├── main.test.ts       # 测试；不会进 .xipk
├── libs/*.ts          # 可选：相对 import 的拆分模块，构建时内联
├── manifest.json      # 清单；支持 // 注释与尾逗号（JSONC）
├── resources/         # 图片等资源；宿主按路径渲染
├── xime-plugin.d.ts   # SDK 类型声明（xipm init 生成）
└── tsconfig.json      # 类型检查配置
```

`xipm pack` 只把以下内容打进 `.xipk`：

```text
my-plugin-0.1.0.xipk
├── manifest.json
├── main.js            # 编译产物，IIFE，定义 globalThis.plugin
└── resources/         # 可选
```

- `main.ts` 必须 `export default plugin;`；`xipm build` 会生成
  `var plugin = (function () { ... })();`。
- `manifest.json` 的 `entry` 固定为 `main.js`，不要手写入口脚本。
- 安装后解压到 `files/plugins/<id>/`，由宿主 QuickJS 沙箱加载。
- `.xipk` 本质是 zip，条目用 `/` 分隔并带 UTF-8 flag；用 `xipm pack` 生成即可，
  不要手工改 zip。

最小 `manifest.json`：

```jsonc
{
  "id": "com.example.daily_quote",
  "name": "每日一言",
  "description": "拉取一句随机句子，点选上屏",
  "version": "0.1.0",
  "type": "tool",
  "entry": "main.js",
  "platforms": ["android"],
  "minHostVersion": "3.0.0",
  "capabilities": {
    "tool": { "display": "passive" }
  }
}
```

## manifest 字段

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | string | ✅ | — | 唯一标识；字母/数字/下划线/连字符，点号分段，≤64 |
| `type` | string | ✅ | — | `tool` / `emoji` / `speech` / `clipboard_sync` / `backup` / `prediction` / `unknown` |
| `entry` | string | ✅ | `main.js` | 入口脚本，固定 `main.js` |
| `version` | string | ✅ | `0.0.0` | 语义化版本，必须与索引 `currentVersion` 一致 |
| `name` | string |  | `= id` | 展示名 |
| `icon` | string |  | — | 文字图标，或 `resources/` 下的图片文件名 |
| `description` | string |  | `""` | 描述 |
| `platforms` | string[] |  | `["android"]` | 目标平台；不含当前平台时宿主不加载 |
| `minHostVersion` | string |  | — | 最低主应用版本；不满足时拒绝安装/加载 |
| `maxHostVersion` | string |  | — | 最高主应用版本（含） |
| `network.hosts` | string[] |  | `[]` | 允许联网的域名 / IPv4 白名单 |
| `network.allowCustomHosts` | boolean |  | `false` | 允许用户自定义服务器域名，保存配置后自动授权 |
| `toolbarButtons` | object[] |  | `[]` | tool 插件的工具栏入口按钮 |
| `capabilities` | object |  | — | 能力声明；宿主消费能力的**唯一来源** |

`capabilities` 常用键：

| 键 | 适用 type | 说明 |
|---|---|---|
| `emoji` | emoji | `supportsSearch` / `columns` / `itemHeightDp` |
| `tool.display` | tool | `direct` 或 `passive` |
| `speech` | speech | `inputMode` / `supportsPartialResults` / `requiresNetwork` |
| `clipboard_sync.protocols` | clipboard_sync | 同步协议，启动前硬校验 |
| `backup.protocols` | backup | 备份传输协议 |
| `events` | 任意 | 订阅的下行事件，如 `text_committed` |
| `candidate_transform` | tool | 候选词变换（15ms 硬超时） |
| `quick_send_read` | 任意 | 注入 `host.quickSend` |
| `clipboard_read` | 任意 | 注入 `host.clipboard` |

`toolbarButtons` 示例：

```jsonc
"toolbarButtons": [
  {
    "id": "com.example.daily_quote:open",
    "label": "每日一言",
    "icon": "icon.png",
    "action": "open_panel"
  }
]
```

`action` 当前只有 `open_panel`。按钮的 `icon` 若用图片，文件必须在 `resources/` 中。

旧字段说明：

- `activation` / `configSchema` 等旧字段宿主 v3 **不消费**。激活方式由 `type` 推导
  （emoji/tool/prediction 多选，speech/clipboard_sync/backup 单选）；
  配置表单由插件的 `settings.schema()` 提供。
- 索引 YAML 里仍可保留 `activation` 以兼容旧工具，但宿主不会读它。技能会提示这是旧字段；
  若 manifest 也写了 `activation`，两处必须一致。

## 索引字段映射

v2 条目放在 `src/plugins/v2/<id>.yaml`，生成到 `plugins/v2/index.yaml`
（`index_version: 2`，键为 `plugins`）。索引字段是 manifest 的**投影**，不是另一套配置。

| manifest.json | 索引 YAML | 索引必填 | 规则 |
|---|---|---|---|
| `id` | `id` | ✅ | 必须相等，且等于文件名 |
| `type` | `pluginType` | ✅ | 枚举必须合法；索引里的 `type: remote` 是下载类型，不是插件类型 |
| `version` | `currentVersion` | ✅ | 必须相等，并与 `versions[].version` 对应 |
| `name` | `name` | ✅ | 展示名；建议同步 |
| `icon` | `icon` |  | 有则原样同步 |
| `description` | `description` | ✅ | 展示描述；建议同步 |
| `platforms` | `platforms` | ✅ | 非空列表，原样同步 |
| `minHostVersion` | `minHostVersion` |  | 原样同步 |
| `capabilities` | `capabilities` |  | 原样同步（深比较） |
| `network` | `network` |  | 原样同步（深比较）；无联网可省略 |
| `maxHostVersion` | — |  | 只存在于 manifest，由宿主安装时执行 |
| `toolbarButtons` | — |  | 只存在于 manifest |
| `entry` | — |  | 固定 `main.js`，不进索引 |

索引里额外需要作者填写：

- `author`、`tags`、`homepage`、`license`、`appVersion`、`warning`；
- `versions[].date`、`changelog`；
- `versions[].downloadUrl[]` 的 `url`、`sha256`、`size`、`sizeBytes`。

`appVersion` 与 `minHostVersion` 保持一致，例如 manifest 写 `"3.0.0"`，索引写
`appVersion: ">=3.0.0"`。完整的 v2 条目示例：

```yaml
id: com.example.daily_quote
name: 每日一言
author: you
description: 拉取一句随机句子，点选上屏
type: remote
tags: [工具]
pluginType: tool
icon: "言"
activation: multi          # 旧字段，可省略
minHostVersion: "3.0.0"
platforms: [android]
capabilities:
  tool:
    display: passive
network:
  hosts: [v1.hitokoto.cn]
homepage: https://github.com/you/daily-quote
license: MIT
appVersion: ">=3.0.0"
currentVersion: "0.1.0"
versions:
  - version: "0.1.0"
    date: "2026-10-30"
    changelog: 初始发布
    downloadUrl:
      - url: https://github.com/you/daily-quote/releases/download/v0.1.0/daily-quote-0.1.0.xipk
        sha256: "<64 位十六进制>"
        size: "3.4 KB"
        sizeBytes: 3469
```

本地交叉校验：

```bash
python3 scripts/validate_entry.py src/plugins/v2/<id>.yaml \
  --repo-root /path/to/xime-index \
  --manifest ./manifest.json \
  --asset-file ./daily-quote-0.1.0.xipk
```

脚本会检查 `id` / `pluginType` / `currentVersion` / `icon` / `minHostVersion` /
`platforms` / `capabilities` / `network` 是否与 manifest 一致，以及 `.xipk` 根级是否有
`manifest.json` 和 `main.js`。

## xipm 命令

`xipm` 是官方插件工具链（Rust，位于 Xime 仓库 `tools/xime-plugin/`）：

| 命令 | 作用 |
|---|---|
| `xipm init <name> --type <t> [--parent <dir>]` | 生成插件骨架；`--type` 取 `tool` / `emoji` / `speech` / `prediction` / `clipboard_sync` / `backup` |
| `xipm build [dir] [--out <dir>] [--minify]` | 编译为单文件 `main.js` |
| `xipm check [dir]` | 校验 manifest 字段、命名空间、类型与能力一致性 |
| `xipm test [dir] [--smoke]` | 内嵌 QuickJS + mock host 跑 `main.test.ts`，无需真机 |
| `xipm pack [dir] [--release-dir <dir>] [--no-minify]` | 编译 + 打包 `.xipk`（默认压缩） |

典型流程：

```bash
xipm init daily-quote --type tool --parent ~/xime-plugins
cd ~/xime-plugins/daily-quote
# 编辑 main.ts、manifest.json、main.test.ts
xipm check .
xipm build .
xipm test .
xipm pack . --release-dir dist
# → dist/daily-quote-0.1.0.xipk
```

调试期可用 `xipm pack . --no-minify`；真机热调试用
`xipm dev <dir>`，日志用 `xipm logs <dir>`，安装用 `xipm install <xipk|dir>`。

发布前把 `.xipk` 上传到 GitHub Release，计算校验值：

```bash
python3 scripts/asset_meta.py \
  https://github.com/you/daily-quote/releases/download/v0.1.0/daily-quote-0.1.0.xipk
```

## 版本与兼容

- v2 插件要求宿主 **Xime v3.0.0+**；不要给 `<3.0.0` 的旧 App 使用。
- `minHostVersion` / `maxHostVersion` 是安装与加载门禁；版本比较忽略预发布/构建后缀
  （如 `3.0.0-beta2` 按 `3.0.0` 比较）。
- `minHostVersion` 不要为了“兼容更多设备”而写低于实际用到的 API。用到了 v3.2 的能力就写
  `3.2.0`；写低了会在旧宿主上运行时报错。
- `platforms` 是平台门禁；只发 Android 时写 `[android]`，不要留空。
- 发布新版本：

  1. 修改 `main.ts`，把 `manifest.json` 的 `version` 提升到新版本；
  2. `xipm check` / `xipm test` / `xipm pack`；
  3. 打新 tag、建新 Release，上传新的 `.xipk`（不要复用旧 tag 替换附件）；
  4. 在 `src/plugins/v2/<id>.yaml` 的 `versions` 顶部新增记录，更新
     `currentVersion`、`sha256`、`size`、`sizeBytes`；
  5. 旧版本记录和旧附件全部保留。

- `currentVersion`、manifest `version`、Release 附件名、`versions[].version` 四者必须
  指向同一个版本。manifest 先升、索引没升，会出现“安装的是新包、商店显示旧版本”的错位。
- v1 与 v2 可以共用同一个 `id`，分别放在 `src/plugins/v1/` 和 `src/plugins/v2/`，
  生成两个不同的索引；不要删除 v1 条目，旧 App 仍在读它。

## 常见错误

| 现象 | 原因 | 修复 |
|---|---|---|
| Validate Index 报 `missing pluginType` | 索引条目漏了 `pluginType`，或 manifest 的 `type` 没映射过来 | 补 `pluginType`，值与 manifest `type` 一致 |
| 商店显示版本与实际安装包不一致 | manifest `version`、索引 `currentVersion`、Release 附件不同步 | 四者统一到同一版本号，重新打包上传 |
| `minHostVersion` 不匹配 / 插件不显示 | 写得太高，或与索引 `appVersion` 矛盾 | 按实际 API 需求填写；索引写 `appVersion: ">=<minHostVersion>"` |
| 安装后提示 `.xipk` 无效 / 缺少入口 | 手工压缩时没把 `main.js` 放在根级，或只放了 `main.ts` | 用 `xipm pack` 重新生成；确认根级有 `manifest.json` + `main.js` |
| `.xipk` 里有顶层目录壳 | 压缩了整个插件目录 `my-plugin/...` | 用 `xipm pack`，或进入构建输出目录再压缩 |
| 索引与 manifest 的 `capabilities` / `network` 不一致 | 手动改了一边 | 以 manifest 为准原样复制；跑 `validate_entry.py --manifest` |
| 图标不显示 | `icon` 写了 `resources/` 中不存在的文件名 | 补资源文件，或改用文字图标 |
| 运行时 `E_DENIED` | 请求域名没写进 `network.hosts`，或用户未授权 | 补白名单；用户自定义域名用 `allowCustomHosts: true` |
| `activation` / `configSchema` 不生效 | 宿主 v3 不消费旧字段 | 激活方式由 `type` 决定；配置表单用 `settings.schema()` |
| 测试通过但真机报错 | 没有跑 `xipm check`，manifest 能力与 `definePlugin` 不一致 | 发布前依次跑 `check`、`test`、`pack` |

提交前自查：

```bash
xipm check .
xipm test .
python3 scripts/validate_entry.py src/plugins/v2/<id>.yaml \
  --repo-root /path/to/xime-index \
  --manifest ./manifest.json \
  --asset-file ./<id>-<version>.xipk
```
