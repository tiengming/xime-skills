# 故障排查

按症状查表；每条给出可能原因和修复路径。提交前的完整校验见
[pr-and-ci.md](pr-and-ci.md)，字段定义见 [index-rules.md](index-rules.md)。

| 症状 | 跳到 |
|---|---|
| CI 报 `sha256` 不一致，或版本从索引消失 | [sha256 不一致](#sha256-不一致) |
| 下载地址 404、超时、CI 链接探测失败 | [链接 404](#链接-404) |
| 条目没进索引，日志有 `id 不匹配，跳过` | [id 与文件名不一致](#id-与文件名不一致) |
| 维护者退回截图 | [截图被拒](#截图被拒) |
| PR diff 里出现 `index.yaml` / 子索引 | [误改生成索引](#误改生成索引) |
| 插件装了不显示，或旧 App 装不上 | [v1/v2 混淆](#v1v2-混淆) |
| 商店仍显示旧版本，更新不出现 | [版本未递增](#版本未递增) |
| `ci-update.py --check` 退出 1 | [`ci-update.py --check` 失败](#ci-updatepy---check-失败) |
| `category` 被拒 | [模型 category 未知](#模型-category-未知) |
| 布局 zip 被客户端拒绝 | [zip 结构被拒](#zip-结构被拒) |
| 插件索引与 manifest 对不上 | [插件 manifest 与索引不一致](#插件-manifest-与索引不一致) |
| PR 页面没有任何 CI 检查 | [CI 没有触发](#ci-没有触发) |

## sha256 不一致

**症状**：`ci-update.py --verify` 或 Validate Index 报 `sha256 不一致`；该版本被整版
剔除，生成的子索引里看不到；客户端下载后校验失败、拒绝安装。

**可能原因**：

- `downloadUrl` 指向分支、raw、`@main` 的 jsDelivr，内容已变；
- 同一个 tag / Release 下替换了附件，或 tag 被移动；
- `sha256` 是从旧构建、别的版本复制的，或算完之后又重打了包；
- 填了 SHA-1、截断值，或把 `sizeBytes` 当成了哈希。

**诊断**：

```bash
# 技能目录内：重新下载并输出真实哈希/大小
python3 scripts/asset_meta.py "<downloadUrl>"

# 直接核对（重复下载两次，哈希不同即说明 URL 可变）
curl -sL "<downloadUrl>" -o /tmp/opencode/xime-asset
sha256sum /tmp/opencode/xime-asset

# xime-index 克隆内：按索引记录逐项比对
python3 scripts/ci-update.py --verify
```

**修复**：

1. 只是索引值填错：用 `asset_meta.py` 的结果更新 `sha256`、`size`、`sizeBytes`。
2. 附件内容确实变了：**不要覆盖已发布的附件**。发新 tag、新 Release，上传新产物，
   在 `versions` 顶部新增版本并更新 `currentVersion`；旧版本记录保留。
3. 旧附件已被覆盖、无法恢复：旧版本已经不可校验，联系维护者说明；优先恢复原文件，
   恢复不了就发新版本并在 PR 里注明。不要靠清空 `sha256` 绕过。
4. URL 本身可变：换成 Release 附件；截图可以钉 tag/commit，但下载地址不行。

例外只有 `.gram`：`downloadUrl` 中的 `.gram` 允许 `sha256: ""`，上游会跳过校验；
模型的 `files[]` 不放这个口子，能算就算。详见 [model.md](model.md) 的「.gram 例外」。

## 链接 404

**症状**：浏览器/客户端下载 404；Validate Index 的 URL 探测打印 `FAIL ... 404`；
`validate_entry.py --check-urls` 报下载失败。

**可能原因**：

| 原因 | 确认方式 | 修复 |
|---|---|---|
| 仓库或 Release 是私有的 | 退出登录后打开链接 | 改为公开仓库 / 公开 Release，或镜像到公开地址 |
| owner / repo / tag / 文件名拼错 | 与 Release 页面地址逐字对照 | 复制 Release 附件真实地址 |
| 附件被删除或改名 | Release 页面找不到该文件 | 重新上传同内容附件；内容有变则发新版本 |
| tag 不存在或写成 `v1.0` / `1.0.0` 混用 | `git ls-remote --tags <repo>` | 统一 tag 名 |
| Release 还是 draft | 页面显示 Draft | 发布 Release |
| 文件名大小写不一致 | 对比附件名与 URL | 改为完全一致（Linux 区分大小写） |
| 用了已删除的分支归档 | URL 含 `refs/heads/` | 改用 tag 归档或 Release 附件 |
| ModelScope `resolve/master/...` 路径变动 | 打开链接确认 | 固定到具体 revision，或改用 Release 镜像 |

**诊断**：

```bash
curl -sIL "<downloadUrl>" | sed -n '1,15p'

# 技能目录内：探测条目里的全部 URL
python3 scripts/validate_entry.py /path/to/xime-index/src/layouts/<id>.yaml \
  --repo-root /path/to/xime-index --check-urls
```

**注意**：上游 Validate Index 只探测 `type: remote` 的条目。布局条目没有 `type` 字段，
会被跳过，所以布局下载地址必须自己用 `--check-urls` 或 `asset_meta.py` 验证。模型会
探测 `archive.url` 和带 `url` 的 `files[]`。

## id 与文件名不一致

**症状**：`ci-update.py` 输出 `id 不匹配，跳过`；条目在生成的子索引里消失；PR 里
看不到自己的条目。

**可能原因**：

- 文件名是 `my_layout.yaml`，内容却是 `id: my-layout`（连字符/下划线混用）；
- 复制模板后只改了文件名，没改 `id`，或反过来；
- 大小写不一致；
- 插件用了带点号的 `id`，文件名却少了点号；
- 输入方案的 `id` 与包内 `schema_id` 不一致。

**修复**：

```bash
# 对比文件名与 id
basename src/layouts/<file>.yaml
grep -n '^id:' src/layouts/<file>.yaml

# 需要改文件名时用 git mv，保留历史
git mv src/layouts/old_name.yaml src/layouts/new_name.yaml
```

然后同步所有相关位置：

| 类型 | 必须一致的位置 |
|---|---|
| 布局 | 文件名、`id` |
| 插件 | 文件名、`id`、manifest `id` |
| 输入方案 | 文件名、`id`、主 `.schema.yaml` 的 `schema_id` |
| 模型 | 文件名、`id` |

已经上架的 `id` 是用户安装和更新时的标识，不要随意重命名；确需更换时先问维护者，
通常做法是新增条目并保留旧条目。历史例外（如 `rime-ice` 的 `id` 与 `schema_id`
不同）只用于兼容旧数据，新条目必须一致。

## 截图被拒

**症状**：维护者在 PR 里要求更换截图；商店详情页展示了错误/模糊/无关的图片。

**常见原因与修复**：

| 原因 | 修复 |
|---|---|
| 截了设置页、其他输入法或非键盘界面 | 在曦码中应用该布局，打开真实键盘再截 |
| 用了 `@main` / `master` / 分支 raw 地址 | 固定到 tag 或 commit，首选 Release 附件 |
| `http://` 地址 | 改为 HTTPS |
| 数量为 0 或超过 5 张 | 保留 1~5 张 |
| 单张超过 500KB | 压缩，或裁掉无关区域 |
| 宽度小于 720px | 用原图重新导出，不要放大低清图 |
| 含状态栏、导航栏、个人信息 | 裁到键盘区域，建议 9:16 |
| 截图与当前版本主题不一致 | 按新版本重新截图，更新 `screenshots` |
| 格式不是 png/jpg/webp | 转成支持格式 |

```bash
# 检查尺寸和体积（ImageMagick，可选）
identify screenshot.png
ls -lh screenshot.png
```

截图 URL 不受“必须是 Release 附件”的限制，但必须不可变：Release 附件、固定 commit
的 raw、固定 tag 的 jsDelivr 都可以。规范细节见 [layout.md](layout.md) 的「截图规范」。

## 误改生成索引

**症状**：PR diff 里出现 `index.yaml`、`rimes/index.yaml`、`plugins/index.yaml`、
`plugins/v2/index.yaml`、`models/index.yaml` 或 `layouts/index.yaml`；维护者要求移除；
合并后 bot 提交覆盖你的改动或产生冲突。

**原因**：本地跑了 `ci-update.py` 后用 `git add -A`；直接编辑生成文件；解决冲突时把
生成结果一起提交了。

**修复**（尚未提交）：

```bash
# 用 upstream/main 的版本恢复所有生成文件
git checkout upstream/main -- \
  index.yaml \
  rimes/index.yaml \
  plugins/index.yaml \
  plugins/v2/index.yaml \
  models/index.yaml \
  layouts/index.yaml

git status --short
```

已经 commit 但还没推送：

```bash
git restore --source=upstream/main -- \
  index.yaml rimes/index.yaml plugins/index.yaml \
  plugins/v2/index.yaml models/index.yaml layouts/index.yaml
git add -u -- \
  index.yaml rimes/index.yaml plugins/index.yaml \
  plugins/v2/index.yaml models/index.yaml layouts/index.yaml
git commit -m "chore: drop generated index files"
```

已经推送：追加一个修复提交即可，不要强推改写历史（强推需要单独确认）。预防办法：

- 只 `git add src/<type>/<id>.yaml`，不要 `git add -A`；
- 本地生成后、commit 前恢复生成文件；
- 提交前检查：

  ```bash
  git diff --cached --name-only | grep -vE '^src/' && echo "非 src 文件！"
  ```

规则来源见 [index-rules.md](index-rules.md) 的「PR 只改 src」。

## v1/v2 混淆

**症状**：

- v3 App 里插件不显示，或提示不支持/无法加载；
- 旧 App 安装 v2 插件后无法运行；
- v2 索引报 `missing pluginType` 或 manifest 字段不一致；
- 同一个插件在两代商店里版本/描述对不上。

**原因**：把新插件放进了 `src/plugins/v1/`；把 Lua/DEX 的 `.xipk` 填进了 v2 条目；
v2 包缺少 `manifest.json` / `main.js`；或把 v1 的 `downloadUrl` 指向了 v2 附件。

| | 旧版 v1 | v2 |
|---|---|---|
| 源目录 | `src/plugins/v1/` | `src/plugins/v2/` |
| 生成索引 | `plugins/index.yaml` | `plugins/v2/index.yaml` |
| 兼容 App | `< 3.0.0` | `>= 3.0.0` |
| 包内容 | 旧版 Lua/DEX `.xipk` | `manifest.json` + `main.js` + `resources/` |
| 索引 `appVersion` | 如 `">=2.6.0"` | `">=3.0.0"` |

**修复**：

- 新插件一律按 [plugin-v2.md](plugin-v2.md) 上架；v1 只维护旧条目，见
  [plugin-v1.md](plugin-v1.md)。
- 需要同时支持两代 App 时，两个目录各放一个条目，可以共用 `id`，但各自指向对应格式
  的 Release 附件；不要互相覆盖。
- v2 条目用 manifest 交叉校验：

  ```bash
  python3 scripts/validate_entry.py src/plugins/v2/<id>.yaml \
    --repo-root /path/to/xime-index \
    --manifest ./manifest.json \
    --asset-file ./<id>-<version>.xipk
  ```

- v1 条目出现 `legacy plugin index` 警告是预期的，不代表失败。

## 版本未递增

**症状**：商店仍显示旧版本，更新提示不出现；`currentVersion` 指向的版本不在
`versions` 里；同一个版本号出现两次；用户装到的新包和商店显示不一致。

**原因**：

- 改了产物但没升 `manifest.json` 的 `version`（v2）；
- 忘了更新索引 `currentVersion`；
- `versions` 顶部新增了记录，但 `version` 与 `currentVersion` 不一致；
- 复制旧记录后没改版本号，产生重复；
- 复用了旧 tag，或在旧 Release 上替换了附件。

**修复**：一次发布只认一个版本号，下列位置必须全部一致：

| 位置 | 示例 |
|---|---|
| Release tag | `v1.0.1` |
| Release 附件名 | `my-layout-1.0.1.zip` |
| 插件 `manifest.json` `version` | `1.0.1` |
| `versions[0].version` | `1.0.1` |
| `currentVersion` | `1.0.1` |

步骤：

1. 发新 tag + 新 Release，上传新附件；
2. 在 `versions` **顶部**新增完整记录（`version`、`date`、`changelog`、下载信息）；
3. 更新 `currentVersion`；
4. 保留旧版本记录和旧附件；
5. 重新计算并填写 `sha256` / `size` / `sizeBytes`；
6. 跑 `validate_entry.py` 和 `ci-update.py --check`。

只改描述、标签、截图等元数据时不需要升版本；只要安装产物变化就必须升。`versions`
顺序应与版本新旧一致，最新在最上面。

## `ci-update.py --check` 失败

**症状**：在 `xime-index` 克隆内运行 `python3 scripts/ci-update.py --check` 退出 1，
输出缺少 `sha256` / `size`。

**原因**：`src/` 条目留空，指望合并后 CI 自动补。实际上 `ci-update.py` 只读 `src/`，
自动补全的值只写进生成的子索引；`update-checksums.yml` 还会断言 `src/` 未被修改。
所以 `src/` 缺值就是失败。

**修复**：

```bash
# 技能目录内：下载附件并得到 sha256 / size / sizeBytes
python3 scripts/asset_meta.py "<downloadUrl>"

# 填回 src/ 条目后重跑
cd /path/to/xime-index
python3 scripts/ci-update.py --check
```

- 所有普通下载项都要填 `sha256`、`size`，建议填 `sizeBytes`；
- `.gram` 在 `downloadUrl` 中可以留空 `sha256`，其它文件不行；
- 不要手改 `layouts/index.yaml` 等生成文件来“消除”报错；
- `--no-verify` 只用于本地快速生成，不能代替提交前检查。

## 模型 category 未知

**症状**：校验报 `category` 不在枚举内；商店分组错误；新模型照抄旧条目被拒。

**原因**：拼写错误；用了只存在于历史数据的 `handwriting`；把 `asr` 写成 `speech`
或 `voice`。

**修复**：使用文档枚举：

| 值 | 用途 |
|---|---|
| `prediction` | 智能联想 / 文本预测 |
| `asr` | 语音识别 |
| `punctuation` | 标点预测 |
| `stroke` | 笔画（预留） |
| `other` | 其他 |

`handwriting` 是历史例外（现有 `ochwpro`），新模型不要用；需要新手写分类时先与维护者
确认。字段与大小计算见 [model.md](model.md)。

## zip 结构被拒

**症状**：客户端提示布局包无效 / 安装后无效果；`validate_entry.py --asset-file` 报
顶层目录、路径逃逸、非法扩展名或符号链接。

**常见原因**：

- zip 里有顶层目录壳：`my_layout/xime.custom.yaml`；
- `xime.custom.yaml` 不在根级，或文件名拼错；
- 含 `..`、绝对路径、反斜杠、符号链接；
- 图片/字体放在 `themes/`、`fonts/` 之外，或扩展名不允许；
- 资源名含中文/空格，在设备文件系统上出问题。

**诊断**：

```bash
unzip -l my-layout-1.0.0.zip

python3 scripts/validate_entry.py src/layouts/<id>.yaml \
  --repo-root /path/to/xime-index \
  --asset-file ./my-layout-1.0.0.zip
```

**修复**：进入配置所在目录重新打包，确保根级就是 `xime.custom.yaml`：

```bash
cd my-layout
zip -r ../my-layout-1.0.0.zip xime.custom.yaml themes fonts
cd ..
unzip -l my-layout-1.0.0.zip
```

只保留根级配置、`themes/*`（png/jpg/jpeg/webp/gif）和 `fonts/*`（ttf/otf）；其余文件
客户端会忽略。详细结构见 [layout.md](layout.md) 的「zip 结构」。

## 插件 manifest 与索引不一致

**症状**：`validate_entry.py --manifest` 报字段不一致；CI 报 `missing pluginType`；
商店显示的插件名/版本/能力与安装后的实际插件不符。

**原因**：手动改了一边；发布前只更新了 manifest 或只更新了索引；`capabilities` /
`network` 没有原样复制；`pluginType` 与 manifest `type` 不同；`minHostVersion` 与
`appVersion` 矛盾。

**修复**：

- 以 `manifest.json` 为准，逐项同步索引：`id`、`pluginType`、`currentVersion`、
  `name`、`icon`、`description`、`platforms`、`minHostVersion`、`capabilities`、
  `network`；
- `appVersion` 与 `minHostVersion` 对齐，如 manifest `3.0.0` → 索引 `">=3.0.0"`；
- 跑 `xipm check .` 和带 `--manifest` 的交叉校验；
- 完整映射见 [plugin-v2.md](plugin-v2.md) 的「索引字段映射」。

## CI 没有触发

**症状**：PR 页面没有任何 check run，或只有部分检查。

**原因**：当前上游 `validate.yml` 的 `pull_request.paths` 不包含 `src/**`，只改
`src/` 的 PR 可能不触发 Validate Index。这是上游 workflow 的路径过滤缺口，不是条目
本身的问题。

**处理**：

- 不要为了触发 CI 去修改生成索引或添加无关文件；
- 在 PR 正文贴出本地 `validate_entry.py`、`ci-update.py --check` 的结果；
- 在 PR 里说明仅改 `src/`、当前路径过滤可能不触发检查；
- 是否调整 workflow 由维护者决定，贡献者不要顺手改 `.github/workflows/`。

合并后 bot 提交生成索引会触发 `Validate Index` 和部署，链接可达性仍会在那时被检查；
所以本地的 `--check-urls` / `asset_meta.py` 不能省。流程细节见
[pr-and-ci.md](pr-and-ci.md) 的「盯 CI」。
