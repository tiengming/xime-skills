# Changelog

## v0.1.0 - 2026-10-29

- 新增 `xime-index-submit` 技能，覆盖布局/配色、插件 v2、旧版插件 v1、输入方案、模型五类条目。
- 新增 `preflight.py`、`asset_meta.py`、`validate_entry.py` 校验脚本。
- 新增五类 YAML 模板、分类型参考文档、PR/CI 排错手册。
- 半自动流程：本地校验/提交，push 与开 PR 前必须确认。
- 规则漂移检测：`references/upstream.lock.json` + `preflight.py --check-rules`。
