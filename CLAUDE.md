# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TV 自动化测试录制回放工具后端 — Python/Flask 服务，用于录制和回放 TV 设备上的 UI 自动化测试用例。仅支持 TV 设备（通过采集卡 + ADB），不涉及手机端。

## Running the Application

```bash
python main_app.py          # Flask 服务 http://localhost:5004
cd frontend && npm run dev   # 前端开发服务器
```

Key dependencies: `flask`, `opencv-python`, `pillow`, `requests`.

## Architecture

### Directory Structure

```
backend/
  main_app.py                    # 入口：自动更新 + Flask 启动
  app_config.json                # 应用配置（data_dir, scripts_repo_path）
  common/
    utils.py                     # ADB 路径检测、文件名清理
    adb_utils.py                 # ADB 命令执行、设备检查、Activity 获取
    config_manager.py            # 配置管理（app_config、jira_config、device_config）
  tv_annotation/
    app.py                       # TV 路由注册（注册所有蓝图到 Flask）
    capture_card.py              # 视频采集卡管理器（单例，线程安全）
    key_mappings.py              # 遥控器按键码映射
    recorder.py                  # 录制引擎（getevent + Activity + 分组）
    replay_engine.py             # 回放引擎（Activity 校验 + 恢复策略）
    ai_client.py                 # 大模型客户端（图片上传 + 对话）
    jira_client.py               # Jira API 客户端
    video_recorder.py            # 回放视频录制
    confluence_client.py         # Confluence 同步
    routes/
      config_routes.py           # 设备配置 API
      recording_routes.py        # 录制 API
      replay_routes.py           # 回放 API
      case_routes.py             # 用例管理 API（Jira + 自定义）
      plan_routes.py             # 测试计划 API
      stats_routes.py            # 统计 API
      git_routes.py              # Git 协作 API
      stream_routes.py           # 视频流 API
```

### Data Storage

所有数据本地存储，无数据库：

```
../data/                         # 运行时数据（回放结果、配置）
  jira_config.json               # Jira 连接配置（不入 Git）
  device_config.json             # 设备配置
  replay/                        # 回放数据（截图、视频、结果）
../tv-test-scripts/              # 录制脚本 Git 仓库（团队共享）
  index.json                     # 用例索引
  PROJ-101/case.json + steps.json
  plans/PLAN-001.json            # 测试计划
```

路径通过 `app_config.json` 配置，默认取 backend 上级目录。

### Route Registration

`main_app.py` 调用 `register_tv_routes(app, data_dir, scripts_repo_path)` 注册所有蓝图。每个蓝图由工厂函数 `create_*_routes(...)` 创建。URL 前缀: `/api/tv/...`。

### API Response Convention

```json
{"success": true/false, "message": "...", "data": {...}, "error": "..."}
```

### Key Patterns

- **Singleton**: `CaptureCardManager` 视频采集卡单例
- **Background threads**: 录制/回放在独立线程中运行
- **Graceful degradation**: 路由模块注册失败不影响其他模块
- **Auto-update**: 启动时自动 git pull 代码和脚本，代码有更新时 os.execv 重启
- **Logging**: 双输出（控制台 + log/app.log），启动时清空

## Requirements Reference

完整需求文档见 `docs/requirements.md`，包含录制、回放、Jira 集成、AI 能力、测试计划、统计等详细规格。

## Codebase Language

Comments and UI strings are in Chinese.

## Git 工作流

- 修改代码后自动提交并 push 到远程仓库，无需等用户确认
- commit message 使用中文，格式：简述用户问题 + 修改内容
- 前端代码在 `backend/frontend/` 目录下，与后端同属一个 Git 仓库（feature 分支）
- 如果同时修改了外部 `../frontend/` 的文件，需同步复制到 `backend/frontend/` 再提交
