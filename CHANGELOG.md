# Changelog

## 未发布

- 网络受阻时主动提示代理：`lib.py` 新增 `is_network_error` / `is_network_error_text`
  / `network_hint`，`asset_meta.py`、`preflight.py --check-rules`、
  `validate_entry.py --check-urls` 在 DNS/连接/超时/TLS 失败时打印代理提示（只列
  环境变量名，不打印值），并在技能文档中要求先询问用户是否使用代理。
- 修复 `validate_entry.py` 只认顶层 `schema_id` 的问题：标准 Rime 方案把 `schema_id`
  写在 `schema:` 段内，现在顶层与 `schema.schema_id` 两种写法都会识别。

## v0.1.0 - 2026-10-29

- 新增 `xime-index-submit` 技能，覆盖布局/配色、插件 v2、旧版插件 v1、输入方案、模型五类条目。
- 新增 `preflight.py`、`asset_meta.py`、`validate_entry.py` 校验脚本。
- 新增五类 YAML 模板、分类型参考文档、PR/CI 排错手册。
- 半自动流程：本地校验/提交，push 与开 PR 前必须确认。
- 规则漂移检测：`references/upstream.lock.json` + `preflight.py --check-rules`。
- 新增 GitHub Actions 验证工作流，覆盖 Python 3.10 / 3.12。
- 新增基线、GREEN、REFACTOR 压力测试记录与真实仓库端到端 dry run 文档。
- 测试覆盖 frontmatter、相对链接、五类模板、校验脚本和压力场景红线回归。
