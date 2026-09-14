# LSL_connect_model — OpenBCI 脑电实时采集与分析平台

> Python + LSL 的脑电实验桌面平台：采集 → 在线预处理 → 模型推理 → 可视化 → CSV 录制，一条链路跑通。

## 这是什么

面向运动想象（Motor Imagery）等脑电实验的**采集与实验控制台**。上位机通过串口/合成板读取 OpenBCI 数据，经 LSL（Lab Streaming Layer）推流给算法侧，同时支持在线滤波、插件式模型推理、录制质量报告，并提供**图形界面**与**命令行**两套前端。

无硬件时可用「合成板」模式先跑通全链路。

## 核心能力

| 能力 | 说明 |
|---|---|
| 双数据源 | 真机串口（OpenBCI Cyton）与合成板（无硬件演练）一键切换 |
| LSL 推流 | 同时广播 EEG 流与加速度流，供外部算法/采集软件订阅 |
| 在线预处理 | 带通滤波（0.5–45Hz）+ 50Hz 陷波，参数可在配置中开关 |
| 模型插件 | 从 `config/models.yaml` 注册模型（类插件 / 函数插件两种方式），运行期动态启动/停止 |
| 数据录制 | CSV 按样本落盘 + 录制质量报告 + `.meta.json` 元数据，可复现 |
| 双前端 | 轻量 Tkinter UI（状态栏/控制条/结果网格/日志面板）与 CLI REPL（脚本化操作） |
| 状态机 | `state` + `service_manager` 统一管理 IDLE / RUNNING / ERROR 与生命周期 |

## 环境要求

- Python ≥ 3.9（推荐 3.10+）
- 依赖：`brainflow`、`numpy`、`pylsl`、`pyyaml`（Tkinter 随 Python 自带）
- 若用真机：OpenBCI 板卡 + 对应串口驱动；如需外部看流，安装 OpenBCI GUI 或任意 LSL 接收端

## 安装与运行

```bash
pip install -r requirements.txt

# 准备配置：示例配置 -> 实际配置，按自己的串口修改
cp config/default.example.yaml config/default.yaml
cp config/models.example.yaml  config/models.yaml

python main.py           # 图形界面（默认）
python main.py --cli     # 命令行控制面板
```

无硬件时，把 `config/default.yaml` 里的 `使用合成板` 设为 `true`，即可跑通采集 → 推流 → 录制全流程。

命令行常用指令：`status` / `start` / `stop` / `config port COMx` / `model list` / `record start`。

## 目录结构

```
main.py                 统一入口（GUI / CLI）
eeg_control_ui.py       图形界面入口
eeg_control_panel.py    命令行控制面板入口
eeg_broadcaster.py      LSL 广播辅助工具
lsl_connect/            核心包
├── board.py              板卡/合成板抽象
├── acquisition_work.py   采集线程与批次管理
├── lsl_streams.py        LSL 流定义与推流
├── preprocessing.py      在线滤波与预处理
├── model_worker.py       模型推理工作线程
├── recorder_worker.py    CSV 录制与质量报告
├── service_manager.py    服务生命周期编排
├── state.py              状态机
├── config_loader.py      配置加载与校验
└── ui/                   轻量 UI（app / widgets / controllers / event_bus / theme）
models/                 模型插件（base 接口 / registry 注册表 / demo_stats 示例）
config/                 配置（*.example.yaml 为模板，实际配置不入库）
scripts/                课程自测脚本（check_env + test_*）
docs/                   设计与教学文档
```

## 文档

| 文档 | 内容 |
|---|---|
| `docs/项目需求分析与技术概要.md` | 需求边界与总体技术方案 |
| `docs/项目框架-数据缓存与LSL协议.md` | 数据缓存结构与 LSL 协议约定 |
| `docs/轻量UI技术方案.md` | UI 架构与线程交互设计 |
| `docs/模型接入配置教程.md` | 如何把自己的模型注册成插件 |
| `docs/CSV本地录制扩展方案.md` | 录制格式、质量报告与扩展点 |
| `docs/教学计划.md` | 分课时的实现路线（scripts/ 下脚本与之对应） |

## 硬件与协议说明

- 数据源默认面向 OpenBCI Cyton（8 通道，250Hz）
- LSL 流名可在配置中修改：默认 `OpenBCI_EEG` 与 `OpenBCI_Accel`
- 通道标签按「第几列数据」映射（配置里的 `eeg通道标签` 顺序 = CSV 列顺序）
- 录制产物默认写入 `data/recordings/`（该目录不入版本库）

## 许可

本项目以 **MIT** 授权（见 [LICENSE](LICENSE)），可自由使用、修改与分发，保留版权声明即可。
