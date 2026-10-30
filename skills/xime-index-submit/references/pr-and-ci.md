# 提交 PR 与盯 CI

本文件覆盖上架流程的最后一段：从本地校验到开 PR、盯 CI、合并后确认。规则依据见
[index-rules.md](index-rules.md)，失败排查见 [troubleshooting.md](troubleshooting.md)。

## 前置

开 PR 前必须全部满足：

- [ ] 条目已通过技能校验：`validate_entry.py` 无 error（warning 已逐条确认）。
- [ ] 在 `xime-index` 克隆内通过上游检查：`ci-update.py --check`，涉及新链接时再跑
      `ci-update.py --verify`。
- [ ] `git diff` 只包含 `src/` 下的目标文件，没有生成索引、脚本或无关改动。
- [ ] 下载地址是 GitHub Release 附件；`sha256` / `size` / `sizeBytes` 已按实际附件填满。
- [ ] `currentVersion`、`versions[0].version`、Release 附件、插件 manifest 版本一致。
- [ ] 历史版本记录和旧 Release 附件都保留。
- [ ] 已运行 `preflight.py --check-rules`，没有未处理的上游规则漂移。
- [ ] 用户已明确同意推送分支和创建 PR。

```bash
# 技能目录内：检查仓库、工具和上游规则漂移
python3 scripts/preflight.py --repo /path/to/xime-index --type layout --check-rules

# 技能目录内：校验条目（按类型补充 --asset-file / --manifest / --schema）
python3 scripts/validate_entry.py /path/to/xime-index/src/layouts/<id>.yaml \
  --repo-root /path/to/xime-index \
  --asset-file ./<package>

# xime-index 克隆内：检查 src/ 是否缺 sha256/size
python3 scripts/ci-update.py --check

# xime-index 克隆内：下载并比对所有已记录的 sha256（较慢）
python3 scripts/ci-update.py --verify

# xime-index 克隆内：确认改动范围
git status --short
git diff --name-only upstream/main...HEAD
```

**确认门**：技能可以自动修改文件、跑校验、在本地 commit，但 `git push`、创建 PR、
强推、删除分支都必须先展示将执行的命令和 diff，得到用户明确同意后再做。不要用
`git push --force`、不要改写已推送的历史、不要把 token 写进命令行或 YAML。

## 分支与提交

外部贡献者走 Fork 流程：

```bash
# 首次：创建 fork（已有时跳过）
gh repo fork ximeiorg/xime-index --clone=false

# 克隆自己的 fork
git clone https://github.com/<owner>/xime-index.git
cd xime-index
git remote add upstream https://github.com/ximeiorg/xime-index.git
git fetch upstream

# 已有克隆：确认 origin 是自己的 fork，upstream 是官方仓库
git remote -v
git fetch upstream
```

从最新的 `upstream/main` 建分支，不要从过期的本地 `main` 建：

```bash
git switch -c submit/layout/qq_pinyin-1.0.0 upstream/main
```

分支命名固定为 `submit/<type>/<id>-<version>`：

| 类型 | `<type>` | 示例 |
|---|---|---|
| 布局 / 配色 | `layout` | `submit/layout/qq_pinyin-1.0.0` |
| 插件 v2 | `plugin-v2` | `submit/plugin-v2/com.example.daily_quote-0.1.0` |
| 旧版插件 v1 | `plugin-v1` | `submit/plugin-v1/com.example.legacy_emoji-2.1.0` |
| 输入方案 | `rime` | `submit/rime/my_schema-1.0.0` |
| 模型 | `model` | `submit/model/demo_asr-v1.0` |

同一分支只做一个条目的一次提交；需要修 PR 时继续在该分支追加提交。分支已存在时换个
后缀（如 `-2`），不要强推覆盖。

提交信息与 PR 标题同风格，写清类型和条目：

```text
feat(layouts): 上架 QQ拼音版布局 1.0.0
fix(layouts): xime_theme_pack 1.2.0 补充实际 sha256
feat(plugins): com.example.daily_quote 0.1.0
fix(rimes): my_schema 的 schema_id 与 id 对齐
feat(models): 新增 demo_asr v1.0
```

暂存时只加 `src/`，不要 `git add -A`：

```bash
git add src/layouts/qq_pinyin.yaml
git diff --cached --name-only    # 必须只有 src/...
git commit -m "feat(layouts): 上架 QQ拼音版布局 1.0.0"
```

## PR 标题与正文

标题格式：`<type>(<scope>): <一句话说明>`，例如：

```text
feat(layouts): 上架 QQ拼音版布局（qq_pinyin）
fix(plugins): 修正 com.example.daily_quote 的 manifest 版本
```

正文先写到仓库外的临时文件（如 `/tmp/opencode/xime-index-pr.md`），再传给 `gh`，
避免多行转义。模板：

````markdown
## 变更

- 新增布局 `qq_pinyin` 1.0.0
- 下载地址：https://github.com/you/my-layout/releases/download/v1.0.0/my-layout-1.0.0.zip
- 兼容 Xime `>=3.3.0`

## 类型

- [x] 布局 / 配色
- [ ] 插件 v2
- [ ] 旧版插件 v1
- [ ] 输入方案
- [ ] 模型

## 自查

- [x] 只修改 `src/`，未提交 `index.yaml` 等生成文件
- [x] `sha256` / `size` / `sizeBytes` 已按实际附件填写
- [x] 下载地址是 GitHub Release 附件，不使用分支 / raw / jsDelivr
- [x] `currentVersion` 与 `versions` 顶部版本一致
- [x] 保留全部历史版本和旧 Release 附件
- [x] 本地通过 `validate_entry.py`
- [x] 本地通过 `ci-update.py --check`
- [x] 截图是曦码键盘真实效果，固定到 tag/commit（不适用则 N/A）
- [x] 已确认 License 允许再分发

## 备注

本地校验输出（摘录）：

```text
PASS: 0 error(s), 1 warning(s)
```
````

不适用的小节和复选框可以删掉，但不要勾选没做过的项。维护者会核对 License、截图、
Release 附件和历史版本。

## 有 gh

```bash
# 确认登录状态；不要把 token 打印或写入文件
gh auth status
gh api user -q .login          # 得到 <owner>

# 推送 fork（执行前再次确认）
git push -u origin submit/layout/qq_pinyin-1.0.0

# 创建 PR；--head 必须是 <fork-owner>:<branch>
gh pr create \
  --repo ximeiorg/xime-index \
  --base main \
  --head <owner>:submit/layout/qq_pinyin-1.0.0 \
  --title "feat(layouts): 上架 QQ拼音版布局（qq_pinyin）" \
  --body-file /tmp/opencode/xime-index-pr.md

# 打开 PR 页面
gh pr view --web
```

说明：

- `--repo` 是上游仓库，不是自己的 fork。
- `--head` 不能只写分支名，也不能写 `ximeiorg:<branch>`。
- 想先收集反馈可加 `--draft`；准备好后执行 `gh pr ready`。
- 不要用 `--fill` 代替审阅后的标题/正文，也不要在命令里附带 token。
- **不要执行 `gh pr merge`**，合并由维护者决定。

## 无 gh

没有 `gh` 时，推送和开 PR 都在网页完成：

1. 确认后推送：`git push -u origin submit/layout/qq_pinyin-1.0.0`。
2. 打开跨仓库比较页：

   ```text
   https://github.com/ximeiorg/xime-index/compare/main...<owner>:<branch>?expand=1
   ```

   例如：

   ```text
   https://github.com/ximeiorg/xime-index/compare/main...tiengming:submit/layout/qq_pinyin-1.0.0?expand=1
   ```

3. 页面应显示 `base: ximeiorg/xime-index:main`、`compare: <owner>/xime-index:<branch>`。
   如果显示 “There isn't anything to compare”，检查 fork 是否已推送、分支名是否写错，
   或点 “compare across forks” 手动选择。
4. 粘贴上面模板的标题和正文，创建 PR。

分支名里的 `/` 可以直接放在 URL 中；若页面解析异常，用 “compare across forks”
手选 fork 和分支。fork 必须是公开可访问的；私有 fork 会让维护者无法查看。

## 盯 CI

当前快照（`06fd79c1b8754ded71d2e35c54c79efee4704ecc`）的 workflow：

| Workflow | 触发 | 做什么 |
|---|---|---|
| **Validate Index** | PR；push 到 `main` | 运行 `ci-update.py` 生成索引，校验子索引结构、v2 插件字段、主索引 `from` 引用，并探测 `type: remote` 条目的下载 URL |
| **Auto-fill checksums** | push 到 `main` 且 `src/**/*.yaml` 变化；可手动触发 | 生成索引、断言 `src/` 未被修改、提交生成的子索引（`ci: regenerate index files [skip ci]`） |
| **Deploy to Cloudflare Pages** | push 到 `main` | 重新生成索引并部署 |

**上游路径过滤缺口**：`validate.yml` 的 `pull_request.paths` 目前**不含 `src/**`**，
所以只改 `src/` 的 PR 可能根本不触发 Validate Index，PR 页面上没有任何 check run。
这是上游 workflow 的问题，不是你的条目没问题，也**不要**为了触发 CI 去改生成索引或
无关文件。正确做法：

- 在 PR 正文里贴出本地 `validate_entry.py` 和 `ci-update.py --check` 的结果；
- 在 PR 里说明“本次仅改 `src/`，当前 workflow 路径过滤可能不触发 Validate Index”；
- 需要强制检查时请维护者决定是否调整 workflow（属于维护者范围）。

如果检查确实运行了，常用命令：

```bash
gh pr checks --watch                 # 等所有检查结束
gh pr view --web                     # 看 PR 与检查详情
gh run list --repo ximeiorg/xime-index --limit 10
gh run view <run-id> --log-failed    # 只看失败步骤日志
```

失败路由：

| 失败信息 | 去哪 |
|---|---|
| `sha256` 不一致 / 版本被剔除 | [troubleshooting.md#sha256-不一致](troubleshooting.md#sha256-不一致) |
| URL 探测 404 / timeout | [troubleshooting.md#链接-404](troubleshooting.md#链接-404) |
| `missing pluginType` / v2 字段缺失 | [plugin-v2.md](plugin-v2.md) 的「索引字段映射」 |
| `id 不匹配，跳过` | [troubleshooting.md#id-与文件名不一致](troubleshooting.md#id-与文件名不一致) |
| YAML 解析 / 字段类型错误 | 本地跑 `validate_entry.py`，按 error 修 |
| 结构校验通过但链接超时 | 多为网络抖动或 GitHub 限流，先重跑失败 job |

重跑而不是空提交：

```bash
gh run rerun <run-id> --failed
```

需要修代码时，在同一分支追加提交：先本地重新校验，再推送（仍需确认）。不要为了
“让 CI 变绿”而清空 `sha256`、改生成文件或删历史版本。

## 合并后

- **不要自己合并**，也不要开 auto-merge；合并由 `xime-index` 维护者完成。
- 合并后 `Auto-fill checksums` 会在 `main` 上运行并提交 `ci: regenerate index files
  [skip ci]`。不要从自己的 fork 再提交生成索引，否则会和 bot 冲突。
- bot 提交后，`Validate Index` 和 `Deploy to Cloudflare Pages` 会因生成文件变化而运行；
  等它们变绿。
- 确认上线：

  ```bash
  curl -s https://raw.githubusercontent.com/ximeiorg/xime-index/main/layouts/index.yaml \
    | grep -A3 'id: qq_pinyin'
  ```

  应能看到新版本和下载地址。App 内商店可能有缓存，刷新索引或重启后再看。
- 永远保留旧 Release 附件和历史版本记录；它们用于回滚，也是已发布条目的校验依据。
- 合并后可删除自己的分支，但删除远程分支属于破坏性操作，需单独确认：

  ```bash
  git push origin --delete submit/layout/qq_pinyin-1.0.0
  ```

- 若合并后发现条目有问题，新开分支和 PR 修复；不要直接改 `main` 或强推历史。
