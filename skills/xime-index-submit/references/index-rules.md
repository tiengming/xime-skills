# xime-index 上架规则

> 本文件是 `xime-index-submit` 技能内的规则摘要，依据 **2026-10-30** 的上游快照编写。
> 上架前请用 `preflight.py --check-rules` 确认上游规则没有变化；冲突时以 `xime-index`
> 仓库当前的脚本行为为准。

## 唯一事实来源

xime 的扩展生态由三个仓库分工：

| 仓库 | 角色 | 你在这里做什么 |
|---|---|---|
| 作者自己的仓库（如 `you/my-layout`） | 存放布局、主题、插件、方案、模型产物，用 GitHub Release 提供不可变附件 | 打 tag、建 Release、上传产物与截图 |
| [`ximeiorg/xime-index`](https://github.com/ximeiorg/xime-index) | 市场索引：`src/` 下每个条目一个 YAML，CI 生成子索引并部署 | 新增/修改 `src/` 条目，开 PR |
| [`ximeiorg/xime-docs`](https://github.com/ximeiorg/xime-docs) | 官方文档：插件开发、键盘配置 v2、功能说明 | 查解释性文档，不直接决定索引字段 |

上游规则文件（钉在快照 commit
`06fd79c1b8754ded71d2e35c54c79efee4704ecc`）：

- [CONTRIBUTING.md](https://github.com/ximeiorg/xime-index/blob/06fd79c1b8754ded71d2e35c54c79efee4704ecc/CONTRIBUTING.md)
- [LAYOUT_SPEC.md](https://github.com/ximeiorg/xime-index/blob/06fd79c1b8754ded71d2e35c54c79efee4704ecc/LAYOUT_SPEC.md)
- [scripts/ci-update.py](https://github.com/ximeiorg/xime-index/blob/06fd79c1b8754ded71d2e35c54c79efee4704ecc/scripts/ci-update.py)
- [scripts/lib.py](https://github.com/ximeiorg/xime-index/blob/06fd79c1b8754ded71d2e35c54c79efee4704ecc/scripts/lib.py)

解释性文档：

- [插件开发指南](https://github.com/ximeiorg/xime-docs/blob/main/docs/plugins/PLUGIN_DEVELOPMENT_GUIDE.md)
- [键盘配置 v2](https://github.com/ximeiorg/xime-docs/blob/main/docs/features/keyboard-config-v2.md)

本技能在 [upstream.lock.json](upstream.lock.json) 里记录了快照 commit 和上述四个规则文件的
sha256。运行：

```bash
python3 scripts/preflight.py --repo /path/to/xime-index --check-rules
```

会拉取上游 `main` 并比对。出现 `上游规则已变化，需要复核` 时，先读上游 diff、更新技能，
再继续上架；不要盲信本文件。

**优先级**：`ci-update.py` / `lib.py` 的实际行为 > `CONTRIBUTING.md` 的散文 > 本摘要。
两者已知的冲突点是 `sha256`/`size` 是否“可选”，见下文。

## 五类条目

每类条目一个 YAML，放在固定的 `src/` 子目录；文件名必须等于条目 `id`。

| 类型 | 源文件 | 生成的子索引 | 生成键 | `index_version` | 交付物 |
|---|---|---|---|---|---|
| 布局 / 配色 | `src/layouts/<id>.yaml` | `layouts/index.yaml` | `layouts` | 1 | `xime.custom.yaml` 或根级 zip |
| 输入方案 | `src/rimes/<id>.yaml` | `rimes/index.yaml` | `schemas` | 1 | `.zip` / `.tar.gz` |
| 模型 | `src/models/<id>.yaml` | `models/index.yaml` | `models` | 1 | 单文件列表或 `tar.bz2` 归档 |
| 插件 v1（旧版） | `src/plugins/v1/<id>.yaml` | `plugins/index.yaml` | `plugins` | 1 | `.xipk`（Lua/DEX） |
| 插件 v2 | `src/plugins/v2/<id>.yaml` | `plugins/v2/index.yaml` | `plugins` | 2 | `.xipk`（`manifest.json` + `main.js` + `resources/`） |

要点：

- `ci-update.py` 逐文件读取；`data["id"]` 与文件名不一致时打印
  `id 不匹配，跳过`，该条目不会进入索引。
- 布局 `id` 只允许 `[a-z0-9_]`；插件 `id` 用点号分段（如
  `com.example.my_plugin`，字母/数字/下划线/连字符，≤64）；输入方案的 `id`
  必须等于 `.schema.yaml` 里的 `schema_id`。
- 插件 v1 只为兼容旧版 App 保留；新插件一律用 v2。
- 模型 `category` 可用 `prediction` / `asr` / `punctuation` / `stroke` / `other`；
  `handwriting` 仅出现在旧条目中，技能会给出兼容性警告。
- 五类模板见 [templates/](../templates/)，布局另见 [layout.md](layout.md)。

## PR 只改 src

PR 只能修改 `src/` 下的条目文件。以下文件全部由 `scripts/ci-update.py` 生成，**不要手改、
不要提交到 PR**：

```text
index.yaml                    # 主索引，引用各子索引
rimes/index.yaml
plugins/index.yaml
plugins/v2/index.yaml
models/index.yaml
layouts/index.yaml
```

原因：

- `ci-update.py` 从 `src/` 读条目，只把白名单字段投影到子索引；手改生成文件会在下次
  生成时被覆盖。
- PR 合并到 `main` 后，`update-checksums.yml` 会自动重新生成并提交子索引
  （提交信息 `ci: regenerate index files [skip ci]`），不需要作者代劳。
- 改动 `scripts/`、workflow、根 `index.yaml` 属于维护者范围，PR 里出现会被要求拆分。

本地验证后建议清掉生成文件再提交，只暂存 `src/`：

```bash
python3 scripts/ci-update.py --no-verify
git checkout -- index.yaml rimes/index.yaml plugins/index.yaml plugins/v2/index.yaml models/index.yaml layouts/index.yaml
git status --short          # 应只看到 src/ 下的改动
```

PR / commit 标题建议带类型和条目 id，例如：

```text
layouts(qq_pinyin): 新增 1.0.1 版本（兼容 3.3.0）
plugins(v2)(com.example.my_plugin): 新增 0.1.0
rimes(my_schema): 修正 schema_id
models(my-model): 补充 v1.0 文件校验值
```

维护者会核对：License 是否允许再分发、截图是否真实键盘效果、产物是否为 Release 附件、
是否保留历史版本、是否夹带生成文件或无关改动。

## sha256 与 size

下载项可能出现在三处：普通条目的 `versions[].downloadUrl[]`、模型的
`versions[].archive`、模型的 `versions[].files[]`（带 `url` 时）。三者字段含义相同：

| 字段 | 类型 | 含义 |
|---|---|---|
| `sha256` | 64 位十六进制字符串 | 内容指纹；客户端下载后强校验，不匹配直接丢弃 |
| `size` | 人类可读字符串，如 `11.9 KB` / `1.2 MB` | 展示用大小 |
| `sizeBytes` | 正整数 | 精确字节数；商店显示与排序用，模型总大小也由它汇总 |

### 上游脚本的真实行为

`ci-update.py` 的文档字符串写明：**只读 `src/`，不会修改任何源文件**。

- 生成时（默认或 `--verify`）会下载每个带 `sha256` 的 URL 并比对。不一致的版本会被
  **整版剔除**，不进入生成的子索引；若 `currentVersion` 指向被剔除的版本，
  `currentVersion` 回退到剩余的第一个版本。
- 下载失败（网络错误、404 等）只打印警告，该版本**仍会进入索引**——所以链接可达性
  必须自己先验证。
- `--verify`：只校验，不写任何文件；有 sha256 不一致或下载失败时退出 1。
- `--check`：只检查 `src/` 中是否缺 `sha256`/`size`，缺了就退出 1；`.gram` 文件和
  `master`/`main` 版本跳过。
- `--no-verify`：生成时跳过 `check_checksums` 下载比对，但仍会用填充函数计算缺失的
  校验值。
- `sizeBytes` 与真实字节数不一致只产生 `size_warn`，不会剔除版本；`size` 字符串不参与
  校验。

### 与 CONTRIBUTING.md 的差异

`CONTRIBUTING.md` 多处把 `sha256`/`size` 写成“可选，CI 自动补全”。准确理解是：

- CI 会把补全后的值写进**生成的子索引**，但**不会写回 `src/`**；
- `update-checksums.yml` 也只提交生成的子索引，并明确断言 `src/` 未被修改；
- 因此 `src/` 条目缺 `sha256`/`size` 时，`--check` 会失败，PR 也不应依赖“合并后自动补”。

本技能采用更严格的策略：**开 PR 前就在 `src/` 条目里填满 `sha256`、`size`、`sizeBytes`**。
这样生成的索引、Release 附件和本地校验三者一致，也避免维护者合并后才暴露问题。

### 计算校验值

技能自带脚本直接下载 URL 并输出全部字段：

```bash
python3 scripts/asset_meta.py https://github.com/you/repo/releases/download/v1.0.0/pkg.zip
# url / sha256 / size / sizeBytes / kind / immutable / policy
```

- 加 `--expected-sha256 <hex>` 可断言已有值；
- 加 `--strict` 时，非 GitHub Release 附件会以退出码 3 提示；
- 也可以从 GitHub Release 页面的附件 digest 读取，或用 `sha256sum <file>` 本地计算。

`.gram` 文件在 `downloadUrl` 中允许 `sha256: ""`：上游 `--check` 和填充函数会跳过它，
`check_checksums` 则把它记为“未记录 sha256、无法校验”。模型的 `files[]` 若也放 `.gram`，
技能会放行空 `sha256`，但上游 `--check` 不会为 `files[]` 开这个例外；能计算就计算。

## 版本更新

已有条目发新版本的顺序：

1. 在 `versions` 列表**顶部**新增一条完整记录（`version`、`date`、`changelog`、
   `downloadUrl` 或模型 `archive`/`files`）。
2. 把 `currentVersion` 改成新版本号，字符串必须与 `versions[].version` 完全一致。
3. 新版本使用新的 tag 和新的 Release 附件；**不要删除或替换旧版本的 Release 资产**，
   历史版本用于回滚，索引会保留。
4. 填好新版本的 `sha256`/`size`/`sizeBytes`。
5. 本地运行 `python3 scripts/ci-update.py --check` 和一次生成校验，再开 PR。

示例（布局，节选）：

```yaml
currentVersion: "1.0.1"
versions:
  - version: "1.0.1"          # 新版本放最上面
    date: "2026-10-30"
    changelog: 修复候选栏间距
    downloadUrl:
      - url: https://github.com/you/my-layout/releases/download/v1.0.1/my-layout-1.0.1.zip
        sha256: "<64 位十六进制>"
        size: "12.0 KB"
        sizeBytes: 12288
  - version: "1.0.0"          # 旧版本保留
    date: "2026-10-01"
    changelog: 初始发布
    downloadUrl:
      - url: https://github.com/you/my-layout/releases/download/v1.0.0/xime.custom.yaml
        sha256: "<旧版本 sha256>"
        size: "11.9 KB"
        sizeBytes: 12185
```

其它规则：

- 同一文件里 `version` 不能重复；`currentVersion` 必须能在 `versions` 中找到。
- 新条目不要用 `master` / `main` 作为版本号——分支内容会变，`sha256` 必然失效。
  历史条目保留的分支版本只做兼容，不再新增。
- `date` 用 `YYYY-MM-DD`；`changelog` 写用户能看懂的变更，不要留空。
- 版本号建议语义化；模型可使用 `v1.0` 这类标签，但必须前后一致。

## 常见 CI 检查

| Workflow | 触发 | 做什么 |
|---|---|---|
| **Validate Index**（`validate.yml`） | PR；push 到 `main` | 运行 `ci-update.py` 生成索引，校验各子索引结构、`plugins/v2` 的 `index_version: 2` / `pluginType` / `downloadUrl.url`、主索引的 `from` 引用，并逐个请求所有 `type: remote` 条目的下载 URL；任一请求失败即退出 1 |
| **Auto-fill checksums**（`update-checksums.yml`） | push 到 `main` 且改动 `src/**/*.yaml`；可手动触发 | 运行 `ci-update.py`，断言 `src/` 未被修改，然后只提交五个生成的子索引（`ci: regenerate index files [skip ci]`） |
| **Deploy to Cloudflare Pages**（`deploy.yml`） | push 到 `main` | 再生成一次索引，`build_dist.py` 构建 `dist/`，部署到 Cloudflare Pages |

本地对应命令：

```bash
python3 scripts/ci-update.py --check      # 只查 src 缺不缺 sha256/size
python3 scripts/ci-update.py --verify     # 下载并比对 sha256，不写文件
python3 scripts/ci-update.py              # 校验 + 生成子索引（src 只读）
python3 scripts/ci-update.py --no-verify  # 跳过 sha256 比对，快速生成
```

PR 前至少跑 `--check`；涉及新链接时再跑一次默认生成，确认没有版本被剔除。
Validate Index 的 URL 探测会访问每一个 `type: remote` 历史版本，网络抖动或 GitHub 限流都可能
造成红叉，重跑通常可排除偶发失败；持续失败则检查链接是否被删除或仓库是否转为私有。
布局条目没有 `type` 字段，会被这一步跳过；布局的下载地址必须自己用 `asset_meta.py`
或 `validate_entry.py --check-urls` 验证。

规则漂移提醒：如果 `preflight.py --check-rules` 报告 `CONTRIBUTING.md`、
`LAYOUT_SPEC.md`、`ci-update.py` 或 `lib.py` 变化，先停止提交，读上游 diff 并更新本技能；
本文件描述的是快照 `06fd79c1b8754ded71d2e35c54c79efee4704ecc` 的行为。
