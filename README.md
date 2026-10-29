# Xime Skills

面向 Xime 扩展生态的 Agent Skills。当前包含一个技能：**`xime-index-submit`**，把“自制布局/配色、插件、输入方案、模型 → 作者仓库 Release → `xime-index` 条目 → PR → CI”的流程固化下来。

## 安装

```bash
npx skills add tiengming/xime-skills --skill xime-index-submit -g
```

`-g` 表示安装到用户级目录（`~/.agents/skills/`），所有项目可用。去掉 `-g` 则安装到当前项目。

手动安装：

```bash
git clone https://github.com/tiengming/xime-skills.git
cp -r xime-skills/skills/xime-index-submit ~/.agents/skills/
```

## 支持的条目

| 类型 | `xime-index` 源文件 | 作者侧产物 |
|---|---|---|
| 布局 / 配色 | `src/layouts/<id>.yaml` | `xime.custom.yaml` 或根级 zip |
| 插件 v2 | `src/plugins/v2/<id>.yaml` | `.xipk`（manifest + main.js + resources） |
| 旧版插件 v1 | `src/plugins/v1/<id>.yaml` | `.xipk`（Lua/DEX，仅维护旧版） |
| 输入方案 | `src/rimes/<id>.yaml` | zip/tar.gz（schema + dict） |
| 模型 | `src/models/<id>.yaml` | 文件列表或 tar.bz2 归档 |

## 前置条件

- Python 3.10+ 与 PyYAML（`python3 -m pip install PyYAML`）。
- Git。
- 可选：GitHub CLI `gh`（用于自动开 PR）；`uv`（用于跑 `xime-index` 的脚本）。没有它们也能用，技能会输出手动步骤。
- 网络能访问 GitHub。若直连失败，可设置代理：

```bash
export HTTPS_PROXY=http://127.0.0.1:10809   # 示例，按你的代理修改
```

## 安全边界

- 技能会自动校验、生成条目、本地提交。
- **`git push` 和开 PR 前必须经你明确确认**；不会自动合并。
- 不会把生成的子索引提交进 PR；PR 只改 `src/`。
- 不会执行下载的资产，只计算哈希并检查 zip 结构。

## 无 `gh` 时

技能会打印 GitHub compare URL，例如：

```text
https://github.com/ximeiorg/xime-index/compare/main...<你的用户名>:<分支>?expand=1
```

你在浏览器中确认并创建 PR。

## License

CC BY-NC-SA 4.0，与 `xime-index` 保持一致。
