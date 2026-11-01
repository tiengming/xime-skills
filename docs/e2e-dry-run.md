# 端到端 dry run

日期：2026-11-01
目的：在真实 `ximeiorg/xime-index` 克隆上跑一遍“校验已有条目 → 添加样例条目 → 结构校验 →
生成器检查 → 清理”，确认技能脚本和上游脚本能配合工作。不 push、不改上游。

## 环境

- 克隆：`/tmp/opencode/xime-index-e2e`，`git clone --depth 50` 自
  `https://github.com/ximeiorg/xime-index.git`。
- 克隆到的 HEAD：`06fd79c ci: regenerate index files [skip ci]`。
- 网络经代理 `HTTPS_PROXY=http://127.0.0.1:10809`。
- 技能目录：`/home/tieng/project/xime/xime-skills/skills/xime-index-submit`。

## 1. 校验已有真实条目

```bash
python3 .../scripts/validate_entry.py \
  src/layouts/xime_theme_pack.yaml --repo-root . --check-urls
```

结果：

```text
type: layout
id:   xime_theme_pack
warning: screenshot 使用 jsdelivr-tag ...（5 张）
warning: 版本 1.2.0: downloadUrl 建议补充 sizeBytes
warning: 版本 1.1.0: downloadUrl 建议补充 sizeBytes
OK: 0 error(s), 7 warning(s)
exit=3
```

结论：真实条目的下载地址可达，历史版本符合预期地产生“非 Release 截图”和“缺
`sizeBytes`”警告；没有 error。退出码 3 语义正确（仅警告）。

## 2. 添加样例条目并做结构校验

计划中的命令直接把 `tests/fixtures/layout/valid.yaml` 复制为 `e2e_sample.yaml`，但夹具的
`id` 是 `demo_layout`，与文件名不一致。第一次运行按预期报错：

```text
error: filename must equal id: 文件名为 'e2e_sample'，id 为 'demo_layout'
FAILED: 1 error(s), 2 warning(s)
exit=1
```

把 `id` 改为 `e2e_sample` 后重跑：

```text
type: layout
id:   e2e_sample
warning: screenshot 使用 jsdelivr-tag ...
warning: 版本 1.0.0: downloadUrl 建议补充 sizeBytes
OK: 0 error(s), 2 warning(s)
exit=3
```

结论：结构校验通过；样例的假 URL 没有被访问（未加 `--check-urls`），符合计划。

## 3. 生成器检查

```bash
python3 scripts/ci-update.py --check
```

实际结果：**exit 1**，列出 12 条上游既有条目的 `缺 sha256/size`：

```text
src/rimes/builtin.yaml
src/rimes/xqzm.yaml
src/plugins/v1/...（多条旧插件）
src/models/predictive-text-base.yaml
```

`e2e_sample` 不在输出中。删除样例后再次运行，仍是同样的 12 条、同样 exit 1。

这与计划里的“Expected: `ci-update.py --check` exits 0”不一致。原因是当前
`upstream/main` 本身就有历史条目缺校验值，不是样例引入的。不能为了让它变绿去改生成索引
或伪造校验值；正确的 PR 做法是：

- 在 PR 正文里说明 `--check` 的失败项全部是既有条目，并附上“删除本条目后仍失败”的证据；
- 保证本条目自己的 `sha256`/`size`/`sizeBytes` 完整；
- 由维护者决定是否先修基线。

## 4. 改动范围与清理

样例存在时：

```text
git status --short
?? src/layouts/e2e_sample.yaml

git diff --name-only
src/layouts/e2e_sample.yaml
```

删除样例后 `git status --short` 为空。没有修改 `layouts/index.yaml` 或任何其它生成文件，
没有 commit、没有 push。

## 5. 无 `gh` 的 compare URL

```python
from lib import github_compare_url
github_compare_url("ximeiorg/xime-index", "tester", "submit/layout/demo-1.0.0")
```

输出：

```text
https://github.com/ximeiorg/xime-index/compare/main...tester:submit/layout/demo-1.0.0?expand=1
```

与预期一致。

## 结论

- 技能脚本能在真实克隆上校验真实条目；`--check-urls` 可用。
- 样例条目在 `id` 与文件名一致时结构通过。
- 当前上游基线使 `ci-update.py --check` 无法全绿；技能要求“不要为变绿改生成文件/猜校验值”
  的处理方式仍然成立。
- 完整 push/PR 仍未执行；留给 Task 17 的发布步骤，并且需要用户明确确认。
