# TV 自动化测试录制回放工具 - 需求文档

> 本工具仅针对 **TV 设备**，不涉及手机端功能,无关代码需要移除。

## 一、核心流程

测试人员根据测试用例（来自 Jira 或本地自定义）手动在 TV 上走一遍测试流程，工具录制所有操作。回归测试时通过回放自动执行，结合 AI 进行结果校验和动态导航。支持指定次数重复回放，适用于压测等场景。

```
测试用例（Jira 导入 / 本地自定义）→ 人工录制 → 保存操作序列 → 自动回放（支持重复 N 次）→ 生成测试报告
```

---

## 二、Jira 集成

### 2.1 连接配置

本地保存 Jira 连接信息（不入 Git）：

```json
// jira_config.json
{
  "base_url": "https://jira.tcl.com",
  "authorization": "Basic YXBwLWplbmtpbnMtMDE6WUgyMyZfMzJHMmhl"
}
```

### 2.2 导入方式

- **JQL 批量导入**：输入 JQL 查询语句（如 `project = 系统基线用例库 and issuetype = 测试用例`），批量拉取匹配的用例
- **Jira Key 单条导入**：输入单个 Jira Key（如 `PROJ-101`），逐条导入

### 2.3 拉取字段

参考 `script/get_jira_info.txt` 中的样本代码，拉取以下字段：

- **基础字段**：Key、summary、description、issuetype、priority、labels、reporter、created、updated、customfield_10107
- **测试步骤**：通过 `GET /rest/synapse/latest/public/testCase/{jira_key}/steps` 获取，包含 sequenceNumber、step、expectedResult、stepData

### 2.4 同步策略

- 支持手动触发重新同步，更新本地 `case.json` 中的 Jira 字段
- 录制数据和回放结果不受同步影响

### 2.5 过滤查询

- 按 Jira Key 精确/前缀匹配
- 按标题关键词模糊搜索
- 基于本地 `index.json` 查询，不依赖 Jira API

### 2.6 参考实现

完整样本代码见 `script/get_jira_info.txt`，关键 API：

```
# 获取用例详情
GET https://jira.tcl.com/rest/api/2/issue/{jiraKey}

# 获取测试步骤
GET https://jira.tcl.com/rest/synapse/latest/public/testCase/{jira_key}/steps

# JQL 批量搜索
GET https://jira.tcl.com/rest/api/2/search?jql={jql}
```

### 2.7 自定义用例

不依赖 Jira，在工具内直接创建本地测试用例，适用于压测、探索性测试等 Jira 中没有对应用例的场景。

**创建方式：**

- 前端提供"新建用例"入口（与 Jira 导入并列）
- 用户填写：用例名称（必填）、描述（选填）
- 工具自动生成本地唯一 Key，格式为 `LOCAL-{自增序号}`，如 `LOCAL-001`

**case.json 结构（自定义用例）：**

```json
{
  "key": "LOCAL-001",
  "source": "custom",
  "name": "压测场景-应用启动稳定性",
  "description": "循环启动主应用，验证冷启动是否稳定无崩溃",
  "created_at": "2026-02-12T10:00:00",
  "created_by": "DESKTOP-ABC123"
}
```

与 Jira 用例的区别：`source` 字段为 `"custom"`，无 Jira 相关字段（summary、priority、labels 等）。录制、回放、统计流程与 Jira 用例完全一致。

**index.json 中的标识：**

```json
{
  "key": "LOCAL-001",
  "name": "压测场景-应用启动稳定性",
  "source": "custom",
  "has_recording": true,
  "last_replay": "2026-02-12T11:00:00",
  "last_replay_result": "passed"
}
```

---

## 三、数据存储

所有数据保存本地，不上传数据库和阿里云。

### 3.1 存储路径

**不使用 C 盘固定路径，改为相对项目目录的路径。** 数据存放在工具代码同级目录下，便于移植和管理：

```
E:/project/ui-auto/
  ├── backend/                          ← 工具代码
  └── data/                             ← 所有运行时数据（不入工具代码 Git）
      ├── jira_config.json              ← Jira 连接配置
      ├── app_config.json               ← 工具配置（脚本仓库路径等）
      └── replay/                       ← 回放数据（截图、视频、结果）
          ├── PROJ-101/
          │   └── 2026-02-10_143000/
          │       ├── result.json
          │       ├── replay.mp4
          │       └── checkpoints/
          └── PROJ-102/
              └── ...
```

路径通过 `app_config.json` 配置，默认存放在 backend 目录下：

```json
// backend/app_config.json（入 Git，存默认配置）
{
  "data_dir": "./data",
  "scripts_repo_path": "./tv-test-scripts"
}
```

### 3.2 录制脚本（独立 Git 仓库，团队共享）

录制数据为纯文本（JSON），通过独立 Git 仓库管理，团队成员 pull 即可获取他人录制的脚本。

**录制时不截图、不录制视频。** 截图和视频仅在回放时产生。

```
tv-test-scripts/                        ← 独立 Git 仓库
  ├── .gitignore
  ├── index.json                        ← 用例索引（供过滤查询）
  ├── PROJ-101/
  │   ├── case.json                     ← Jira 用例信息
  │   └── steps.json                    ← 录制的操作序列（纯 JSON）
  ├── PROJ-102/
  │   └── ...
```

`.gitignore`：
```
jira_config.json
app_config.json
```

### 3.3 index.json（用例索引）

用于快速过滤，不需要每次遍历所有目录：

```json
[
  {
    "key": "PROJ-101",
    "summary": "验证WiFi设置页面功能",
    "status": "To Do",
    "priority": "High",
    "imported_at": "2026-02-10T14:30:00",
    "has_recording": true,
    "last_replay": "2026-02-10T16:00:00",
    "last_replay_result": "passed"
  }
]
```

---

## 四、录制

### 4.0 录制前置检查

点击"开始录制"时，先执行以下检查，任一失败则阻止录制启动并向用户展示具体错误原因：

**检查步骤：**

```
1. 执行 adb devices，解析输出
   ├── 命令本身失败（FileNotFoundError）→ 报错"ADB 工具未找到，请检查安装路径"，中止
   └── 继续

2. 检查配置的设备 serial 是否在 adb devices 列表中
   ├── 不在列表 → 报错"设备未连接，请检查 ADB 连接或 USB/网络"，中止
   └── 状态为 offline / unauthorized → 报错对应原因，中止

3. 执行 adb shell echo ok，验证命令可执行
   ├── 返回 "ok" → 检查通过
   └── 失败 → 报错"ADB 命令无法执行，请检查设备授权"，中止
```

检查通过后才启动 `getevent` 监听，开始录制。

### 4.1 按键录制

- 通过 ADB `getevent -t` 监听遥控器按键事件
- 区分短按和长按（阈值 1.5s）
- 记录每步的 ADB 回放命令
- **录制时不截图、不录制视频**

### 4.2 Activity 记录

- 每步操作执行前后，通过 `adb shell dumpsys window | grep -E "mCurrentFocus"` 获取当前 Activity
- 存入 `before_activity` 和 `after_activity`，供回放时对比校验

### 4.3 按键自动分组

- 按时间间隔自动分组：间隔 < 阈值（如 1s）的连续按键归为同一组
- 组内不截图不校验，保留原始操作节奏
- 组与组之间为自然的检查点

### 4.4 ADB 指令录制

录制过程中用户可手动输入 ADB 指令，工具执行并记录为独立操作步骤。

- 前端提供 ADB 指令输入框，录制期间随时可用
- 执行前后各获取一次 Activity，存入 `before_activity` / `after_activity`
- 不参与按键自动分组逻辑，作为独立步骤插入序列中
- 回放时直接执行该命令，同样做 Activity 前后对比

### 4.5 AI 指令插入

- 录制过程中，测试人员可随时插入 AI 指令，两种类型：
  - **ai_navigate**：动态导航，如"找到'设置'并进入"
  - **ai_verify**：校验断言，如"确认当前页面是 WiFi 设置页面"

### 4.6 操作序列数据结构（steps.json）

共四种操作类型：`key_group`（按键组）、`adb_command`（ADB 指令）、`ai_navigate`（AI 导航）、`ai_verify`（AI 校验）。

```json
[
  {
    "type": "key_group",
    "commands": [
      {"key": "DOWN", "adb_command": "input keyevent KEYCODE_DPAD_DOWN"},
      {"key": "DOWN", "adb_command": "input keyevent KEYCODE_DPAD_DOWN"},
      {"key": "ENTER", "adb_command": "input keyevent KEYCODE_ENTER"}
    ],
    "interval_ms": 150,
    "before_activity": "com.example.tv/.MainActivity",
    "after_activity": "com.example.tv/.SettingsActivity"
  },
  {
    "type": "adb_command",
    "command": "am force-stop com.example.tv",
    "description": "强制停止应用",
    "before_activity": "com.example.tv/.SettingsActivity",
    "after_activity": "com.android.launcher/.Launcher"
  },
  {
    "type": "ai_navigate",
    "prompt": "在当前列表中找到'网络设置'并选中，按ENTER进入"
  },
  {
    "type": "ai_verify",
    "prompt": "确认当前页面显示的是WiFi列表，且已连接到某个WiFi网络"
  },
  {
    "type": "key_group",
    "commands": [
      {"key": "BACK", "adb_command": "input keyevent KEYCODE_BACK"}
    ],
    "before_activity": "com.example.tv/.WifiSettingsActivity",
    "after_activity": "com.example.tv/.SettingsActivity"
  }
]
```

---

## 五、回放

### 5.1 回放前置

点击"开始回放"时，先执行与录制相同的 ADB 连接检查（见 4.0），任一失败则阻止回放启动。

检查通过后：
- 按 Home 键回到首页，确保起始状态一致

### 5.1.1 指定次数重复回放

启动回放时可指定重复次数（默认 1 次），适用于压测、稳定性验证等场景。

**参数：**
- `repeat`：重复次数（整数，≥ 1）
- `stop_on_failure`：遇到失败是否停止（默认 `false`，即继续跑完所有轮次）

**执行逻辑：**

```
for i in 1..repeat:
  按 Home 键重置起始状态
  执行完整回放流程（同单次回放）
  保存本次结果到 result_{i}.json
  ├── 失败且 stop_on_failure=true → 中止循环
  └── 否则 → 继续下一轮
生成汇总结果（passed/failed/aborted 各多少轮）
```

**结果目录结构（以重复 5 次为例）：**

```
data/replay/LOCAL-001/
  2026-02-12_100000/       ← 本次多轮回放任务目录
    summary.json           ← 汇总：5轮，passed 4，failed 1
    run_1/
      result.json
      replay.mp4
    run_2/
      result.json
      replay.mp4
    ...
```

**summary.json：**

```json
{
  "jira_key": "LOCAL-001",
  "repeat": 5,
  "stop_on_failure": false,
  "started_at": "2026-02-12T10:00:00",
  "finished_at": "2026-02-12T10:20:00",
  "total_duration_s": 1200,
  "passed": 4,
  "failed": 1,
  "aborted": 0,
  "pass_rate": 0.8,
  "runs": [
    {"run": 1, "result": "passed", "duration_s": 235},
    {"run": 2, "result": "passed", "duration_s": 241},
    {"run": 3, "result": "failed", "duration_s": 198, "failed_step": 7, "failed_reason": "before_activity 不一致"},
    {"run": 4, "result": "passed", "duration_s": 243},
    {"run": 5, "result": "passed", "duration_s": 239}
  ]
}
```

Confluence 统计上报时，多轮回放以每一轮作为独立条目计入统计。

### 5.2 回放引擎执行逻辑

```
对每个操作单元：

  key_group / adb_command:
    1. 获取当前 Activity，与录制时 before_activity 对比
       ├── 不一致 → 截图，标记"状态偏离"，中断回放
       └── 一致 → 继续
    2. 执行操作（按原始间隔执行按键组 / 执行 adb shell <command>）
    3. 等待画面稳定（Activity 轮询，见 5.4）
    4. 获取 Activity，与录制时 after_activity 对比
       ├── 一致 → 通过，进入下一个操作单元
       └── 不一致 → 尝试按 BACK 键恢复（见 5.2.1）

  ai_navigate:
    1. 截图 → 发给大模型（附带 prompt + 可用按键列表）
    2. 大模型返回按键指令 → 执行 → 再截图 → 再发给大模型
    3. 循环直到大模型返回"已完成"或达到最大轮次（如 20 次）
       └── 超过最大轮次 → 截图，标记"AI 导航超时"，中断回放

  ai_verify:
    1. 截图 → 发给大模型（附带 prompt）
    2. 大模型返回：通过/失败 + 判断理由 + 置信度
    3. 记录结果到报告
       ├── 通过 → 继续执行下一个操作单元
       └── 失败 → 标记该步失败，继续执行下一个操作单元（不中断）
```

### 5.2.1 after_activity 不一致的恢复策略

执行完按键组或 ADB 指令后，若 after_activity 与录制值不一致，说明可能出现了弹窗、广告、权限请求等干扰：

```
after_activity 不一致
  ↓
截图（记录当前异常页面）
执行 adb shell input keyevent KEYCODE_BACK（尝试关闭干扰层）
等待稳定后重新获取 Activity
  ├── Activity 恢复为预期值 → 标记该步"有干扰但已恢复"（警告），继续执行
  └── 仍不一致 → 截图，标记该步失败，中断回放
```

恢复只尝试一次，防止陷入循环。

### 5.2.2 异常处理策略汇总

| 异常类型 | 处理行为 | 说明 |
|----------|----------|------|
| before_activity 不一致 | 截图，**中断回放** | 状态已偏离，继续执行无意义 |
| after_activity 不一致，BACK 后恢复 | 标记警告，**继续** | 有干扰但状态已恢复 |
| after_activity 不一致，BACK 后仍不一致 | 截图，**中断回放** | 页面停留在意外状态 |
| ai_verify 失败 | 记录失败，**继续** | 校验断言失败，不影响后续步骤有效性 |
| ai_navigate 超过最大轮次 | 截图，**中断回放** | 目标页面未到达，当前状态未知 |

### 5.3 长按精确回放

- 使用 `sendevent` 代替 `input keyevent --longpress`，精确控制按住时长

### 5.4 页面就绪判断

不使用固定等待时间，也不使用截图对比。通过轮询 Activity 来判断页面是否就绪：

```
执行按键组
  ↓
轮询 dumpsys window mCurrentFocus（每 300ms 一次，最多等待 5s）
  ├── Activity 发生变化 → 页面已跳转，就绪
  └── 超时 Activity 未变化 → 认为是同页面内操作，直接继续
  ↓
对比录制时的 after_activity
```

Activity 轮询比截图轻量，且目的完全一致。同页面内内容加载的情况（如列表滚动）不在此处处理，交由 `ai_verify` 判断。

### 5.5 视频录制

- 回放全程通过采集卡后台线程录制视频
- 与回放引擎独立运行，对操作节奏零干扰
- 回放结束生成视频文件，供测试人员查看完整过程

---

## 六、测试计划

将多条测试用例组合为一个可复用的执行集合，一次启动即可顺序运行所有用例，并生成整体报告。

### 6.1 计划数据结构

计划定义文件存放在脚本 Git 仓库的 `plans/` 目录，与用例脚本一起共享：

```
tv-test-scripts/
  plans/
    PLAN-001.json
    PLAN-002.json
  PROJ-101/
    case.json
    steps.json
  LOCAL-001/
    ...
```

**PLAN-001.json：**

```json
{
  "id": "PLAN-001",
  "name": "WiFi功能回归测试",
  "description": "覆盖WiFi连接、断开、切换等核心场景",
  "created_at": "2026-02-12T10:00:00",
  "created_by": "DESKTOP-ABC",
  "cases": [
    {"key": "PROJ-101"},
    {"key": "PROJ-102"},
    {"key": "PROJ-103"},
    {"key": "LOCAL-001", "repeat": 10}
  ],
  "stop_on_failure": false
}
```

- `cases`：有序列表，执行时按顺序运行
- 单条用例可附带 `repeat` 参数（适合压测用例）
- `stop_on_failure`：某条用例失败时是否中止后续执行

### 6.2 执行流程

```
启动测试计划
  ↓
ADB 连接检查（同 4.0）
  ↓
for 每条用例 in plan.cases:
  ├── 无 steps.json → 标记 "no_script"，跳过，继续下一条
  ├── 按 Home 键重置起始状态
  ├── 执行单条用例回放（复用回放引擎，支持 repeat）
  └── 保存该用例结果
       ├── 失败且 stop_on_failure=true → 中止计划
       └── 否则 → 继续下一条
  ↓
生成 plan_result.json（计划汇总）
  ↓
上报 Confluence（异步，同单条用例回放）
```

前端实时展示当前执行进度（第 X 条 / 共 N 条）及各用例执行状态。

### 6.3 结果目录结构

```
data/replay/plans/
  PLAN-001/
    2026-02-12_100000/          ← 本次计划执行目录
      plan_result.json           ← 计划汇总结果
      PROJ-101/
        result.json
        replay.mp4
      PROJ-102/
        result.json
        replay.mp4
      LOCAL-001/
        run_1/ ... run_10/       ← repeat=10 时
        summary.json
```

### 6.4 plan_result.json

```json
{
  "plan_id": "PLAN-001",
  "plan_name": "WiFi功能回归测试",
  "run_at": "2026-02-12T10:00:00",
  "finished_at": "2026-02-12T10:45:00",
  "total_duration_s": 2700,
  "total_cases": 4,
  "passed": 3,
  "failed": 1,
  "no_script": 0,
  "aborted": 0,
  "pass_rate": 0.75,
  "cases": [
    {"key": "PROJ-101", "result": "passed",   "duration_s": 187},
    {"key": "PROJ-102", "result": "failed",   "duration_s": 142, "failed_step": 5, "failed_reason": "before_activity 不一致"},
    {"key": "PROJ-103", "result": "passed",   "duration_s": 210},
    {"key": "LOCAL-001", "result": "passed",  "duration_s": 1980, "repeat": 10, "repeat_pass": 9, "repeat_fail": 1}
  ]
}
```

### 6.5 Confluence 统计上报

测试计划执行完成后，以**每条用例每一轮**作为独立条目上报，与单条回放的统计口径一致，确保通过率等指标可跨维度汇总。

---

## 七、AI 能力

### 7.1 动态导航（ai_navigate）

- 解决动态内容（列表排序变化、推荐内容更新等）导致固定按键序列失效的问题
- 大模型根据截图理解当前画面，返回具体按键指令
- 设置最大轮次防止死循环

### 7.2 智能校验（ai_verify）

- 大模型根据截图 + prompt 进行语义级判断
- 不受动态内容（时间、推荐位等）干扰
- 返回结构化结果：通过/失败、理由、置信度

### 7.3 大模型接入

使用内部私有化部署的大模型，参考 `script/请求大模型.txt` 中的样本代码。

**接口信息：**

```
# 对话/工作流接口
POST https://chat-ape-dls.tclking.com/3rd_party/v1/chat/agent

# 图片上传接口
POST https://chat-ape-dls.tclking.com/chatape/v1/files/objects
```

**请求头：**

```python
headers = {
    "X-App-Signature": "XcHFOesX3prKv8tLYpkf351_BzfgLv4LZ2U47nDggYk=",
    "X-APP-ID": "abc1502b-93a9-45e9-b3dc-e518a6821866",
    "username": "zhaoji1.huang"
}
```

**流程：截图 → 上传图片获取 URL → 将 URL 作为内容发送给大模型 → 解析返回的 JSON 结果**

---

## 八、测试报告

每次回放生成报告，包含：

- 测试用例名称（关联 Jira Key）
- 总体结果：通过 / 失败
- 每步执行结果：Activity 校验结果、AI 校验结果及理由
- 失败步骤的截图
- 完整回放视频链接
- 执行时长

### 8.1 AI 操作过程记录

`ai_navigate` 和 `ai_verify` 的完整过程需要记录下来，供用户在报告中查看大模型做了什么。

**ai_navigate 记录结构：**

```json
{
  "type": "ai_navigate",
  "prompt": "找到'网络设置'并进入",
  "rounds": [
    {
      "round": 1,
      "screenshot": "navigate_0_round_1.jpg",
      "ai_response": {
        "action": "DOWN",
        "reason": "当前选中项是'显示设置'，目标'网络设置'在其下方"
      },
      "executed_key": "KEYCODE_DPAD_DOWN"
    },
    {
      "round": 2,
      "screenshot": "navigate_0_round_2.jpg",
      "ai_response": {
        "action": "ENTER",
        "done": true,
        "reason": "当前已选中'网络设置'，按ENTER进入"
      },
      "executed_key": "KEYCODE_ENTER"
    }
  ],
  "total_rounds": 2,
  "result": "success"
}
```

**ai_verify 记录结构：**

```json
{
  "type": "ai_verify",
  "prompt": "确认当前页面显示的是WiFi列表，且已连接到某个WiFi网络",
  "screenshot": "verify_1.jpg",
  "ai_response": {
    "passed": false,
    "reason": "WiFi开关显示为关闭状态，未连接到任何WiFi网络",
    "confidence": 0.95
  },
  "result": "failed"
}
```

以上记录保存在回放结果目录的 `result.json` 中，报告展示时按操作顺序呈现每个 AI 步骤的截图、大模型的判断理由和执行的操作。

### 8.2 result.json 完整数据结构

```json
{
  "jira_key": "PROJ-101",
  "summary": "验证WiFi设置页面功能",
  "replay_at": "2026-02-12T10:00:00",
  "duration_s": 187,
  "result": "passed",
  "total_steps": 12,
  "failed_step": null,
  "failed_reason": null,
  "operator": "DESKTOP-ABC123",
  "tool_version": "1.0.0",
  "steps": []
}
```

- `result`：`passed` / `failed` / `aborted`（前置检查失败或中途中断）
- `failed_step`：失败时记录步骤序号（从 0 开始）
- `failed_reason`：失败原因描述，如 "before_activity 不一致" / "AI 导航超时"
- `operator`：取本机 hostname，用于区分不同用户
- `steps`：每步详细执行记录（AI 操作过程、Activity 对比结果等）

---

## 九、团队协作

### 9.1 脚本共享

- 录制脚本通过独立 Git 仓库管理
- 录制数据为纯 JSON 文本，无图片视频，仓库轻量
- 团队成员 `git pull` 即可获取他人录制的脚本，直接回放

### 9.2 脚本提交

录制完成后由用户手动决定是否提交，不自动提交。

**流程：**

```
录制完成
  ↓
用户可选操作：回放验证脚本是否正确
  ↓
确认无误后，点击"提交到仓库"按钮
  ↓
前端展示待提交内容（哪些用例的脚本），用户确认
  ↓
后端执行：git add → git commit → git push
  ↓
提交成功，其他成员可通过 git pull 获取
```

**设计要点：**

- 录制完成后不自动提交，用户可能需要先回放验证
- 支持录制多个用例后一次性批量提交
- 录制失败或取消的脚本不会提交
- 提交前展示变更内容，由用户确认

### 9.3 手动同步脚本

前端提供"同步脚本"按钮，用户点击后从远程仓库拉取最新的录制脚本。

- 后端执行 `git -C <scripts_repo_path> pull`
- 拉取完成后刷新本地 `index.json`，前端更新用例列表
- 返回同步结果：新增/更新了哪些用例，或已是最新

适用场景：其他成员提交了新脚本后，无需重启工具即可获取。

### 9.4 工作流

```
测试人员 A：
  导入 Jira 用例 → 录制操作 → （可选）回放验证 → 提交到仓库

测试人员 B：
  启动工具（自动拉取最新）→ 获取 A 录制的脚本 → 回放 → 查看结果
  或：点击"同步脚本"按钮 → 获取最新脚本 → 回放
```

### 9.5 自动更新

服务启动时自动拉取最新的工具代码和录制脚本，确保用户每次执行的都是最新版本。

**更新流程（在 `main_app.py` 启动时、Flask 初始化之前执行）：**

```
启动 main_app.py
  │
  ├── 1. 检查本地是否有未提交的修改
  │     ├── 有 → 跳过更新，直接启动
  │     └── 没有 → 继续
  │
  ├── 2. git pull 工具代码仓库
  │     ├── 有更新 → 设置 JUST_UPDATED 标记，os.execv 重启自身
  │     └── Already up to date → 继续
  │
  ├── 3. git pull 脚本仓库（scripts_repo_path）
  │     └── 无论成功失败都继续启动
  │
  └── 4. 正常启动 Flask 服务
```

**关键设计：**

- **代码有更新时自动重启**：通过 `os.execv(sys.executable, [sys.executable] + sys.argv)` 用新进程替换当前进程，加载更新后的代码
- **防止无限重启**：通过环境变量 `JUST_UPDATED` 标记，重启后的新进程跳过更新检查
- **本地有修改时跳过**：通过 `git status --porcelain` 检查，避免覆盖用户正在开发的代码
- **网络不可用时不阻塞**：`git pull` 加 10 秒超时，失败后直接使用当前版本启动
- **脚本仓库热更新**：脚本是数据文件（JSON），拉取后不需要重启，直接可用

### 9.6 Git 仓库规范

- `jira_config.json`、`app_config.json` 不入 Git（含敏感配置）
- 回放数据不入 Git（截图、视频、结果存本地）
- 仅 `index.json`、`case.json`、`steps.json` 入 Git

---

## 十、使用统计

统计工具的整体使用情况，衡量使用量、有效性和稳定性。数据来源为每次回放产生的 `result.json`。

### 10.1 统计维度

| 维度 | 指标 |
|------|------|
| 使用量 | 总回放次数、活跃用户数（按 hostname 去重） |
| 有效性 | 通过率（passed / total）、各用例历史通过率 |
| 稳定性 | 中断率（aborted / total）、常见失败原因 Top N |

### 10.2 本地统计接口

`GET /api/stats` 扫描所有本地 `result.json` 文件，返回聚合结果：

```json
{
  "total_replays": 42,
  "passed": 35,
  "failed": 5,
  "aborted": 2,
  "pass_rate": 0.833,
  "avg_duration_s": 156,
  "by_case": [
    {"jira_key": "PROJ-101", "summary": "...", "total": 5, "passed": 4, "failed": 1}
  ],
  "recent": [
    {"jira_key": "PROJ-101", "replay_at": "...", "result": "passed", "duration_s": 187, "operator": "DESKTOP-ABC"}
  ]
}
```

### 10.3 Confluence 统计同步

**每次回放结束后自动同步到 Confluence**，无需手动操作，从而汇聚所有用户的使用数据。

**目标页面**：`https://confluence.tclking.com/pages/viewpage.action?pageId=670115830`

**Confluence 配置**（存入 `jira_config.json`，不入 Git）：

```json
{
  "confluence_url": "https://confluence.tclking.com",
  "confluence_page_id": "670115830",
  "confluence_token": "<Personal Access Token>"
}
```

> **说明**：使用 Confluence Personal Access Token（PAT）认证，请勿将 token 提交到 Git。

**认证方式**：

```python
headers = {
    "Authorization": "Bearer <confluence_token>",
    "Content-Type": "application/json"
}
```

**同步策略**：pageId 固定已知，直接读取当前版本号后覆盖更新：

```
回放结束
  ↓
保存 result.json（本地）
  ↓
后台异步执行（不阻塞用户操作）：
  1. GET /rest/api/content/670115830
     → 获取当前页面 version.number
  2. 读取所有本地 result.json，聚合统计数据
  3. 生成 Confluence Storage Format 页面内容（HTML 表格）
  4. PUT /rest/api/content/670115830
     body: { version: {number: current+1}, title: "...", body: {...} }
     ├── 成功 → 静默完成
     └── 失败（无网络/权限等）→ 记录日志，不影响主流程
```

**Confluence API：**

```
# 获取页面信息（含当前版本号）
GET https://confluence.tclking.com/rest/api/content/670115830

# 更新页面（version.number 需为当前值 +1）
PUT https://confluence.tclking.com/rest/api/content/670115830
Content-Type: application/json
Authorization: Bearer <token>

{
  "version": {"number": <current_version + 1>},
  "title": "TV 自动化测试 - 回放统计报告",
  "type": "page",
  "body": {
    "storage": {
      "value": "<HTML 表格内容>",
      "representation": "storage"
    }
  }
}
```

**Confluence 页面内容示例：**

```
TV 自动化测试 - 回放统计报告
（最后更新：2026-02-12 10:15 by DESKTOP-ABC）

汇总
  总回放次数：42   通过：35   失败：5   中断：2   通过率：83.3%
  平均执行时长：156 秒   活跃用户：3

最近 20 条记录（表格）
  时间 | 用例 | 执行人 | 结果 | 时长 | 失败原因

各用例统计（表格）
  用例 Key | 用例标题 | 总次数 | 通过 | 失败 | 通过率
```

---

## 十一、前端

### 11.1 技术栈

- **React 18** + **Ant Design 5**：组件化 UI 框架
- **Vite**：构建工具，开发热更新 + 生产打包
- **react-router-dom**：SPA 路由
- **axios**：HTTP 请求库

### 11.2 目录结构

```
frontend/
  vite.config.js              ← 配置：proxy /api → localhost:5004，build 输出到 backend/frontend_dist
  src/
    main.jsx                  ← 入口：BrowserRouter + Ant Design ConfigProvider (zhCN)
    api.js                    ← 统一 API 层（所有后端接口封装）
    App.jsx                   ← 主布局：左侧导航 Sider + 右侧内容区 Routes
    pages/
      DeviceConfig.jsx        ← 设备配置：采集卡选择/切换、TV IP、串口、ADB 连接检查、实时预览、Jira 配置
      CaseManagement.jsx      ← 用例管理：列表(搜索+来源筛选)、JQL 批量导入、Key 单条导入、新建自定义用例、详情查看、同步、删除
      Recording.jsx           ← 录制：选择用例、开始/停止、实时视频预览、ADB 指令输入、AI 指令插入、步骤列表、删除末步
      Replay.jsx              ← 回放：选择用例、指定重复次数、失败停止选项、进度展示、实时预览、历史结果表格、详情查看(步骤 Collapse)
      TestPlan.jsx            ← 测试计划：计划 CRUD、用例多选、执行计划(进度展示)、查看结果
      Statistics.jsx          ← 统计报表：汇总卡片(Statistic)、各用例统计表格、最近执行记录表格
      GitCollab.jsx           ← Git 协作：仓库状态、变更文件列表、提交(填写消息)、拉取同步、提交历史表格
```

### 11.3 构建与部署

```bash
# 开发模式（热更新，自动代理 API 请求）
cd frontend && npm run dev     # http://localhost:5173

# 生产构建（输出到 backend/frontend_dist/）
cd frontend && npm run build

# 访问（Flask 提供静态文件）
python main_app.py             # http://localhost:5004
```

构建产物 `frontend_dist/` 入 Git，用户无需安装 Node.js 即可使用。

### 11.4 页面导航

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | 设备配置 | 首页，采集卡选择和设备连接配置 |
| `/cases` | 用例管理 | Jira 导入 + 自定义用例 + 列表管理 |
| `/recording` | 录制 | 实时录制操作 |
| `/replay` | 回放 | 自动回放 + 结果查看 |
| `/plans` | 测试计划 | 多用例编排执行 |
| `/stats` | 统计报表 | 使用数据汇总 |
| `/git` | Git 协作 | 脚本版本管理 |

---

## 十二、优先级

| 优先级 | 模块 | 说明 |
|--------|------|------|
| P0 | 录制增强 | Activity 记录、按键分组、ADB 指令录制、AI 指令插入 |
| P0 | 回放引擎 | 按键回放、Activity 校验、画面稳定判断 |
| P1 | AI 集成 | 动态导航、智能校验（接入内部大模型） |
| P1 | 视频录制 | 回放过程全程录像 |
| P2 | Jira 集成 | 用例导入（JQL + 单条）、过滤查询、重新同步 |
| P2 | 测试报告 | 报告生成与展示 |
| P2 | 自动更新 | 启动时拉取最新代码和脚本，代码更新后自动重启 |
| P2 | 自定义用例 | 本地创建用例（LOCAL-xxx），无需 Jira，与现有录制回放流程完全一致 |
| P2 | 重复回放 | 指定次数重复回放，支持失败继续/中止，适用于压测场景 |
| P2 | 测试计划 | 多用例编排为可复用计划，顺序执行并生成汇总报告 |
| P2 | 使用统计 | 回放结果自动同步 Confluence，汇聚团队使用数据 |
| P1 | 前端重构 | React + Ant Design 5 全功能前端，覆盖所有后端 API |
