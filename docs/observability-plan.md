# TV 自动化测试工具 — 可观测性与可维护性方案

## 一、现状分析

### 1.1 日志体系

| 组件 | 现状 | 问题 |
|------|------|------|
| TeeOutput（main_app.py:78-102） | 自定义类，将 stdout/stderr 同时写到控制台和 `log/app.log` | 每次启动**清空日志文件**（第75行 `open(LOG_FILE, "w").close()`），历史记录全部丢失 |
| werkzeug 请求日志（main_app.py:213-214） | 被设为 ERROR 级别 | 所有正常 HTTP 请求不留痕迹，无法事后排查用户调了什么接口 |
| 日志轮转 | 无 | 长期运行日志文件无限增长，无自动清理 |

### 1.2 各层日志覆盖情况

#### API 路由层 — 几乎没有日志

| 文件 | 日志情况 |
|------|---------|
| replay_routes.py | 没有 import logging，没有任何日志 |
| recording_routes.py | 没有 import logging，没有任何日志 |
| config_routes.py | 没有 import logging，没有任何日志 |
| stream_routes.py | 没有 import logging，没有任何日志 |
| case_routes.py | 有 logger，但只在异常时记录（JQL 导入失败、同步失败） |
| plan_routes.py | 有 logger，主要在后台执行线程中记录异常 |
| git_routes.py | 有 logger |

**影响**：用户调了什么接口、传了什么参数、返回了什么结果，在日志里完全看不到。参数校验失败直接 return 400，日志里也找不到。

#### 引擎层 — 日志较完整

| 文件 | 覆盖内容 |
|------|---------|
| recorder.py | 开始/停止录制、按键释放事件（键名、时长、是否长按）、Activity 变化、插入操作、保存步骤 |
| replay_engine.py | 回放开始（case_key、第几次）、每步执行（步骤序号/类型）、Activity 校验、截图耗时、长按细节、AI 异常、等待步骤 |
| ai_client.py | 每轮截图/上传/对话耗时、模型原始返回、执行按键、导航完成/超时 |

**结论**：引擎干活时会记日志，但"谁让它干的"（API 入口）以及"干不了时的拒绝"（参数校验失败）没有记录。

### 1.3 其他可观测性

| 方面 | 现状 |
|------|------|
| 健康检查 | `/api/status` 只返回静态配置信息，不检查设备/采集卡/磁盘等实际状态 |
| 全局异常处理 | 未捕获的异常返回 HTML 500 页面，对前端不友好 |
| 操作审计 | 无独立的业务操作记录 |

---

## 二、改进方案

### 2.1 P0：日志轮转，不再清空（改动 ~5 行）

**问题**：每次重启清空 `app.log`，线上问题无法事后排查。

**方案**：用 `RotatingFileHandler` 替换当前逻辑，保留最近 5 个日志文件，每个最大 10MB。

```python
from logging.handlers import RotatingFileHandler

# 删除 open(LOG_FILE, "w").close()
# 替换 logging.basicConfig 中的 FileHandler
handler = RotatingFileHandler(
    LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
)
```

### 2.2 P0：API 请求日志中间件（改动 ~15 行）

**问题**：所有 API 请求不留痕迹。

**方案**：在 `main_app.py` 添加 `before_request` / `after_request` 中间件，统一记录。

```python
import time

logger = logging.getLogger("api")

@app.before_request
def log_request_start():
    request._start_time = time.time()

@app.after_request
def log_request_end(response):
    if not request.path.startswith('/api/'):
        return response
    duration = time.time() - getattr(request, '_start_time', time.time())

    # 请求参数摘要
    params = dict(request.args) if request.args else None
    body_summary = None
    if request.is_json and request.content_length and request.content_length < 2048:
        body_summary = request.get_json(silent=True)

    # 失败时记录错误信息
    error_info = None
    if response.status_code >= 400:
        error_info = response.get_data(as_text=True)[:500]

    logger.info(
        f"{request.method} {request.path} -> {response.status_code} ({duration:.2f}s)"
        f"{f' params={params}' if params else ''}"
        f"{f' body={body_summary}' if body_summary else ''}"
        f"{f' error={error_info}' if error_info else ''}"
    )
    return response
```

**记录策略**：

| 内容 | 是否记录 | 原因 |
|------|---------|------|
| 请求路径+方法+状态码+耗时 | 必须记录 | 基本排查信息，数据量小 |
| Query 参数 | 记录 | 通常不敏感，体积小 |
| Request Body | 仅记录 < 2KB 的 | 避免大数据（截图 base64）撑爆日志 |
| Response Body | 不记录 | 数据量大，和请求日志用途重复 |
| 异常响应（>=400） | 记录 error 摘要 | 排查问题必需 |

**日志效果示例**：

```
# 正常请求 — 简洁
POST /api/tv/replay/start -> 200 (0.35s) body={'case_key': 'SQAST-24894'}

# 失败请求 — 带错误信息
POST /api/tv/replay/start -> 400 (0.02s) body={'case_key': ''} error={"success":false,"error":"case_key 不能为空"}

# GET 请求带参数
GET /api/tv/stats/summary -> 200 (0.12s) params={'module': '设置'}

# 大 body（超过 2KB）不记录内容
POST /api/tv/recording/save -> 200 (1.20s)
```

**注意**：请求日志中间件**不会记录**录制/回放过程中的按键操作、AI 导航细节等——这些发生在后台线程中，不经过 HTTP 请求。这部分已由引擎层日志（recorder.py、replay_engine.py、ai_client.py）覆盖。

### 2.3 P1：全局异常处理返回 JSON（改动 ~5 行）

**问题**：未捕获的异常返回 HTML 500 页面，前端无法解析。

**方案**：

```python
@app.errorhandler(Exception)
def handle_exception(e):
    logger.exception(f"未捕获异常: {request.method} {request.path}")
    return jsonify({"success": False, "error": f"服务器内部错误: {str(e)}"}), 500
```

### 2.4 P1：健康检查接口（改动 ~20 行）

**问题**：`/api/status` 永远返回 `"ok"`，无法判断系统真实状态。

**方案**：新增 `/api/health` 接口，主动探测各依赖组件。

```python
@app.route("/api/health")
def health():
    checks = {
        "adb_device": check_adb_device(device_serial) if device_serial else "未配置",
        "capture_card": capture_card.is_opened() if capture_card else False,
        "scripts_repo": os.path.isdir(scripts_repo_path),
        "data_dir_writable": os.access(data_dir, os.W_OK),
        "disk_free_mb": shutil.disk_usage(data_dir).free // (1024*1024),
    }
    healthy = checks.get("data_dir_writable", False)
    return jsonify({"healthy": healthy, "checks": checks}), 200 if healthy else 503
```

**设计原则**：
- **只做诊断，不做修复** — 不会尝试重连 ADB 或重启采集卡
- 可被频繁调用（前端轮询/监控系统），无副作用
- 自动重连应放在各引擎内部（回放失败时重试、采集卡取帧失败时重连）

**使用场景**：
- 前端首页调用，设备没连直接提示用户
- 用户反馈"用不了"时，访问此接口一眼定位问题
- 后续接入监控系统，定时检测+告警

### 2.5 P2：关键操作审计日志（改动 ~15 行 + 各路由调用）

**问题**：普通日志（app.log）混杂技术细节，无法快速追溯业务操作历史。

**方案**：独立的 `data/audit.log`，JSON Lines 格式，只记录关键业务动作。

```python
def audit_log(action, case_key, detail=""):
    entry = {
        "time": datetime.now().isoformat(),
        "action": action,
        "case": case_key,
        "detail": detail,
    }
    with open(os.path.join(data_dir, "audit.log"), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
```

**记录的操作**：

```jsonl
{"time": "2026-03-06T14:30:01", "action": "录制开始", "case": "SQAST-24894"}
{"time": "2026-03-06T14:32:15", "action": "录制保存", "case": "SQAST-24894", "detail": "共12步"}
{"time": "2026-03-06T14:35:00", "action": "回放开始", "case": "SQAST-24894"}
{"time": "2026-03-06T14:36:20", "action": "回放完成", "case": "SQAST-24894", "detail": "通过 10/12步"}
{"time": "2026-03-06T14:40:00", "action": "用例删除", "case": "SQAST-24894"}
{"time": "2026-03-06T15:00:00", "action": "计划执行", "case": "PLAN-001", "detail": "包含5个用例"}
{"time": "2026-03-06T15:01:00", "action": "配置变更", "case": "", "detail": "tv_ip: 192.168.1.100 -> 192.168.1.101"}
```

**与普通日志的区别**：

| | 普通日志 (app.log) | 审计日志 (audit.log) |
|---|---|---|
| 记什么 | 所有技术细节（ADB 输出、异常堆栈、框架信息） | 只记业务操作 |
| 给谁看 | 开发者排查技术问题 | 管理者/使用者追溯操作历史 |
| 数据量 | 大，启动一次几千行 | 小，一次操作一行 |
| 格式 | 自由文本 | 结构化 JSON，方便搜索和统计 |

### 2.6 P3：前端错误上报（可选）

添加 `/api/report-error` 接口，让前端 JS 错误也能记录到后端日志，便于排查前端问题。

---

## 三、各层职责总结

```
┌─────────────────────────────────────────────────┐
│  请求日志中间件（P0 新增）                         │
│  记录：谁调了什么接口、参数、状态码、耗时、错误      │
│  不记录：后台线程中的操作细节                       │
├─────────────────────────────────────────────────┤
│  API 路由层                                      │
│  当前：几乎无日志                                  │
│  中间件补上后：入口/出口信息已覆盖                   │
├─────────────────────────────────────────────────┤
│  引擎层（recorder / replay_engine / ai_client）   │
│  当前：已有较完整的过程日志                         │
│  记录：按键操作、Activity 变化、AI 对话、截图耗时    │
├─────────────────────────────────────────────────┤
│  审计日志（P2 新增）                               │
│  记录：关键业务操作流水（录制/回放/删除/配置变更）    │
│  独立文件，结构化 JSON，面向业务追溯                 │
├─────────────────────────────────────────────────┤
│  健康检查（P1 新增）                               │
│  记录：各组件实时状态（ADB/采集卡/磁盘/仓库）       │
│  只诊断不修复，可频繁调用                           │
└─────────────────────────────────────────────────┘
```

---

## 四、实施优先级

| 优先级 | 改动 | 工作量 | 价值 |
|--------|------|--------|------|
| P0 | 日志轮转，不再启动清空 | ~5 行 | 保留历史日志，事后可排查 |
| P0 | API 请求日志中间件 | ~15 行 | 所有接口调用可追溯 |
| P1 | 全局异常处理返回 JSON | ~5 行 | 前端不再收到 HTML 错误页 |
| P1 | 健康检查接口 `/api/health` | ~20 行 | 快速定位系统问题 |
| P2 | 关键操作审计日志 | ~15 行 + 各路由调用 | 业务操作可追溯 |
| P3 | 前端错误上报接口 | ~1 个接口 | 前端问题可排查 |
