---
name: xime-index-submit
description: Use when submitting or updating a Xime keyboard layout or theme, plugin, input scheme, or model in the xime-index marketplace, or when fixing a xime-index PR or CI failure. Covers Release assets, sha256 and size, src YAML, local validation, and consent-gated push and PR creation.
---

# Xime Index 上架

把自制的布局 / 配色、插件、输入方案、模型上架到 `ximeiorg/xime-index`。流程固定为：
预检 → 分类 → 产物校验 → 发布取数 → 写 `src/` 条目 → 本地验证 → 提交 PR → 盯 CI →
合并后确认。

核心原则：

> 索引只存引用；`sha256` 是可信指纹；PR 只改 `src/`；`git push` 和开 PR 前必须确认。

需要两个目录：

- **技能目录**：本文件所在目录，含 `scripts/` 与 `references/`。
- **`xime-index` 克隆**：含上游 `src/` 与 `scripts/ci-update.py`。

没有 `xime-index` 克隆时，停在阶段 0，请用户提供路径或克隆；不要凭记忆生成 YAML。

## 何时使用

- 首次上架布局 / 配色、插件 v2、旧版插件 v1、输入方案、模型。
- 给已有条目发新版本、更新 `currentVersion`、补充校验值。
- 修已开的 `xime-index` PR：Validate Index 失败、链接 404、sha256 不一致、截图被拒。
- 审查现有条目是否符合当前规则，或检查上游规则是否漂移。

## 何时不要使用

- 开发布局、插件、Rime 方案或模型本身——用 `xime-docs`、`xipm` 和对应项目仓库。
- 修改 `xime-index` 的 `scripts/`、workflow、生成索引——属于维护者范围。
- 上传/托管 Release 资产、代管截图——本技能只校验和引用，不代办发布。
- 判断 License 的法律效力——只检查字段并请作者确认再分发权利。
- 没有产物、Release 地址或 `xime-index` 克隆——信息不足时不要猜。
- 合并 PR、改 `main`、强推历史——这些动作不在本技能授权范围内。

## 决策树

```text
要上架/更新什么？
├─ 布局 / 配色
│  └─ src/layouts/<id>.yaml        → references/layout.md
├─ 输入方案
│  └─ src/rimes/<id>.yaml          → references/rime.md
├─ 模型
│  └─ src/models/<id>.yaml         → references/model.md
├─ 插件
│  ├─ 新插件 / Xime >= 3.0.0
│  │  └─ src/plugins/v2/<id>.yaml  → references/plugin-v2.md
│  └─ 旧 App (< 3.0.0) 维护
│     └─ src/plugins/v1/<id>.yaml  → references/plugin-v1.md
└─ 不确定类型
   └─ references/index-rules.md 的「五类条目」
```

任务性质：

| 情况 | 做法 |
|---|---|
| 新条目 | 从 `templates/` 复制对应模板，填完整字段 |
| 版本更新 | `versions` 顶部加新记录，更新 `currentVersion`，保留旧版本 |
| 修 PR / CI | 先读 [troubleshooting.md](references/troubleshooting.md)，再回到阶段 5 |
| 只改元数据 | 不改版本号；涉及安装产物才升版本 |

一个条目只属于一类。布局带配色时仍走 `src/layouts/`，`tags` 写 `配色`；不要另造类型。

## 阶段 0：预检

- [ ] 确认 `xime-index` 克隆路径、当前分支和工作区状态。
- [ ] 运行 `preflight.py`，检查仓库结构、可选工具和上游规则漂移。
- [ ] 退出码 2（必需项失败）时停止；退出码 3（仅警告）时逐条向用户说明。
- [ ] `preflight.py --check-rules` 报告规则变化时，先读上游 diff、更新技能或确认影响，
      不要带着未知漂移继续。

```bash
# 在技能目录运行
python3 scripts/preflight.py \
  --repo /path/to/xime-index \
  --type layout \
  --check-rules
```

`--type` 取 `layout` / `plugin-v2` / `plugin-v1` / `rime` / `model`。缺少 `gh`、`uv`、
`npx` 只记为提示，不阻止流程；缺少 Python、PyYAML 或仓库路径才是失败。

**停止条件**：仓库不是 `xime-index`、`src/` 结构缺失、必需校验失败、规则漂移未解释。

## 阶段 1：分类

- [ ] 用决策树确定类型：布局、插件 v1/v2、输入方案、模型。
- [ ] 确定是新条目、版本更新，还是修 PR/CI。
- [ ] 通读对应 reference，不要只看模板。
- [ ] 检查 `id` 是否已存在；更新时先读现有 YAML，保留历史。

```bash
ls /path/to/xime-index/src/layouts
grep -R "^id: <id>$" /path/to/xime-index/src
```

新建插件默认 v2；只有维护旧 App 兼容条目才用 v1。输入方案的新条目要求
`id == schema_id`；布局 `id` 只允许 `[a-z0-9_]`；插件 `id` 用点号分段。

**停止条件**：无法判断类型、`id` 冲突且用户未决定、更新目标不存在或已被删除。

## 阶段 2：产物校验

先校验产物，再写索引。新条目还没有 YAML 时，先做下面的产物检查；写完条目后在
阶段 5 再跑完整交叉校验。

```bash
# 布局：初查根级是否有 xime.custom.yaml、是否带目录壳
unzip -l ./<layout>-<version>.zip

# 插件 v2：工具链自检 + 确认 .xipk 根级是 manifest.json / main.js
xipm check .
unzip -l ./<id>-<version>.xipk

# 输入方案：确认包含 .schema.yaml 与 .dict.yaml，并核对 schema_id
unzip -l ./<schema>-<version>.zip
grep -n "schema_id" ./<schema>.schema.yaml

# 模型：确认归档内容与 files 清单对应
tar -tjf ./<model>.tar.bz2 | head -30

# 所有类型：确认下载地址和校验值
python3 scripts/asset_meta.py "<downloadUrl>"
```

已有条目或已写好草稿 YAML 时，可以提前跑交叉校验：

```bash
python3 scripts/validate_entry.py /path/to/xime-index/src/<type>/<id>.yaml \
  --repo-root /path/to/xime-index \
  --asset-file ./<package>
# 插件另加 --manifest；方案另加 --schema；模型改用 --check-urls
```

`validate_entry.py --asset-file` 会在阶段 5 做完整的 zip 路径安全、扩展名和符号链接检查，
`unzip -l` 只是初查。

本阶段的 `asset_meta.py` 只用于初查。写入条目的 `sha256`/`size` 必须来自阶段 3 对实际
`downloadUrl` 的下载结果；本地构建产物只能用来交叉比对，不能直接当作发布值。

类型要点：

| 类型 | 必须确认 |
|---|---|
| 布局 / 配色 | Release 附件；zip 根级有 `xime.custom.yaml`；无 `..`/绝对路径/符号链接；截图是真实键盘 |
| 插件 v2 | `manifest.json` + `main.js`；`pluginType`、`minHostVersion`、`platforms`、`capabilities`、`network` 与索引一致 |
| 插件 v1 | 仅旧 App；包是旧版 Lua/DEX `.xipk`；不要写 v2 专有字段 |
| 输入方案 | `.zip`/`.tar.gz` 含 `.schema.yaml` 与 `.dict.yaml`；`id == schema_id`；依赖写方案 id |
| 模型 | `category` 合法；`files`/`archive` 二选一；归档为 `tar.bz2`；`.gram` 例外仅限 `downloadUrl` |

所有类型共同要求：下载地址是 GitHub Release 附件，版本号与产物一致，License 字段存在且
作者确认允许再分发，历史版本保留。

**停止条件**：zip 不安全、manifest 与索引不一致、`schema_id` 不符、`category` 非法、
缺少 License 确认、产物与版本号对不上。

## 阶段 3：发布与取数

- [ ] 确认交付物已上传为 **GitHub Release 附件**；分支、raw、`@main` 的 jsDelivr 都不行。
- [ ] **下载 `downloadUrl` 指向的实际附件**，计算 `sha256`、`size`、`sizeBytes`。
- [ ] 本地构建文件只用于交叉比对；不得用本地哈希代替附件哈希。
- [ ] 与作者提供的值比对；不一致时先停下确认上传的附件是否正确，再决定写入哪个值。
- [ ] 记录 URL、版本、日期、changelog，供阶段 4 写入。

```bash
# 在技能目录运行；--strict 对非 Release 地址给出警告（退出码 3）
python3 scripts/asset_meta.py "<downloadUrl>" --strict

# 已有期望值时直接断言
python3 scripts/asset_meta.py "<downloadUrl>" --expected-sha256 "<64 位十六进制>"
```

退出码：`0` 成功；`2` 下载失败；`3` `--strict` 下地址不是 Release 附件；`4` sha256 与
期望值不一致。

`.gram` 在 `downloadUrl` 中允许 `sha256: ""`，其它文件必须填。模型 `files[]` 没有这个
例外，能算就算。`sizeBytes` 用实际字节数，不要用 `size` 字符串反推。

下载失败、代理不可用或无法访问附件时，停止并说明。不要假设本地文件就是远端内容，
也不要把“本地算过哈希”说成“已验证发布附件”。

**停止条件**：附件不可下载、URL 可变、sha256 与作者值不一致且未解释、把分支地址当发布地址。

## 阶段 4：生成/更新条目

- [ ] 从 `templates/` 复制对应模板到 `src/<type>/<id>.yaml`。
- [ ] 填完整字段；文件名必须等于 `id`。
- [ ] 新版本放 `versions` 顶部，`currentVersion` 与它完全一致。
- [ ] 保留历史版本和旧附件；不要删除、不要覆盖旧 tag。
- [ ] 只写 `src/`，绝不手改 `index.yaml` 或子索引。

```bash
cp templates/layout.yaml /path/to/xime-index/src/layouts/<id>.yaml
```

模板：`layout.yaml`、`plugin-v2.yaml`、`plugin-v1.yaml`、`rime.yaml`、`model.yaml`。
字段含义以对应 reference 为准；模板里的空值必须替换成实际值。

缺少 `license`、`author`、`repo`、截图等无法从产物推断的字段时，向用户确认。
不要填 `MIT` 之类的常见默认值，也不要编造仓库地址或作者名。

版本更新时，新内容必须使用新 tag + 新 Release。下载地址保持不变不能作为复用旧 tag
的理由；现有 URL 只属于已经发布的旧版本，覆盖它会让旧版本的哈希失效。

更新版本时：

```yaml
currentVersion: "<新版本>"
versions:
  - version: "<新版本>"       # 新的在最上面
    date: "YYYY-MM-DD"
    changelog: "..."
    downloadUrl:
      - url: https://github.com/<owner>/<repo>/releases/download/<tag>/<asset>
        sha256: "<64 位十六进制>"
        size: "<人类可读>"
        sizeBytes: <整数>
  - version: "<旧版本>"       # 历史保留
```

**停止条件**：`currentVersion` 不在 `versions` 中、版本重复、历史被删、产物地址更新但
版本号没升、写入了生成索引。

## 阶段 5：本地验证

- [ ] 逐条运行 `validate_entry.py`，error 清零；warning 逐条确认。
- [ ] 在 `xime-index` 克隆内运行 `ci-update.py --check`。
- [ ] 涉及新链接时运行 `ci-update.py --verify`（会下载全部已记录 URL）。
- [ ] 确认 diff 只含 `src/`；生成文件如被本地脚本改动，恢复后再提交。

```bash
# 技能目录：布局/插件用 --asset-file；插件加 --manifest；
# 方案加 --schema；模型用 --check-urls
python3 scripts/validate_entry.py /path/to/xime-index/src/<type>/<id>.yaml \
  --repo-root /path/to/xime-index \
  --asset-file ./<package>

# xime-index 克隆内
cd /path/to/xime-index
python3 scripts/ci-update.py --check
python3 scripts/ci-update.py --verify

# 改动范围
git status --short
git diff --name-only
```

`validate_entry.py` 退出码：`0` 通过；`1` 校验错误；`2` 文件/用法错误；`3` 仅警告。
`ci-update.py --check` 缺 `sha256`/`size` 时退出 1；`--verify` 下载失败或哈希不一致时
退出 1。

生成索引被改动时，用 `upstream/main` 的版本恢复，只保留 `src/`；不要提交生成文件。
排查见 [troubleshooting.md](references/troubleshooting.md) 的「误改生成索引」。

**停止条件**：存在 error、`--check` 失败、diff 含 `src/` 以外文件、历史版本被删。

## 阶段 6：提交 PR

- [ ] 从 `upstream/main` 建分支：`submit/<type>/<id>-<version>`。
- [ ] 只暂存 `src/` 目标文件，commit 信息写清类型和条目。
- [ ] 向用户展示 diff、commit、将执行的 push/PR 命令，取得**明确同意**。
- [ ] 同意后 push 到 fork；再次确认后创建 PR。
- [ ] PR 正文使用模板，勾选真实完成的检查项。

```bash
git switch -c submit/layout/<id>-<version> upstream/main
git add src/layouts/<id>.yaml
git diff --cached --name-only       # 必须只有 src/
git commit -m "feat(layouts): 上架 <名称> <version>"
```

完整 fork 设置、PR 正文模板、`gh pr create` 和无 `gh` 的 compare URL 见
[pr-and-ci.md](references/pr-and-ci.md)。

**停止条件**：用户未同意 push 或开 PR。此时保留本地 commit，按「交接」输出命令，
不要执行推送。用户只同意 push 时，不要顺手创建 PR。

## 阶段 7：盯 CI

- [ ] 读取 PR 检查：Validate Index、链接探测；区分真实失败和网络抖动。
- [ ] 记住当前上游路径过滤可能让仅改 `src/` 的 PR 不触发检查；本地校验不能省。
- [ ] 失败按 [troubleshooting.md](references/troubleshooting.md) 定位，修复后重新验证。
- [ ] 需要更新 PR 时追加 commit；不要空提交、不要强推。

```bash
gh pr checks --watch
gh pr view --web
gh run list --repo ximeiorg/xime-index --limit 10
gh run view <run-id> --log-failed
```

`Auto-fill checksums` 只在合并到 `main` 后运行，不会替 PR 里的 `src/` 补值。
Validate Index 的 URL 探测只覆盖 `type: remote`，布局条目要自己跑 `--check-urls`。

**停止条件**：CI 红且原因未定位、用户要求跳过校验、有人提议合并。不要合并 PR，
合并权在维护者。

## 阶段 8：合并后

- [ ] 由维护者合并；不执行 `gh pr merge`，不开 auto-merge。
- [ ] 等 bot 提交 `ci: regenerate index files [skip ci]`，等 Validate Index / Deploy 变绿。
- [ ] 用 raw 索引确认新版本已上线。
- [ ] 提醒作者保留旧 Release 附件和历史版本。
- [ ] 删除远程分支、tag 或 Release 前单独取得确认。

```bash
# 按类型替换子索引：layouts / rimes / plugins / plugins/v2 / models
curl -s https://raw.githubusercontent.com/ximeiorg/xime-index/main/layouts/index.yaml \
  | grep -A3 'id: <id>'
```

合并后发现问题的，新开分支和 PR 修复；不要直接改 `main`，不要强推历史。

## 确认门

一次确认只覆盖一个动作。用户说“可以”不等于同意后续所有步骤；动作变化时重新确认。

| 动作 | 默认 | 要求 |
|---|---|---|
| 改文件、跑校验、本地 commit | 允许 | 说明改了什么、校验结果 |
| `git push` | 停止 | 展示 diff、分支、目标 remote 和完整命令，取得明确同意 |
| 创建 PR | 停止 | 展示 title、body、base/head，取得再次同意 |
| `git push --force` / 改写历史 | 禁止 | 单独确认；默认拒绝，优先追加提交 |
| 删除分支 / tag / Release / 资产 | 停止 | 单独确认，说明不可逆影响 |
| 安装 `gh` / `uv` / `xipm` 等工具 | 停止 | 先问用户；不运行来源不明的安装脚本 |
| 合并 PR | 禁止 | 由维护者执行；本技能不代劳 |
| 跳过校验或伪造校验结果 | 禁止 | 校验不是可协商项；push 可以同意，校验不能跳过。用户坚持时说明后果并停止 |
| 读取/写入 token | 禁止 | 不打印、不落盘、不写进命令历史或 YAML |

## 红线

| 借口 | 现实 | 正确做法 |
|---|---|---|
| “CI 会自动补 sha” | 只补生成索引，不写回 `src/`；`--check` 会失败 | 开 PR 前在 `src/` 填满 `sha256`/`size`/`sizeBytes` |
| “先用分支 URL，回头再改” | 内容一变哈希就失效，版本会被剔除 | 一开始就用 Release 附件 |
| “只改一个生成索引没关系” | 下次生成会被覆盖，违反贡献规则 | 只改 `src/`，生成文件交给 CI |
| “用户说快点，直接 push” | 速度不覆盖确认门 | 展示命令和 diff，取得明确同意 |
| “清空 sha 让 CI 变绿” | 掩盖了内容不一致，客户端会拒装 | 重新下载核对；内容变了就发新版本 |
| “旧版本删了省空间” | 破坏回滚和已发布条目的校验 | 保留全部历史版本和旧附件 |
| “v1 也能在 v3 跑” | v3 不加载 Lua/DEX 旧插件 | 新插件用 v2；v1 只维护旧 App |
| “截图差不多就行” | 必须是曦码键盘真实效果，分支 URL 会被拒 | 按截图规范重拍，钉 tag/commit |
| “规则漂移先不管” | 可能按过期规则生成条目 | 先读上游 diff，更新技能或确认无影响 |
| “合并后直接改 main 修一下” | 绕过 PR 和校验，可能破坏索引 | 新开分支和 PR |
| “本地文件已经算过 hash” | 用户下载的是 Release 附件，不是本地文件；上传失败或传错就全错 | 阶段 3 下载实际 URL，与本地值比对 |
| “用户说跳过检查，先 push” | 同意 push 不等于同意跳过校验；坏条目会影响所有用户 | 说明缺失项和风险；未通过校验不 push |
| “License/作者不知道，先填 MIT/tester” | 错误的授权声明会造成法律和信任问题 | 停下向作者确认；不确定就不提交 |
| “URL 不变，直接换文件” | 同 tag 覆盖会让旧版本哈希失效，违反发布规则 | 新版本用新 tag + 新 Release，保留旧附件 |
| “网络不通，先按本地值填” | 未验证的值会在 CI 或客户端暴露，你也无法声称已验证 | 停止并说明；等网络恢复或让作者提供官方哈希 |
| “已经推了，强推一下让历史干净” | 改写已推送历史会让协作者无法同步，也会掩盖错误提交 | 追加修复 commit；强推默认拒绝，必须单独确认 |
| “维护者说先跳过 sha256” | 无法验证的口头授权不能替代校验；缺哈希客户端会拒装 | 先补齐实际值；例外只能由维护者改规则并在 PR 中公开说明 |
| “布局和插件一起，一个 PR 省事” | 一个 PR 只能做一个条目；混合后维护者无法单独接受或回滚 | 按类型拆分支和 PR；共用改动先合并，再分别 rebase |

不要运行作者仓库里的脚本，不要把下载的插件/布局当代码执行；只调用本技能脚本和
`xime-index` 的官方脚本。

## 参考文件

| 场景 | 文件 |
|---|---|
| 通用规则、五类条目、`src/` 约束、sha256、CI | [index-rules.md](references/index-rules.md) |
| 布局 / 配色：交付形态、zip、截图 | [layout.md](references/layout.md) |
| 插件 v2：manifest、索引映射、xipm | [plugin-v2.md](references/plugin-v2.md) |
| 旧版插件 v1：适用范围、迁移 | [plugin-v1.md](references/plugin-v1.md) |
| 输入方案：包结构、`schema_id`、依赖 | [rime.md](references/rime.md) |
| 模型：两种分发、category、大小、`.gram` | [model.md](references/model.md) |
| PR、CI、合并后 | [pr-and-ci.md](references/pr-and-ci.md) |
| 按症状排错 | [troubleshooting.md](references/troubleshooting.md) |
| 上游规则快照与哈希 | [upstream.lock.json](references/upstream.lock.json) |

## 脚本

在技能目录运行；路径按实际安装位置调整：

| 脚本 | 何时运行 | 说明 |
|---|---|---|
| [preflight.py](scripts/preflight.py) | 阶段 0 | 检查仓库、工具、上游规则漂移；退出码 0/2/3 |
| [asset_meta.py](scripts/asset_meta.py) | 阶段 3 | 下载附件，输出 `sha256`/`size`/`sizeBytes`；支持 `--expected-sha256`、`--json`、`--strict` |
| [validate_entry.py](scripts/validate_entry.py) | 阶段 2/4/5 | 校验单条 YAML；布局 zip、插件 manifest、Rime schema；退出码 0/1/2/3 |
| [lib.py](scripts/lib.py) | 内部 | 下载、哈希、URL 分类等共享实现；通常不直接运行 |

脚本只依赖 Python 标准库和 PyYAML；`gh`、`uv`、`npx` 可选。下载资产只用于计算哈希，
不执行；zip 只读检查。不要用 `--no-verify` 代替提交前校验。

## 交接

用户拒绝 push / 开 PR 时，保留本地 commit，并输出可直接执行的下一步：

```bash
git push -u origin submit/<type>/<id>-<version>

gh pr create \
  --repo ximeiorg/xime-index \
  --base main \
  --head <owner>:submit/<type>/<id>-<version> \
  --title "<type>(<scope>): <说明>" \
  --body-file /tmp/opencode/xime-index-pr.md
```

没有 `gh` 时给出 compare URL：

```text
https://github.com/ximeiorg/xime-index/compare/main...<owner>:<branch>?expand=1
```

交接时说明：已运行的校验及结果、仍未验证的风险、目标分支、commit、PR 标题和正文位置。
不要替用户执行未确认的命令。

完成标准：条目通过 `validate_entry.py` 和 `ci-update.py --check`；diff 只含 `src/`；
PR 已创建并附校验结果（用户拒绝时已完成交接）；CI 状态和后续动作已明确交给用户或维护者。
