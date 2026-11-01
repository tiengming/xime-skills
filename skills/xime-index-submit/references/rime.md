# 输入方案（Rime）上架

输入方案是 Rime 配置包，用户在「扩展商店 → 输入方案」下载后启用并部署。
源文件放在 `src/rimes/<id>.yaml`，生成 `rimes/index.yaml`（键 `schemas`）。
通用索引规则见 [index-rules.md](index-rules.md)。

## 包结构

交付物是 `.zip` 或 `.tar.gz`，至少包含：

```text
my_schema-1.0.0.zip
├── my_schema.schema.yaml      # 方案定义，schema_id: my_schema
├── my_schema.dict.yaml        # 方案引用的词典
├── my_schema.custom.yaml      # 可选：方案补丁
├── symbols.yaml               # 可选：符号表
├── opencc/                    # 可选：简繁转换等数据
└── lua/                       # 可选：方案依赖的 Lua 脚本
```

要求：

- 方案文件里的 `schema_id` 要与文件名、索引 `id` 一致（见下节）。
- 方案引用的所有 `.dict.yaml`、`opencc/` 数据、`lua/` 脚本都要打进包里；
  缺文件会在用户「部署方案」时报错。
- 不要打包个人数据：`*.userdb/`、`build/`、`sync/`、`installation.yaml`、
  `user.yaml` 等；它们会污染用户的 `rime/` 目录。
- 不要附带 `default.custom.yaml` 之类的全局补丁，除非你明确要改用户全局配置。
- 包内可以含多个方案文件，但索引 `id` 指向主方案；不要用多个 `schema_id` 混淆主方案。
- GitHub 的 tag 归档（`archive/refs/tags/<tag>.zip`）会自动带一层
  `<repo>-<tag>/` 目录，这是方案包的正常形态，和布局 zip 的“禁止顶层目录壳”规则不同。

## id 与 schema_id

新条目（`type: remote`）要求三者一致：

```text
文件名 <id>.yaml  ==  条目 id  ==  主方案 .schema.yaml 里的 schema_id
```

例如：

```yaml
# src/rimes/my_schema.yaml
id: my_schema
```

```yaml
# my_schema.schema.yaml
schema:
  schema_id: my_schema
  name: 我的方案
```

原因：

- 客户端按 `schema_id` 识别方案、处理 `dependencies` 和部署；
- `ci-update.py` 按文件名匹配 `id`，不一致会直接跳过该条目；
- 技能用 `--schema` 校验时，`schema_id` 不一致会报错。

历史例外：`built-in` 条目和部分早期多方案包使用了“市场 id”，例如
`rime-ice` 的索引 id 是 `rime-ice`，而包内主 `schema_id` 是 `rime_ice`。
这些是兼容旧数据，**不要拿它们当新条目的模板**。`built-in` 条目由 Xime
维护者管理，社区新方案一律用 `type: remote`。

## 依赖

`dependencies` 是必填列表，写其它方案的 **`schema_id`**，不是显示名：

```yaml
dependencies: []                 # 无依赖
# 或
dependencies: [luna_pinyin, stroke, cangjie]
```

规则：

- 依赖项必须能在索引或内置方案中找到；写错 id 会导致安装/部署失败。
- 安装时会自动处理依赖，但索引只按 id 声明，**不能指定依赖的版本**；依赖使用其
  当前版本。
- 只写真正需要的方案。`symbols` / `essay` 这类共享包按实际引用声明。
- 不要写自己，避免循环依赖。
- 依赖是列表，不能写成字符串；技能会直接报错。

## 版本与下载地址

索引字段：

| 字段 | 必填 | 说明 |
|---|---|---|
| `type` | ✅ | 商店方案固定 `remote`；仅应用内置方案用 `built-in` |
| `appVersion` | ✅ | 兼容的 App 版本，如 `">=2.3.0"` / `">=3.2.3"` |
| `currentVersion` | ✅ | 当前版本，必须与 `versions[].version` 一致 |
| `versions[].version` | ✅ | 版本号或 tag；新的放最上面 |
| `versions[].date` | ✅ | `YYYY-MM-DD` |
| `versions[].changelog` | ✅ | 更新说明 |
| `versions[].downloadUrl[].url` | ✅ | 不可变下载地址 |
| `versions[].downloadUrl[].sha256` | ✅ | 64 位十六进制 |
| `versions[].downloadUrl[].size` | ✅ | 人类可读大小 |
| `versions[].downloadUrl[].sizeBytes` | 建议 | 精确字节数 |

下载地址优先级：

1. **GitHub Release 附件**（推荐，发布后不可变）：
   `https://github.com/you/repo/releases/download/v1.0.0/my_schema-1.0.0.zip`
2. **GitHub tag 归档**（tag 本身不可变）：
   `https://github.com/you/repo/archive/refs/tags/v1.0.0.zip`
3. 分支归档 / raw / jsDelivr：**不要用于新条目**，内容会变，`sha256` 会失效。

历史条目里有 `version: master`、`.../refs/heads/master.zip` 且 `sha256: ""` 的写法
（如 `luna_pinyin`），那是旧数据；上游对 `master`/`main` 版本会跳过校验，但新条目
不要模仿。

多个下载项：

```yaml
# 全部必装：不带 name，客户端会安装每一项
downloadUrl:
  - url: https://github.com/you/repo/releases/download/v1.0.0/my_schema-1.0.0.zip
    sha256: "<64 位十六进制>"
    size: "1.2 MB"
    sizeBytes: 1258291
  - url: https://github.com/you/repo/releases/download/v1.0.0/extra.gram
    sha256: ""
    size: "380 MB"
    sizeBytes: 398458880
```

```yaml
# 二选一：带 name，客户端让用户选择
downloadUrl:
  - name: 基础版
    url: https://github.com/you/repo/releases/download/v1.0.0/base.zip
    sha256: "<64 位十六进制>"
    size: "1.2 MB"
  - name: 完整版
    url: https://github.com/you/repo/releases/download/v1.0.0/full.zip
    sha256: "<64 位十六进制>"
    size: "42 MB"
```

`.gram` 文件允许 `sha256: ""`；其它文件不要留空。校验值用：

```bash
python3 scripts/asset_meta.py \
  https://github.com/you/repo/releases/download/v1.0.0/my_schema-1.0.0.zip
```

更新版本：

1. 修改方案/词典，打新 tag，建新 Release 并上传新包；
2. 在 `src/rimes/<id>.yaml` 的 `versions` 顶部新增记录；
3. 更新 `currentVersion`、`sha256`、`size`、`sizeBytes`；
4. 旧版本记录和旧附件保留，不要覆盖旧 tag；
5. 跑 `ci-update.py --check` 和 `validate_entry.py --schema`。

本地校验：

```bash
python3 scripts/validate_entry.py src/rimes/<id>.yaml \
  --repo-root /path/to/xime-index \
  --schema ./my_schema.schema.yaml
```

`--schema` 会读取标准写法 `schema:` 段内的 `schema_id`（也兼容顶层 `schema_id`），
与索引 `id` 不一致时直接报错。

## 常见错误

| 现象 | 原因 | 修复 |
|---|---|---|
| 条目被 CI 跳过 | 文件名与 `id` 不一致 | 文件名改成 `<id>.yaml` |
| 技能报 `schema_id 与 id 不一致` | 索引 id 与主方案 `schema_id` 不同 | 统一三者；不要照抄 `rime-ice` 等历史例外 |
| 安装后不显示方案 / 无法启用 | 包内没有 `.schema.yaml`，或 `schema_id` 拼错 | 补方案文件并核对 `schema` 段 |
| 部署时报词典缺失 | 漏打 `.dict.yaml` 或其引用的 opencc/lua 数据 | 把方案引用的全部文件打进包 |
| 依赖安装失败 | `dependencies` 写了显示名或错误 id | 改成其它方案的精确 `schema_id`，并确认其存在 |
| PR 后链接失效 / 版本被剔除 | 用了分支归档或 raw，内容已变 | 改用 Release 附件或 tag 归档，重新计算 sha256 |
| `--check` 报缺 sha256/size | 新版本留空，指望 CI 写回 src | 在 `src/` 里填满；CI 只写生成的子索引 |
| 用户主题/全局配置被改 | 包里带了 `default.custom.yaml` 或 `user.yaml` | 删除全局补丁和个人数据，只发方案自身文件 |
| 二选一的包被全部安装 | 多个 `downloadUrl` 没写 `name` | 需要用户选择时给每项加 `name` |
| 版本号对不上 | `currentVersion` 不在 `versions` 中，或复制后忘改 | 修正 `currentVersion`，删除重复版本 |

规则漂移提醒：本文件依据快照
`06fd79c1b8754ded71d2e35c54c79efee4704ecc`。如果 `preflight.py --check-rules`
报告 `CONTRIBUTING.md` / `scripts/ci-update.py` 变化，先复核再提交。
