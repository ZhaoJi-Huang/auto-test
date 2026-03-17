# 函数调用链知识图谱

> 维护目的：修改/开发功能时，通过此图谱快速定位影响范围，保证修改到位、不遗漏。
>
> 最后更新：2026-03-17

---

## 目录

- [1. 模块总览](#1-模块总览)
- [2. 功能模块详解](#2-功能模块详解)
- [3. 核心调用链](#3-核心调用链)
- [4. 跨模块依赖关系](#4-跨模块依赖关系)
- [5. 共享状态与单例](#5-共享状态与单例)
- [6. API 端点清单](#6-api-端点清单)
- [7. 修改影响分析指南](#7-修改影响分析指南)

---

## 1. 模块总览

```
backend/
├── main_app.py                          # 入口：自动更新 + Flask 启动
├── common/                              # 公共工具层
│   ├── utils.py                         #   ADB 路径检测、文件名清理
│   ├── adb_utils.py                     #   ADB 命令执行（依赖 utils.ADB_PATH）
│   ├── config_manager.py                #   配置文件读写
│   └── audit_log.py                     #   业务审计日志
├── tv_annotation/                       # 业务核心层
│   ├── app.py                           #   路由注册中心
│   ├── capture_card.py                  #   采集卡管理器（单例）
│   ├── key_mappings.py                  #   按键码映射表
│   ├── recorder.py                      #   录制引擎
│   ├── replay_engine.py                 #   回放引擎
│   ├── ai_client.py                     #   AI 大模型客户端
│   ├── jira_client.py                   #   Jira API 客户端
│   ├── video_recorder.py               #   视频录制
│   ├── confluence_client.py             #   Confluence 同步
│   └── routes/                          # API 路由层
│       ├── config_routes.py             #   设备配置 API
│       ├── recording_routes.py          #   录制 API
│       ├── replay_routes.py             #   回放 API
│       ├── case_routes.py               #   用例管理 API
│       ├── plan_routes.py               #   测试计划 API
│       ├── stats_routes.py              #   统计 API
│       ├── git_routes.py                #   Git 协作 API
│       └── stream_routes.py             #   视频流 API
```

### 层次依赖关系

```
Routes (API 层)
  ↓ 调用
Engines (录制/回放/AI 引擎层)
  ↓ 调用
Services (采集卡/视频/Jira/Confluence 服务层)
  ↓ 调用
Common (ADB 工具/配置管理/审计日志)
```

---

## 2. 功能模块详解

### 2.1 公共工具层 (common/)

#### common/utils.py
| 函数/变量 | 说明 | 被谁调用 |
|-----------|------|----------|
| `ADB_PATH` | 全局 ADB 路径（模块加载时检测） | adb_utils, recorder, replay_engine, capture_card |
| `get_adb_path()` | 检测 ADB 可执行文件路径 | 模块初始化 |
| `sanitize_filename(name)` | 清理文件名中的非法字符 | case_routes |

#### common/adb_utils.py
| 函数 | 说明 | 被谁调用 |
|------|------|----------|
| `run_adb(cmd_list, device_serial, timeout)` | 执行 ADB 命令 | recorder, replay_engine, config_routes, recording_routes, ai_client |
| `check_adb_device(device_serial)` | 检查设备连接 | recorder, replay_engine, config_routes, plan_routes |
| `get_current_activity(device_serial)` | 获取当前 Activity | recorder, replay_engine |
| `send_keyevent(device_serial, keycode)` | 发送按键事件 | replay_engine, ai_client, recording_routes, plan_routes |
| `list_adb_devices()` | 列出所有已连接设备 | ensure_device_serial, config_routes |
| `ensure_device_serial(device_config, data_dir)` | 确保获取有效设备序列号（未配置时自动检测） | config_routes, recording_routes, replay_routes, plan_routes, main_app |
| `connect_device(device_serial)` | 网络连接设备 | config_routes |

#### common/config_manager.py
| 函数 | 说明 | 被谁调用 |
|------|------|----------|
| `load_app_config()` | 加载 app_config.json | main_app |
| `load_device_config(data_dir)` | 加载设备配置 | app.py, main_app |
| `save_device_config(data_dir, config)` | 保存设备配置 | config_routes, ensure_device_serial |
| `load_jira_config(data_dir)` | 加载 Jira 配置 | jira_client, case_routes |
| `save_jira_config(data_dir, config)` | 保存 Jira 配置 | case_routes |

#### common/audit_log.py
| 函数 | 说明 | 被谁调用 |
|------|------|----------|
| `init_audit_log(data_dir)` | 初始化审计日志 | main_app |
| `audit_log(action, case_key, detail)` | 记录业务操作 | recording_routes, replay_routes, case_routes, plan_routes |

---

### 2.2 采集卡模块 (capture_card.py)

**类**: `CaptureCardManager`（单例）

| 方法 | 说明 | 被谁调用 |
|------|------|----------|
| `start(device_id, width, height)` | 启动采集 | config_routes, stream_routes |
| `stop()` | 停止采集 | config_routes, main_app(atexit) |
| `get_frame()` | 获取当前帧(numpy) | video_recorder |
| `get_frame_as_jpeg(quality)` | 获取 JPEG 帧 | stream_routes |
| `get_frame_as_png()` | 获取 PNG 帧 | （备用） |
| `save_frame(filepath)` | 保存帧到文件 | （备用） |
| `take_screenshot(filepath, device_serial)` | 截图（采集卡优先，ADB 兜底） | replay_engine, ai_client(via capture_func) |
| `_open_device()` | 打开采集设备 | start() |
| `_capture_loop()` | 后台帧捕获循环 | start() 启动的线程 |

**独立函数**:
| 函数 | 说明 | 被谁调用 |
|------|------|----------|
| `enumerate_capture_devices(max_index)` | 枚举可用采集设备 | config_routes |

**全局变量**: `capture_card` — 单例实例，被 config_routes, replay_routes, stream_routes, replay_engine 引用

---

### 2.3 按键映射模块 (key_mappings.py)

| 函数/变量 | 说明 | 被谁调用 |
|-----------|------|----------|
| `KEY_CODE_MAP` | Linux 事件码 → 按键名 | recorder._parse_event_line |
| `ADB_KEYCODE_MAP` | 按键名 → ADB keycode | replay_engine |
| `KEY_NAME_TO_LINUX_CODE` | 按键名 → Linux 事件码 | replay_engine._send_long_press |
| `get_key_name(key_code)` | Linux 码 → 按键名 | recorder |
| `get_adb_keycode(key_name)` | 按键名 → ADB keycode | recorder, recording_routes |
| `get_linux_keycode(key_name)` | 按键名 → Linux 码 | replay_engine |

---

### 2.4 录制引擎 (recorder.py)

**类**: `TVRecorder`

| 方法 | 说明 | 调用了谁 |
|------|------|----------|
| `start(case_key)` | 开始录制 | → check_adb_device, get_current_activity, _find_key_event_device, _start_getevent_listener |
| `stop()` | 停止录制 | → get_current_activity, _flush_raw_keys_with_activity, _save_steps |
| `insert_adb_command(cmd, desc)` | 插入 ADB 命令步骤 | → get_current_activity, run_adb, _flush_raw_keys_with_activity |
| `insert_ai_instruction(type, prompt)` | 插入 AI 步骤 | → _flush_raw_keys_with_activity |
| `insert_step_at(index, step)` | 在指定位置插入步骤 | （直接操作 _steps） |
| `insert_key_at(index, key_name)` | 在指定位置插入按键 | → get_adb_keycode |
| `delete_step(index)` | 删除指定步骤 | （直接操作 _steps） |
| `delete_last_step()` | 删除最后步骤 | （直接操作 _steps/_raw_keys） |
| `_find_key_event_device()` | 自动检测按键输入设备 | → run_adb(getevent -pl) |
| `_start_getevent_listener()` | 启动 getevent 监听 | → subprocess.Popen |
| `_listen_loop()` | 读取 getevent 输出(线程) | → _parse_event_line |
| `_activity_sampler()` | Activity 采样(线程) | → get_current_activity |
| `_parse_event_line(line)` | 解析事件行 | → get_key_name, get_adb_keycode |
| `_group_raw_keys(raw_keys)` | 按时间间隔分组 | （纯数据处理） |
| `_save_steps(steps)` | 保存 steps.json | → get_case_dir(case_routes), _clean_steps_for_save |

---

### 2.5 回放引擎 (replay_engine.py)

**类**: `ReplayEngine`

| 方法 | 说明 | 调用了谁 |
|------|------|----------|
| `replay(case_key, repeat, stop_on_failure)` | 开始回放 | → check_adb_device, get_case_dir, _ensure_adb_root, _replay_worker(线程) |
| `quick_replay(case_key)` | 快速回放 | → replay(...) 的快速模式 |
| `stop()` | 停止回放 | → 设置 _stop_requested |
| `_replay_worker(...)` | 回放工作线程 | → _execute_single_run, VideoRecorder.start/stop, _save_json |
| `_execute_single_run(steps, run_dir)` | 执行单次回放 | → 以下各 executor |
| `_execute_key_group(step, ...)` | 执行按键组 | → send_keyevent, _send_long_press, get_current_activity, _wait_activity_stable, _take_screenshot |
| `_execute_adb_command(step, ...)` | 执行 ADB 命令 | → run_adb, get_current_activity, _take_screenshot |
| `_execute_ai_navigate(step, ...)` | 执行 AI 导航 | → ai_navigate(ai_client), _take_screenshot |
| `_execute_ai_verify(step, ...)` | 执行 AI 验证 | → ai_verify(ai_client), _take_screenshot |
| `_execute_wait(step, ...)` | 执行等待 | → time.sleep |
| `_take_screenshot(filepath)` | 截图 | → capture_card.take_screenshot |
| `_wait_activity_stable()` | 等待 Activity 稳定 | → get_current_activity |
| `_send_long_press(keycode, duration)` | 发送长按 | → get_linux_keycode, run_adb(sendevent) |
| `_ensure_adb_root()` | 确保 adb root | → run_adb |
| `_find_input_device()` | 查找 sendevent 设备 | → run_adb(getevent -pl) |
| `_build_steps_overview(steps)` | 生成步骤摘要(静态) | （纯数据处理） |

---

### 2.6 AI 客户端 (ai_client.py)

| 函数 | 说明 | 调用了谁 |
|------|------|----------|
| `upload_image(filepath)` | 上传截图到平台 | → _compress_image, requests.post |
| `chat(text, image_url, workflow_id)` | 单轮对话 | → chat_with_history |
| `chat_with_history(messages, workflow_id)` | 多轮对话 | → requests.post |
| `_parse_json_response(text)` | 从 AI 回复提取 JSON | （纯解析） |
| `_compress_image(filepath, max_size_kb, quality)` | 压缩图片 | → PIL.Image |
| `ai_navigate(prompt, device_serial, capture_func, max_rounds, stop_check)` | AI 导航循环 | → capture_func, upload_image, chat_with_history, _parse_json_response, send_keyevent |
| `ai_verify(prompt, screenshot_path)` | AI 验证截图 | → upload_image, chat, _parse_json_response |

**被谁调用**: replay_engine._execute_ai_navigate, replay_engine._execute_ai_verify

---

### 2.7 Jira 客户端 (jira_client.py)

**类**: `JiraClient`

| 方法 | 说明 | 调用了谁 |
|------|------|----------|
| `_get_config()` | 加载 Jira 配置 | → load_jira_config(config_manager) |
| `_request(method, url, config)` | HTTP 请求封装 | → requests |
| `_fetch_steps(config, jira_key)` | 获取测试步骤 | → _request |
| `_parse_issue(issue, config)` | 解析 Jira Issue | → _fetch_steps |
| `import_by_jql(jql, max_results)` | JQL 批量导入 | → _request, _parse_issue |
| `import_by_key(jira_key)` | 单个导入 | → _request, _parse_issue |
| `sync_case(jira_key)` | 重新同步 | → import_by_key |

**被谁调用**: case_routes (import_by_jql, import_by_key, sync_case)

---

### 2.8 视频录制 (video_recorder.py)

**类**: `VideoRecorder`

| 方法 | 说明 | 调用了谁 |
|------|------|----------|
| `start(output_path, fps, resolution)` | 开始录制 | → cv2.VideoWriter |
| `stop()` | 停止并转码 | → _transcode_to_h264(后台线程) |
| `_recording_loop(fps)` | 帧捕获循环(线程) | → capture_card.get_frame |
| `_transcode_to_h264(filepath)` | ffmpeg H.264 转码 | → subprocess(ffmpeg) |

**被谁调用**: replay_engine._replay_worker

---

### 2.9 Confluence 同步 (confluence_client.py)

| 函数 | 说明 | 调用了谁 |
|------|------|----------|
| `sync_to_confluence(data_dir)` | 异步同步(启动后台线程) | → _do_sync |
| `_do_sync(data_dir)` | 执行同步 | → _load_confluence_config, _scan_all_results, _build_html, requests |
| `_build_html(results)` | 构建 Confluence HTML | （纯数据处理） |

---

## 3. 核心调用链

### 3.1 录制流程

```
[前端] POST /api/tv/recording/start
  └─ recording_routes.start_recording()
       ├─ adb_utils.ensure_device_serial()     ← 未配置时自动检测
       └─ _get_recorder() → TVRecorder(device_serial, scripts_repo_path, key_event_device)
            └─ TVRecorder.start(case_key)
                 ├─ adb_utils.check_adb_device()
                 ├─ _find_key_event_device()
                 │    └─ adb_utils.run_adb(["shell", "getevent", "-pl"])
                 ├─ adb_utils.get_current_activity()     ← 记录初始 Activity
                 └─ _start_getevent_listener()
                      └─ subprocess.Popen(getevent -t <device>)
                           ├─ [线程] _listen_loop()
                           │    └─ _parse_event_line()
                           │         ├─ key_mappings.get_key_name()
                           │         └─ key_mappings.get_adb_keycode()
                           └─ [线程] _activity_sampler()
                                └─ adb_utils.get_current_activity()  (每 0.5s)
```

### 3.2 停止录制

```
[前端] POST /api/tv/recording/stop
  └─ recording_routes.stop_recording()
       └─ TVRecorder.stop()
            ├─ 终止 getevent 进程
            ├─ _flush_raw_keys_with_activity()
            │    └─ _group_raw_keys()
            └─ _save_steps()
                 ├─ case_routes.get_case_dir()
                 └─ _clean_steps_for_save()
```

### 3.3 回放流程

```
[前端] POST /api/tv/replay/start
  └─ replay_routes.start_replay()
       └─ get_shared_replay_engine()
            ├─ adb_utils.ensure_device_serial()     ← 未配置时自动检测
            └─ ReplayEngine(device_serial, data_dir, scripts_repo_path, capture_card)
                 └─ ReplayEngine.replay(case_key, repeat, stop_on_failure)
                      ├─ adb_utils.check_adb_device()
                      ├─ case_routes.get_case_dir()  → 加载 steps.json
                      ├─ _ensure_adb_root()
                      └─ [线程] _replay_worker()
                           └─ for run in range(repeat):
                                ├─ VideoRecorder.start()
                                ├─ _execute_single_run(steps, run_dir)
                                │    └─ for step in steps:
                                │         ├── [key_group]    → _execute_key_group()
                                │         │    ├─ adb_utils.send_keyevent() / _send_long_press()
                                │         │    ├─ adb_utils.get_current_activity()
                                │         │    ├─ _wait_activity_stable()
                                │         │    └─ _take_screenshot() → capture_card.take_screenshot()
                                │         ├── [adb_command]  → _execute_adb_command()
                                │         │    ├─ adb_utils.run_adb()
                                │         │    └─ _take_screenshot()
                                │         ├── [ai_navigate]  → _execute_ai_navigate()
                                │         │    └─ ai_client.ai_navigate()
                                │         │         ├─ capture_func() → capture_card.take_screenshot()
                                │         │         ├─ ai_client.upload_image()
                                │         │         ├─ ai_client.chat_with_history()
                                │         │         └─ adb_utils.send_keyevent()
                                │         ├── [ai_verify]    → _execute_ai_verify()
                                │         │    ├─ _take_screenshot()
                                │         │    └─ ai_client.ai_verify()
                                │         │         ├─ ai_client.upload_image()
                                │         │         └─ ai_client.chat()
                                │         └── [wait]         → _execute_wait()
                                ├─ VideoRecorder.stop()
                                │    └─ [线程] _transcode_to_h264() → ffmpeg
                                └─ _save_json(result.json / summary.json)
```

### 3.4 测试计划执行

```
[前端] POST /api/tv/plans/<plan_id>/run
  └─ plan_routes.run_plan()
       └─ [线程] _execute_plan(plan, ...)
            └─ for case in plan["cases"]:
                 ├─ adb_utils.check_adb_device()
                 ├─ adb_utils.send_keyevent(HOME)  ← 重置到首页
                 ├─ case_routes.get_case_dir()
                 ├─ get_shared_replay_engine() → ReplayEngine
                 ├─ ReplayEngine.replay(case_key, repeat)
                 ├─ 轮询 ReplayEngine.status 等待完成
                 ├─ _check_latest_replay_result()
                 └─ _save_json(plan_result.json)
```

### 3.5 用例管理（Jira 导入）

```
[前端] POST /api/tv/cases/import/jql
  └─ case_routes.import_by_jql()
       └─ JiraClient.import_by_jql(jql)
            ├─ _request("GET", /search?jql=...)
            └─ for issue in issues:
                 └─ _parse_issue(issue)
                      └─ _fetch_steps(jira_key)
                           └─ _request("GET", /synapse/.../steps)
       └─ for case in imported:
            ├─ _save_case(case.json)
            ├─ _build_index_entry()
            └─ update_index_entry()
                 └─ save_index(index.json)
```

### 3.6 视频流推送

```
[前端] GET /api/tv/stream
  └─ stream_routes.screen_stream()
       └─ Generator:
            ├─ capture_card.start()
            └─ loop:
                 └─ capture_card.get_frame_as_jpeg()
                      → yield MJPEG boundary frame
```

---

## 4. 跨模块依赖关系

### 依赖矩阵

```
                        被依赖方 →
调用方 ↓          utils  adb_utils  config_mgr  audit_log  capture_card  key_map  recorder  replay_eng  ai_client  jira_client  video_rec  case_routes  replay_routes
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
main_app           ·       ✓          ✓           ✓          ✓            ·         ·          ·           ·           ·            ·          ·             ·
app.py             ·       ·          ✓           ·          ·            ·         ·          ·           ·           ·            ·          ·             ·
config_routes      ·       ✓          ✓           ✓          ✓            ·         ·          ·           ·           ·            ·          ·             ·
recording_routes   ·       ✓          ·           ✓          ·            ✓         ✓          ·           ·           ·            ·          ✓             ✓
replay_routes      ·       ✓          ·           ✓          ✓            ·         ·          ✓           ·           ·            ·          ·             ·
case_routes        ·       ·          ✓           ✓          ·            ·         ·          ·           ·           ✓            ·          ·             ✓
plan_routes        ·       ✓          ·           ✓          ·            ·         ·          ·           ·           ·            ·          ✓             ✓
stats_routes       ·       ·          ·           ·          ·            ·         ·          ·           ·           ·            ·          ✓             ·
git_routes         ·       ·          ·           ·          ·            ·         ·          ·           ·           ·            ·          ·             ·
stream_routes      ·       ·          ·           ·          ✓            ·         ·          ·           ·           ·            ·          ·             ·
recorder           ✓       ✓          ·           ·          ·            ✓         ·          ·           ·           ·            ·          ✓(动态)       ·
replay_engine      ✓       ✓          ·           ·          ✓            ✓         ·          ·           ✓(动态)     ·            ✓(动态)    ✓(动态)       ·
ai_client          ·       ✓          ·           ·          ·            ·         ·          ·           ·           ·            ·          ·             ·
jira_client        ·       ·          ✓           ·          ·            ·         ·          ·           ·           ·            ·          ·             ·
video_recorder     ·       ·          ·           ·          ✓(间接)      ·         ·          ·           ·           ·            ·          ·             ·
```

### 跨路由模块调用（关键！修改时必须注意）

| 被导出函数 | 所属模块 | 被谁导入 |
|-----------|---------|---------|
| `get_case_dir()` | case_routes | recording_routes, plan_routes, stats_routes, recorder(动态), replay_engine(动态) |
| `load_index()` | case_routes | stats_routes, plan_routes |
| `save_index()` | case_routes | （内部使用） |
| `update_index_entry()` | case_routes | （内部使用） |
| `get_shared_replay_engine()` | replay_routes | recording_routes, plan_routes |

> **重要**: `get_case_dir()` 和 `get_shared_replay_engine()` 是跨模块共享最广的函数，修改其签名或行为需检查所有调用方。

---

## 5. 共享状态与单例

| 共享状态 | 位置 | 类型 | 访问者 |
|---------|------|------|--------|
| `capture_card` | capture_card.py 全局 | CaptureCardManager 单例 | config_routes, replay_routes, stream_routes, replay_engine, video_recorder |
| `_recorder` | recording_routes.py | TVRecorder 实例 | recording_routes 内部 |
| `_shared_engine` | replay_routes.py | dict(含 ReplayEngine) | replay_routes, recording_routes(via get_shared_replay_engine), plan_routes |
| `_plan_run_state` | plan_routes.py | dict(含 threading.Lock) | plan_routes 内部 |
| `device_config` | app.py 创建并传递 | dict | config_routes, recording_routes, replay_routes, stream_routes |
| `_session` | ai_client.py | requests.Session | ai_client 内部 |
| `ADB_PATH` | utils.py | str | adb_utils, recorder, replay_engine, capture_card |

### 线程安全机制

| 组件 | 锁 | 保护的资源 |
|------|-----|-----------|
| CaptureCardManager | `frame_lock` | `current_frame` |
| TVRecorder | `_lock` | `_steps`, `_raw_keys` |
| ReplayEngine | `_lock` | 状态字段 (`_is_replaying`, `_current_step` 等) |
| VideoRecorder | `_lock` | `_writer` |
| plan_routes | `_plan_run_state["lock"]` | 计划执行状态 |
| audit_log | `_lock` | 日志文件写入 |

---

## 6. API 端点清单

### 设备配置 (config_routes)
| 方法 | URL | 路由函数 | 核心依赖 |
|------|-----|---------|---------|
| GET | `/api/tv/config` | `get_config` | device_config |
| POST | `/api/tv/config` | `update_config` | config_manager, adb_utils, capture_card |
| GET | `/api/tv/capture-devices` | `list_capture_devices` | capture_card.enumerate |
| GET | `/api/tv/device/check` | `check_device` | adb_utils |
| GET | `/api/tv/input-devices` | `list_input_devices` | adb_utils.run_adb |
| GET | `/api/tv/adb_devices/list` | `adb_devices_list` | adb_utils.list_adb_devices |

### 录制 (recording_routes)
| 方法 | URL | 路由函数 | 核心依赖 |
|------|-----|---------|---------|
| POST | `/api/tv/recording/start` | `start_recording` | TVRecorder |
| POST | `/api/tv/recording/stop` | `stop_recording` | TVRecorder |
| GET | `/api/tv/recording/status` | `recording_status` | TVRecorder |
| POST | `/api/tv/recording/insert_adb` | `insert_adb_command` | TVRecorder |
| POST | `/api/tv/recording/insert_ai` | `insert_ai_instruction` | TVRecorder |
| POST | `/api/tv/recording/delete_last` | `delete_last_step` | TVRecorder |
| POST | `/api/tv/recording/insert_step_at` | `insert_step_at` | TVRecorder, key_mappings |
| POST | `/api/tv/recording/delete_step` | `delete_step` | TVRecorder |
| POST | `/api/tv/recording/quick_replay` | `quick_replay` | ReplayEngine(shared) |
| POST | `/api/tv/recording/quick_replay/stop` | `stop_quick_replay` | ReplayEngine(shared) |
| POST | `/api/tv/recording/send_key` | `send_key` | adb_utils, key_mappings |
| POST | `/api/tv/recording/send_adb` | `send_adb` | adb_utils |
| GET | `/api/tv/recording/saved_steps/<key>` | `get_saved_steps` | case_routes.get_case_dir |
| POST | `/api/tv/recording/saved_steps/<key>/insert` | `insert_saved_step` | case_routes, key_mappings |
| POST | `/api/tv/recording/saved_steps/<key>/delete` | `delete_saved_step` | case_routes |
| POST | `/api/tv/recording/saved_steps/<key>/update` | `update_saved_step` | case_routes, key_mappings |

### 回放 (replay_routes)
| 方法 | URL | 路由函数 | 核心依赖 |
|------|-----|---------|---------|
| POST | `/api/tv/replay/start` | `start_replay` | ReplayEngine |
| POST | `/api/tv/replay/stop` | `stop_replay` | ReplayEngine |
| GET | `/api/tv/replay/status` | `replay_status` | ReplayEngine |
| GET | `/api/tv/replay/results/<key>` | `list_results` | 文件扫描 |
| GET | `/api/tv/replay/result/<key>/<ts>` | `get_result` | 文件读取 |
| GET | `/api/tv/replay/result/<key>/<ts>/run/<idx>` | `get_run_result` | 文件读取 |
| GET | `/api/tv/replay/screenshot/...` | `get_screenshot` | send_file |
| GET | `/api/tv/replay/video/...` | `get_video` | send_file |

### 用例管理 (case_routes)
| 方法 | URL | 路由函数 | 核心依赖 |
|------|-----|---------|---------|
| GET | `/api/tv/cases` | `list_cases` | load_index |
| GET | `/api/tv/cases/<key>` | `get_case` | get_case_dir |
| POST | `/api/tv/cases/create` | `create_custom_case` | index 管理 |
| PUT | `/api/tv/cases/<key>` | `update_case` | index 管理 |
| DELETE | `/api/tv/cases/<key>` | `delete_case` | index 管理, shutil |
| POST | `/api/tv/cases/<key>/copy` | `copy_case` | index 管理 |
| POST | `/api/tv/cases/import/jql` | `import_by_jql` | JiraClient |
| POST | `/api/tv/cases/import/key` | `import_by_key` | JiraClient |
| POST | `/api/tv/cases/sync/<key>` | `sync_case` | JiraClient |
| GET | `/api/tv/modules` | `list_modules` | load_index, 目录扫描 |
| POST | `/api/tv/modules` | `create_module` | 目录创建 |
| PUT | `/api/tv/modules/<name>` | `rename_module` | os.rename, index |
| DELETE | `/api/tv/modules/<name>` | `delete_module` | shutil.rmtree |
| GET | `/api/tv/jira/config` | `get_jira_config` | config_manager |
| POST | `/api/tv/jira/config` | `save_jira_config` | config_manager |

### 测试计划 (plan_routes)
| 方法 | URL | 路由函数 | 核心依赖 |
|------|-----|---------|---------|
| GET | `/api/tv/plans` | `list_plans` | 文件扫描 |
| GET | `/api/tv/plans/<id>` | `get_plan` | _load_plan |
| POST | `/api/tv/plans` | `create_plan` | _save_plan |
| PUT | `/api/tv/plans/<id>` | `update_plan` | _load_plan, _save_plan |
| DELETE | `/api/tv/plans/<id>` | `delete_plan` | os.remove |
| POST | `/api/tv/plans/<id>/run` | `run_plan` | ReplayEngine(shared), adb_utils |
| POST | `/api/tv/plans/<id>/stop` | `stop_plan` | ReplayEngine(shared) |
| GET | `/api/tv/plans/<id>/status` | `plan_status` | _plan_run_state, ReplayEngine |
| GET | `/api/tv/plans/<id>/results` | `plan_results` | 文件扫描 |

### 统计 (stats_routes)
| 方法 | URL | 路由函数 | 核心依赖 |
|------|-----|---------|---------|
| GET | `/api/tv/stats` | `get_stats` | _scan_results, case_routes.load_index |

### Git 协作 (git_routes)
| 方法 | URL | 路由函数 | 核心依赖 |
|------|-----|---------|---------|
| POST | `/api/tv/git/commit` | `git_commit` | _run_git |
| POST | `/api/tv/git/pull` | `git_pull` | _run_git |
| GET | `/api/tv/git/status` | `git_status` | _run_git |
| GET | `/api/tv/git/log` | `git_log` | _run_git |
| GET | `/api/tv/git/file-content` | `git_file_content` | 文件读取 |

### 视频流 (stream_routes)
| 方法 | URL | 路由函数 | 核心依赖 |
|------|-----|---------|---------|
| GET | `/api/tv/stream` | `screen_stream` | capture_card |
| GET | `/api/tv/screenshot` | `take_screenshot` | capture_card |

---

## 7. 修改影响分析指南

### 修改某个模块时，需要检查的影响范围：

#### 修改 `adb_utils.py`
- **直接影响**: recorder, replay_engine, ai_client, config_routes, recording_routes, plan_routes
- **重点检查**: `run_adb()` 返回值格式、`send_keyevent()` 参数、`check_adb_device()` 返回值

#### 修改 `capture_card.py`
- **直接影响**: config_routes, replay_routes, stream_routes, replay_engine, video_recorder
- **重点检查**: `take_screenshot()` 返回值、`get_frame_as_jpeg()` 格式、`start()/stop()` 时序

#### 修改 `key_mappings.py`
- **直接影响**: recorder, replay_engine, recording_routes
- **重点检查**: 新增/删除按键映射、`get_adb_keycode()` 兜底行为

#### 修改 `recorder.py`
- **直接影响**: recording_routes
- **重点检查**: `start()/stop()` 返回值、steps 数据结构、属性（is_recording 等）

#### 修改 `replay_engine.py`
- **直接影响**: replay_routes, recording_routes(quick_replay), plan_routes
- **重点检查**: `replay()` 返回值、`status` 属性结构、result.json 格式

#### 修改 `ai_client.py`
- **直接影响**: replay_engine
- **重点检查**: `ai_navigate()` 返回值格式、`ai_verify()` 返回值格式

#### 修改 `case_routes.py`（特别是导出函数）
- **直接影响**: recording_routes, plan_routes, stats_routes, recorder(动态), replay_engine(动态)
- **重点检查**: `get_case_dir()` 参数/返回值、`load_index()` 数据结构、index.json 格式

#### 修改 `replay_routes.py`（特别是 get_shared_replay_engine）
- **直接影响**: recording_routes, plan_routes
- **重点检查**: `get_shared_replay_engine()` 返回的引擎状态

#### 修改步骤数据结构 (steps.json)
- **影响范围**: recorder(写入), replay_engine(读取+执行), recording_routes(编辑), case_routes(复制)
- **重点检查**: 新增字段需在 recorder 写入 + replay_engine 读取处同步、`_clean_steps_for_save()` 是否需更新

#### 修改结果数据结构 (result.json)
- **影响范围**: replay_engine(写入), replay_routes(读取), plan_routes(读取判断), stats_routes(聚合)
- **重点检查**: 所有读取 result.json 的地方是否兼容新字段

#### 修改 index.json 格式
- **影响范围**: case_routes(读写), stats_routes(读取), plan_routes(读取)
- **重点检查**: `load_index()`, `save_index()`, `update_index_entry()`, `_build_index_entry()`

### 新增步骤类型检查清单

如果要新增一种步骤类型（如 `wait`, `screenshot` 等）：

1. [ ] `recorder.py` — 添加插入方法（如 `insert_xxx()`）
2. [ ] `replay_engine.py` — 添加执行方法 `_execute_xxx()` 并在 `_execute_single_run()` 中分发
3. [ ] `replay_engine.py` — 在 `_build_steps_overview()` 中添加摘要文本
4. [ ] `recording_routes.py` — 添加 API 端点（如有需要）
5. [ ] `recording_routes.py` — 步骤编辑相关路由兼容新类型
6. [ ] 前端 — 录制界面支持新类型插入 + 回放状态展示

### 新增 API 端点检查清单

1. [ ] 在对应 routes 文件中添加路由函数
2. [ ] 确认蓝图已在 `app.py` 的 `register_tv_routes()` 中注册
3. [ ] 遵循统一响应格式 `{"success": bool, "message": str, "data": ...}`
4. [ ] 需要记录的操作调用 `audit_log()`
5. [ ] 前端对应页面添加 API 调用
