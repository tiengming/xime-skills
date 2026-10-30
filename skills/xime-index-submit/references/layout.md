# 布局 / 配色上架

布局条目只保存**引用**：`xime.custom.yaml`、主题图片、字体和截图都托管在作者自己的仓库，
索引通过不可变 URL + `sha256` 指向它们。规则来源见
[LAYOUT_SPEC.md](https://github.com/ximeiorg/xime-index/blob/06fd79c1b8754ded71d2e35c54c79efee4704ecc/LAYOUT_SPEC.md)。

## 交付形态

二选一，**两种都必须把交付物上传为 GitHub Release 附件**，再在索引里引用附件地址。

### A. 单文件：纯文本布局

没有图片、字体等资源时，直接把 `xime.custom.yaml` 上传为 Release 附件：

```text
https://github.com/<owner>/<repo>/releases/download/<tag>/xime.custom.yaml
```

示例：

```yaml
downloadUrl:
  - url: https://github.com/you/my-layout/releases/download/v1.0.0/xime.custom.yaml
    sha256: "<64 位十六进制>"
    size: "3.5 KB"
    sizeBytes: 3584
```

### B. zip 包：带主题图片 / 字体

配置与资源一起打包，**整个 zip** 作为 Release 附件上传：

```text
https://github.com/<owner>/<repo>/releases/download/<tag>/<layout>-<version>.zip
```

示例：

```yaml
downloadUrl:
  - url: https://github.com/you/my-layout/releases/download/v1.0.0/my-layout-1.0.0.zip
    sha256: "<64 位十六进制>"
    size: "12.0 KB"
    sizeBytes: 12288
```

注意：

- 附件名建议 `<layout>-<version>.zip`，与索引里的版本对应。
- 不要散传 zip 内部的 `xime.custom.yaml`、图片、字体；客户端只下载这个 zip。
- 不要把 raw、jsDelivr、分支地址作为 `downloadUrl`——内容会变，`sha256` 会失效。
- 每个版本用新的 tag + 新 Release；旧版本附件保留，供回滚。

## zip 结构

解压后**根目录**必须直接包含 `xime.custom.yaml`：

```text
my-layout-1.0.0.zip
├── xime.custom.yaml              # 必填，必须在根级
├── themes/                       # 可选，客户端部署到 rime/themes/
│   ├── bg.jpg
│   └── bg_night.jpg
├── fonts/                        # 可选，客户端部署到 rime/fonts/
│   └── MapleMono.ttf
├── README.md                     # 可选，客户端忽略
└── preview.png                   # 可选，客户端忽略
```

允许与禁止：

| 路径 | 规则 |
|---|---|
| `xime.custom.yaml` | 必须在根级；不能是 `my_layout/xime.custom.yaml` |
| `themes/*` | 只允许一层，扩展名 `png/jpg/jpeg/webp/gif` |
| `fonts/*` | 只允许一层，扩展名 `ttf/otf` |
| 根级 README / LICENSE / 图片 | 允许携带，但不会被安装 |
| 其他目录 | 技能会警告；客户端不会安装 |
| `..`、绝对路径、反斜杠 | 拒绝 |
| 符号链接 | 拒绝 |

资源文件名用 `[a-z0-9_-]`，避免中文和空格；否则在设备文件系统上容易出问题。

打包时先进入配置所在目录，确保没有目录壳：

```bash
cd my-layout
zip -r ../my-layout-1.0.0.zip xime.custom.yaml themes fonts
cd ..
unzip -l my-layout-1.0.0.zip     # 确认 xime.custom.yaml 在根级
```

本地检查 zip：

```bash
python3 scripts/validate_entry.py src/layouts/<id>.yaml \
  --repo-root /path/to/xime-index \
  --asset-file ./my-layout-1.0.0.zip
```

## xime.custom.yaml 约定

`xime.custom.yaml` 是普通的顶层 YAML（由应用合并覆盖），不要套 Rime 的 `patch:` 外壳。

**资源只用相对路径**，客户端会解析到 `rime/themes/` 与 `rime/fonts/`：

```yaml
# 图片背景主题
color_schemes:
  my_theme:
    name: "我的主题"
    keyboard_background:
      type: image
      src: "themes/bg.jpg"          # 相对 rime/ 目录
      src_dark: "themes/bg_night.jpg"
      fit: cover
      overlay_alpha: 0.25
```

```yaml
# 字体
keyboard:
  fonts:
    key_font: "fonts/MapleMono.ttf"
    candidate_font: "fonts/LXGWWenKai.ttf"
```

普通布局条目**不要包含**这些与布局无关的样板：

| 不要写 | 原因 |
|---|---|
| `xime_index` / `xime_index.base_urls` | 会覆盖用户自己的索引地址 |
| `style.color_scheme` | 会覆盖用户当前选择的主题 |
| `color_schemes`（普通布局） | 会顶掉用户已有配色 |

**配色 / 主题包的例外**：如果交付物本身就是一套或多套配色，`color_schemes` 和
`style.color_scheme` 就是产品内容，应当包含。此时条目 `tags` 必须含 `配色`
（例如 `tags: [配色]`），技能才不会把它当成普通布局告警。主题包同样通过
`xime.custom.yaml` 或 zip 交付，并遵守上面的 Release / zip 规则。

其他约定：

- 同一时刻只有一套布局生效；应用新布局会覆盖上一套，不保留备份。
- 「恢复默认」会删除 `xime.custom.yaml` 及本布局引入的 `themes/`、`fonts/` 文件。
- 不要在配置里写设备绝对路径；换机后必然失效。

## 截图规范

截图用于商店详情页，必须是**曦码输入法设置界面中打开/预览的键盘样式**，即应用该布局后的
真实键盘效果。

| 项目 | 要求 |
|---|---|
| 数量 | 1~5 张 |
| 内容 | 曦码键盘实际效果；不接受其他输入法、设置页或非键盘界面 |
| 构图 | 竖屏键盘区，裁掉状态栏 / 导航栏；建议 9:16 |
| 尺寸 | 宽 ≥ 720px |
| 格式 | `png` / `jpg` / `webp` |
| 单张大小 | ≤ 500KB |
| URL | HTTPS，固定到 tag 或 commit；不能是分支 |

好 / 坏 URL 对照：

| 结果 | URL | 说明 |
|---|---|---|
| ✅ 推荐 | `https://github.com/you/repo/releases/download/v1.0.0/01.png` | Release 附件，最稳 |
| ✅ 可用 | `https://raw.githubusercontent.com/you/repo/3b2e27b8be98e47af48d4ae79e7f4e5d25ae5f21/images/0.jpg` | 固定到 commit |
| ✅ 可用 | `https://cdn.jsdelivr.net/gh/you/repo@v1.0.0/images/0.jpg` | 固定到 tag；技能提示可改用 Release |
| ❌ 禁止 | `https://cdn.jsdelivr.net/gh/you/repo@main/images/0.jpg` | 分支会移动 |
| ❌ 禁止 | `https://raw.githubusercontent.com/you/repo/master/0.jpg` | 分支会移动 |
| ❌ 禁止 | `http://...` | 必须是 HTTPS |
| ❌ 禁止 | 其他输入法或非键盘截图 | 不符合商店展示要求 |

截图通常不放进 Release 附件；固定到 tag/commit 的 raw 或 jsDelivr 即可。下载地址
（`downloadUrl`）则相反，**只能**用 Release 附件。

## 更新版本

发布 `1.0.1` 时，新建 tag 和 Release，上传新的 zip 或 yaml；旧版本记录和旧附件都保留：

```yaml
currentVersion: "1.0.1"
versions:
  - version: "1.0.1"                   # 新版本放最上面
    date: "2026-10-30"
    changelog: 修复候选栏间距
    downloadUrl:
      - url: https://github.com/you/my-layout/releases/download/v1.0.1/my-layout-1.0.1.zip
        sha256: "<新 zip 的 sha256>"
        size: "12.4 KB"
        sizeBytes: 12698
  - version: "1.0.0"                   # 历史版本保留
    date: "2026-10-01"
    changelog: 初始发布
    downloadUrl:
      - url: https://github.com/you/my-layout/releases/download/v1.0.0/my-layout-1.0.0.zip
        sha256: "<旧 zip 的 sha256>"
        size: "12.0 KB"
        sizeBytes: 12288
```

步骤：

1. 修改 `xime.custom.yaml` / 资源，提交并打新 tag（如 `v1.0.1`）。
2. 创建新 Release，上传新的交付物。
3. 计算新附件的校验值：
   `python3 scripts/asset_meta.py https://github.com/you/my-layout/releases/download/v1.0.1/my-layout-1.0.1.zip`
4. 在 `src/layouts/<id>.yaml` 顶部新增版本，更新 `currentVersion`。
5. 跑 `validate_entry.py` 和 `ci-update.py --check`，再开 PR。

不要复用旧 tag 替换附件内容，也不要删除旧 Release；已经上架的版本必须保持不可变。

## 常见错误

| 现象 | 原因 | 修复 |
|---|---|---|
| 客户端提示找不到配置 / 安装后无效果 | zip 里有顶层目录壳：`my_layout/xime.custom.yaml` | 进入目录后重新打包，确保 `xime.custom.yaml` 在根级 |
| `sha256` 校验失败，版本被剔除 | 下载地址指向分支 / raw，内容已变；或替换了同 tag 的附件 | 改用 Release 附件；发新 tag、新版本，重新计算 sha256 |
| PR 的 `--check` 失败 | `sha256` 或 `size` 留空 | 在 `src/` 条目里填满；不要依赖合并后自动补 |
| 截图被维护者退回 | 截了设置页、其他输入法，或用了 `@main` | 换成应用布局后的真实键盘截图，固定到 tag/commit |
| 应用布局后用户主题被改 | 普通布局里写了 `style.color_scheme` / `color_schemes` | 删除这些段；配色包则打 `配色` 标签并作为主题包提交 |
| zip 被拒 | 含 `..`、绝对路径、反斜杠或符号链接 | 重新打包，只保留根级配置和 `themes/`、`fonts/` |
| 字体 / 背景不生效 | 资源放错目录或用了绝对路径 | 图片放 `themes/`、字体放 `fonts/`，配置写相对路径 |
| 图片 / 字体没被安装 | 放在 `assets/`、`images/` 等其它目录 | 移到 `themes/` 或 `fonts/`，重新打包 |
| 索引里出现重复版本 | 复制旧记录时没改 `version` | 删除重复项，`currentVersion` 指向唯一版本 |
| CI 链接检查失败 | 历史版本附件被删除，或仓库转私有 | 恢复附件；保持所有历史版本可访问 |
| PR 夹带生成文件 | 本地跑了 `ci-update.py` 并提交了 `layouts/index.yaml` | 只提交 `src/`，生成文件交给 CI |

提交前自查：

```bash
python3 scripts/validate_entry.py src/layouts/<id>.yaml \
  --repo-root /path/to/xime-index \
  --asset-file ./my-layout-<version>.zip
python3 scripts/asset_meta.py <downloadUrl>
```
