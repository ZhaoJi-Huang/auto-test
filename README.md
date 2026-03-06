# TV 自动化测试录制回放工具

基于 Python/Flask + React 的 TV 设备 UI 自动化测试工具，通过 ADB + 视频采集卡实现测试用例的录制与回放。

## 环境要求

- Python 3.8+
- Node.js 16+（仅前端开发/构建时需要）
- ADB（Android Debug Bridge），需加入系统 PATH
- USB 视频采集卡（用于捕获 TV 画面）
- TV 设备通过网络连接（ADB over TCP，默认端口 5555）

## 快速开始

### 1. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 构建前端

```bash
cd backend/frontend
npm install
npm run build
```

构建产物会输出到 `backend/frontend_dist/`，由后端静态托管。

### 3. 启动服务

```bash
cd backend
python main_app.py
```

服务启动后访问 http://localhost:5004

### 4. 连接设备

1. 将视频采集卡通过 USB 连接到电脑，HDMI 端连接 TV
2. 确保 TV 已开启 ADB 调试，通过网络可达（`adb connect <IP>:5555`）
3. 在「设备配置」页面完成采集卡选择和设备 IP 配置

## 配置说明

应用配置文件为 `backend/app_config.json`：

```json
{
  "data_dir": "./data",              // 运行时数据目录（回放结果、配置等）
  "scripts_repo_path": "./tv-test-scripts"  // 测试脚本 Git 仓库路径
}
```

## 功能页面介绍

### 设备配置

硬件连接与基础配置管理页面。

- 选择和切换视频采集卡
- 配置 TV 设备 IP 地址，检测设备连接状态
- 选择遥控器红外接收设备（input device）
- 配置 Jira 连接信息（Base URL、认证 Token）
- 实时预览采集卡画面

### 录制

测试用例步骤录制页面，将操作过程记录为可回放的脚本。

- 选择目标用例后开始录制，自动捕获遥控器按键操作
- 支持 5 种步骤类型：按键（含长按）、ADB 命令、AI 导航、AI 验证、等待延时
- 录制过程中可手动插入、编辑、删除步骤
- 录制完成后支持快速回放验证
- 三栏布局：用例详情 + 实时画面 + 步骤列表

### 回放

执行已录制的测试用例并查看详细结果。

- 选择用例发起回放，实时观看执行过程
- 逐步骤展示执行结果：状态、截图、耗时、AI 推理过程
- 失败步骤自动展开，方便定位问题
- 支持多轮回放及回放视频录制
- 历史结果浏览与对比

### 用例管理

测试用例的创建、导入与维护。

- 从 Jira 导入用例（支持 JQL 批量查询或按 Key 单个导入）
- 手动创建自定义用例，填写描述、前置条件、测试步骤
- 编辑、复制、删除用例
- 同步 Jira 用例最新数据
- 查看用例详情：元信息、测试步骤、已录制的脚本

### 测试计划

批量执行多个用例的计划管理。

- 创建测试计划，选择要执行的用例集合
- 配置执行轮次（每个用例可重复执行多次）
- 执行过程实时监控：当前用例进度、步骤进度条、已完成列表
- 支持暂停/停止执行
- 查看历史执行结果：通过率统计、逐用例结果、多轮明细

### 统计报表

测试执行数据的汇总分析。

- 总览指标：总执行次数、通过率、失败率、中断率、平均耗时
- 按用例维度统计：执行次数、通过/失败次数、单用例通过率
- 近期执行历史：时间、用例、执行人、结果、耗时

### Git 协作

测试脚本的版本管理与团队协作。

- 查看工作区变更状态，按文件勾选要提交的内容
- 点击文件名预览文件内容
- 填写提交信息后选择性提交
- 拉取远程最新变更
- 查看提交历史记录

## 项目结构

```
backend/
  main_app.py                 # 服务入口
  app_config.json             # 应用配置
  requirements.txt            # Python 依赖
  frontend/                   # 前端源码（React）
  frontend_dist/              # 前端构建产物
  common/                     # 公共模块（ADB、配置管理）
  tv_annotation/              # TV 核心业务模块
    routes/                   # API 路由
    capture_card.py           # 采集卡管理
    recorder.py               # 录制引擎
    replay_engine.py          # 回放引擎
    ai_client.py              # AI 大模型客户端
    jira_client.py            # Jira API 客户端
data/                         # 运行时数据（回放结果、设备配置等）
tv-test-scripts/              # 测试脚本 Git 仓库（团队共享）
```
