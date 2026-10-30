# 模型上架

模型产物托管在作者自己的仓库 / 模型站，`xime-index` 只保存引用。源文件放在
`src/models/<id>.yaml`，生成 `models/index.yaml`（键 `models`）。
通用索引规则见 [index-rules.md](index-rules.md)。

> **不要照抄现有条目。** 早期模型（如 `predictive-text-base`）存在 `sha256: ""`、
> `sizeBytes` 为空、以及 ModelScope `resolve/master` 分支地址。这些是历史数据，
> 新条目必须按本文件填满校验值并使用不可变地址。

## 两种模型

| | 文件列表型 | 归档型 |
|---|---|---|
| 分发方式 | 每个文件一个 URL，独立下载 | 一个 `tar.bz2` 整包下载 |
| 索引字段 | `versions[].files[]` 带 `url` | `versions[].archive` + `files[].name` 清单 |
| 适用 | 文件少、需要单独更新某个文件 | 文件多、目录结构固定、ASR 模型等 |
| `storageDir` | 文件落到该目录 | 归档解压到该目录 |

两种可以组合：归档型用 `files[]` 列出归档内文件（只写 `name`，用于校验）；
如果还有独立下载的文件，再给对应项补 `url` / `sha256` / `size`。

条目必填字段：`id`、`name`、`author`、`description`、`category`、`size`、`type`、
`currentVersion`、`versions`；推荐填 `tags`、`homepage`、`license`、`appVersion`。
`type` 固定 `remote`。

文件列表型示例：

```yaml
id: demo_model
name: Demo Model
author: you
description: 逐文件分发的 ONNX 模型
category: prediction
size: 1.00 MB
type: remote
tags: [联想, ONNX]
homepage: https://github.com/you/demo-model
license: MIT
appVersion: ">=3.0.0"
currentVersion: "v1.0"
versions:
  - version: "v1.0"
    date: "2026-10-30"
    changelog: 初始发布
    storageDir: ""
    files:
      - name: model.onnx
        url: https://github.com/you/demo-model/releases/download/v1.0.0/model.onnx
        sha256: "<64 位十六进制>"
        size: 600.0 KB
        sizeBytes: 614400
      - name: tokens.txt
        url: https://github.com/you/demo-model/releases/download/v1.0.0/tokens.txt
        sha256: "<64 位十六进制>"
        size: 424.0 KB
        sizeBytes: 434176
```

归档型示例：

```yaml
id: demo_asr
name: Demo ASR
author: you
description: 整包分发的语音识别模型
category: asr
size: 133.90MB
type: remote
tags: [语音, ASR]
homepage: https://github.com/you/demo-asr
license: Apache-2.0
appVersion: ">=3.0.0"
currentVersion: "v1.0"
versions:
  - version: "v1.0"
    date: "2026-10-30"
    changelog: 初始发布
    storageDir: asr_models/demo_asr
    archive:
      url: https://github.com/you/demo-asr/releases/download/v1.0.0/demo-asr.tar.bz2
      sha256: "<64 位十六进制>"
      size: 133.90MB
      sizeBytes: 133895136
    files:
      - name: encoder.onnx
      - name: decoder.onnx
      - name: tokens.txt
```

## category

| 值 | 用途 |
|---|---|
| `prediction` | 智能联想 / 文本预测 |
| `asr` | 语音识别（含流式、标点等组合模型） |
| `punctuation` | 标点预测 |
| `stroke` | 笔画序列（预留） |
| `other` | 其他 |

`handwriting` 是历史例外：现有手写模型 `ochwpro` 使用它，但官方文档的枚举里没有。
技能会放行并提示兼容性警告；**新模型不要用 `handwriting`**，先与索引维护者确认，
或暂用 `other`。

`category` 决定商店分组，不能拼错；技能会拒绝枚举外的值。

## files 与 archive

版本级字段：

| 字段 | 必填 | 说明 |
|---|---|---|
| `version` | ✅ | 版本号，与 `currentVersion` 一致 |
| `date` | ✅ | `YYYY-MM-DD` |
| `changelog` | ✅ | 更新说明 |
| `storageDir` | 建议 | 相对模型根目录的子目录；`""` 表示根目录 |
| `archive` | 二选一 | 整包下载信息 |
| `files` | 二选一 | 文件列表；至少要有 `archive` 或 `files` |

`storageDir` 要求：

- 只用相对路径，例如 `asr_models/zipformer-zh-int8`；
- `""` 表示模型根目录；
- 不能以 `/` 开头，不能含 `..`，不要写设备绝对路径。

`archive` 字段：

| 字段 | 必填 | 说明 |
|---|---|---|
| `url` | ✅ | HTTPS，建议 Release 附件 |
| `sha256` | ✅ | 64 位十六进制 |
| `size` | ✅ | 人类可读大小 |
| `sizeBytes` | 建议 | 精确字节数 |

归档格式使用 **`tar.bz2`**（文档约定）；不要用 zip 代替，除非确认客户端支持。
归档里的文件应与 `files[].name` 对得上，否则安装校验可能失败。

`files[]` 字段：

| 字段 | 必填 | 说明 |
|---|---|---|
| `name` | ✅ | 文件名或相对路径，不能含 `..`；同一版本不要重名 |
| `url` | 条件 | 独立下载时必填；仅归档内清单时省略 |
| `sha256` | 条件 | 有 `url` 时必填（`.gram` 例外） |
| `size` | 条件 | 有 `url` 时必填 |
| `sizeBytes` | 建议 | 独立下载项的精确字节数 |

判断规则：

- `files[]` 有 `url`：这是独立下载项，必须提供 `sha256` / `size`；
- `files[]` 没有 `url`：只是归档内文件清单，只用于校验归档内容，不需要校验值；
- 归档内文件不要补 `sizeBytes`，否则会被总大小重算逻辑当成独立文件汇总；
- `archive` 和带 `url` 的 `files[]` 可以同时存在，客户端会都下载。

下载地址优先用 GitHub Release 附件。ModelScope 的
`.../resolve/master/...` 是分支地址，内容会变；如必须用 ModelScope，请固定到具体
commit/revision，或改用 Release 镜像。

## 大小计算

- 条目级 `size` 是商店展示与排序用的总大小，人类可读字符串，如 `7.00 MB`、
  `133.90MB`。
- `sizeBytes` 是精确字节数，必须是正整数。
- 生成索引时 `ci-update.py` 会调用 `recalc_model_size`：

  - 只有当**所有版本的所有 `files[]`** 都有 `sizeBytes` 时才重算；
  - 重算值是这些 `sizeBytes` 的**总和**（包含历史版本的文件）；
  - 结果写进生成的 `models/index.yaml`，**不写回 `src/`**；
  - `archive.sizeBytes` 不参与这个汇总。

因此：

- 文件列表型：给每个文件填准确的 `sizeBytes`，让脚本汇总；条目 `size` 可以按合计值
  预填，生成时会再校准。
- 归档型：`files[]` 通常只有 `name`，不会触发重算；`size` 请手动填成归档包大小
  （与 `archive.size` 一致）。
- 多版本条目：脚本会把所有版本的 `files[].sizeBytes` 相加，`size` 可能大于单个安装包。
  这是当前脚本行为；保持每个版本的 `sizeBytes` 准确，并以生成结果为准。
- `size` 与 `sizeBytes` 合计不一致时，技能给警告但不阻止；`sizeBytes` 与真实下载
  字节数不一致时，上游只打印 `size_warn`，不会剔除版本。

计算文件元数据：

```bash
python3 scripts/asset_meta.py \
  https://github.com/you/demo-model/releases/download/v1.0.0/model.onnx
```

## .gram 例外

`.gram` 是 KenLM 语法模型文件，体积通常很大。上游对 `.gram` 有兼容例外：

- 在 `downloadUrl` 中，`.gram` 允许 `sha256: ""`；`ci-update.py --check` 和填充函数
  会跳过它的 sha256 校验。
- `size` 仍然必填，`sizeBytes` 建议填。
- 在模型的 `files[]` 中，技能也允许 `.gram` 留空 `sha256`；但上游 `--check` 对
  `files[]` 不会开同样的口子，仍可能要求补全。**能算就算**，不要依赖例外。

示例：

```yaml
files:
  - name: wanxiang-lts-zh-hans.gram
    url: https://github.com/you/model/releases/download/v1.0.0/model.gram
    sha256: ""
    size: 380 MB
    sizeBytes: 398458880
```

除 `.gram` 外，其它文件（`.onnx`、`.json`、`.txt`、`.bin` 等）都必须有 `sha256`。

## 常见错误

| 现象 | 原因 | 修复 |
|---|---|---|
| 技能报“必须提供 archive 或 files” | 版本下没有任何下载内容 | 补 `archive` 或 `files[]` |
| `category` 被拒 | 拼写错误，或新模型用了 `handwriting` | 改用 `prediction` / `asr` / `punctuation` / `stroke` / `other` |
| 安装后文件缺失 / 校验失败 | `files[].name` 与归档内实际文件名不一致 | 按归档内容逐项列出，注意大小写和子目录 |
| 文件下载 404 | URL 指向未上传的 Release 附件或缺 sha 的历史地址 | 上传附件，改用不可变地址并重算 sha256 |
| `sha256` 为空被拒 | 新条目照抄了旧模型的空值 | 用 `asset_meta.py` 计算并填满；`.gram` 才可例外 |
| 商店大小与包大小不符 | 多版本 `files[].sizeBytes` 被汇总，或 `size` 手填错 | 核对生成后的 `models/index.yaml`，以 `recalc_model_size` 结果为准 |
| 归档解压到错误目录 | `storageDir` 写了绝对路径或 `..` | 改成相对子目录，`""` 表示根目录 |
| 部署/加载失败 | 归档不是 `tar.bz2`，或缺少 `files[]` 声明的文件 | 用 `tar.bz2` 重新打包，补齐清单 |
| `.gram` 仍被 `--check` 报错 | 上游只对 `downloadUrl` 跳过，`files[]` 不跳过 | 尽量计算 sha256；不能算时与维护者确认 |
| 版本更新后旧版本消失 | 删除或覆盖了旧 Release 附件 | 新 tag + 新附件，保留历史版本 |
| 索引显示旧版本 | 只改了 manifest/包，没改 `currentVersion` | 把 `currentVersion` 和 `versions` 顶部记录同步到新版本 |

本地校验：

```bash
python3 scripts/validate_entry.py src/models/<id>.yaml \
  --repo-root /path/to/xime-index \
  --check-urls
```

`--check-urls` 会探测所有 `archive.url` 与带 `url` 的 `files[]`，发布前建议跑一次。
