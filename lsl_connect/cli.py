"""
第 8 课：命令行控制面板（REPL）。
主线程解析命令，调用 ServiceManager。
"""

from __future__ import annotations

from lsl_connect.service_manager import ServiceManager
from lsl_connect.state import ServiceState

HELP_TEXT = """
命令:
  help              显示本帮助
  status            服务 / 采集状态
  start             启动采集 + LSL（仅 IDLE）
  stop              停止采集（RUNNING / ERROR）
  reset             ERROR 恢复为 IDLE
  config port COMx  设置串口（仅 IDLE）
  config filter on|off  开关滤波（仅 RUNNING）
  config labels CH1,CH2,...  设置 EEG 通道名（仅 IDLE，与 CSV 表头一致）
  gui hint          OpenBCI GUI / LSL 连接提示
  quit / exit       退出（会先 stop）
  model list        已登记模型
  model start <name>启动模型（需RUNNING）
  model stop <name> 停止指定模型
  record start [path]  开始 CSV 录制（需 RUNNING，可选文件路径）
  record stop            停止录制
  record status          录制状态
""".strip()

GUI_HINT_TEXT = """
[OpenBCI GUI 7 — STREAMING 验证（推荐 T3/T5）]
1. config/default.yaml 设 gui推流.启用: true
2. 控制面板: start → status 为 RUNNING
3. GUI 左侧选: STREAMING (from external)
4. 右侧填写:
     IP:   225.1.1.1
     PORT: 6677
     BOARD: Synthetic（合成板时）/ Cyton（真机时）
5. START SESSION → 再点绿色 Start Data Stream
6. T5: 保持 GUI + 控制面板 model start demo，跑 10 分钟

说明:
- 这是 BrainFlow UDP 推流，专供 GUI 7 的 STREAMING 模式
- 模型仍走 LSL(OpenBCI_EEG)，两路并行、互不冲突
- 不要用 CYTON (live) Serial，会抢 COM 口

[备选: LabRecorder 录 LSL 流 OpenBCI_EEG]
""".strip()

class ControlPanel:
    """交互式控制面板。"""

    def __init__(self,manager: ServiceManager)->None:
        self._mgr = manager
        self._alive=True

    def run(self)->None:
        print("=" * 50)
        print("OpenBCI EEG 控制面板 — 第 10 课")
        print("输入 help 查看命令")
        print("=" * 50)

        while self._alive:
            try:
                line =input(">").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                self._cmd_quit([])
                break

            if not line:
                continue
            self.dispath(line)

    def dispath(self,line:str)->None:
        parts = line.split()
        cmd = parts[0].lower()
        args=parts[1:]

        handlers ={
            "help": self._cmd_help,
            "?": self._cmd_help,
            "status": self._cmd_status,
            "start": self._cmd_start,
            "stop": self._cmd_stop,
            "reset": self._cmd_reset,
            "config": self._cmd_config,
            "gui": self._cmd_gui,
            "quit": self._cmd_quit,
            "model": self._cmd_model,
            "record": self._cmd_record,
            "exit": self._cmd_quit,
        }

        #输入命令对应取出方法
        handler = handlers.get(cmd)
        if handler is None:
           print(f"未知命令：{cmd}，输入help")
           return
        handler(args)

    def _cmd_help(self,_args: list[str])->None:
        print(HELP_TEXT)

    def _cmd_status(self,_args: list[str])->None:
        print(self._mgr.format_status())
        st=self._mgr.get_status()
        if st["state"] == ServiceState.RUNNING.value:
            print ("[LSL] OpenBCI_EEG (Outlet 活跃) | OpenBCI_Accel (ON)")

    def _cmd_start(self,_args: list[str])->None:
        if self._mgr.get_state() == ServiceState.ERROR:
            print("当前 ERROR，请先 reset 或 stop")
            return

        if self._mgr.start_acquisition():
            print("[OK] 采集已启动 → RUNNING")
            print("可输入 status 查看；gui hint 查看 GUI 连接说明")

        else:
            print(f"[失败] 无法 start（当前 {self._mgr.get_state().value}）")
            err = self._mgr.get_status().get("last_error")
            if err:
                print(f"  原因: {err}")

    def _cmd_stop(self,_args: list[str])->None:
        if self._mgr.stop_acquisition():
            print("[OK] 采集已停止 → IDLE")
        else:
            print(f"[失败] 无法 stop（当前 {self._mgr.get_state().value}）")

    def _cmd_reset(self, _args: list[str]) -> None:
        if self._mgr.reset():
            print("[OK] 已 reset → IDLE")
        else:
            print(f"[失败] 无法 reset（当前 {self._mgr.get_state().value}）")

    def _cmd_config(self,args: list[str]) -> None:
        if len(args) < 2:
            print("用法: config port COM10  |  config filter on|off  |  config labels 名1,名2,...")
            return

        sub =args[0].lower()
        value=args[1]

        if sub == "port":
            ok,msg=self._mgr.set_serial_port(value)
            print(f"{'[OK]' if ok else '[失败]'}{msg}")
        elif sub == "filter":
            v=value.lower()
            if v in("on","1","true"):
               ok,msg=self._mgr.set_filter_enabled(True)
            elif v in("off","0","false"):
                ok,msg=self._mgr.set_filter_enabled(False)

            else:
                print("用法：config filter on|off")
                return
            print(f"{'[OK]' if ok else '[失败]'} {msg}")
        elif sub == "labels":
            text = " ".join(args[1:]) if len(args) > 1 else value
            ok, msg = self._mgr.set_eeg_channel_labels(text)
            print(f"{'[OK]' if ok else '[失败]'} {msg}")
        else:
            print("未知 config 子命令，支持：port，filter，labels")

    def _cmd_gui(self,args: list[str]) -> None:
        if args and args[0].lower() !="hint":
            print("用法： gui hint")
            return
        print(GUI_HINT_TEXT)

    def _cmd_quit(self,args: list[str]) -> None:
        print("正在退出...")
        self._mgr.shutdown()
        self._alive=False
        print("再见。")

    def _cmd_model(self, args: list[str]) -> None:
        if not args:
            print("用法: model list | model start <name> | model stop <name>")
            return

        sub = args[0].lower()

        if sub == "list":
            specs = self._mgr.get_model_specs()
            if not specs:
                print("（无已登记模型，请检查 config/models.yaml）")
                return
            running = set(self._mgr.get_running_models())
            print("已登记模型:")
            for n in sorted(specs.keys()):
                spec = specs[n]
                mark = " *" if n in running else ""
                desc = spec.description or "（无说明）"
                print(
                    f"  {n}{mark}  |  {desc}  "
                    f"|  窗口={spec.window_size}  步长={spec.hop_size}"
                )
            print("  (* 表示运行中)")
            return

        if sub == "start":
            if len(args) < 2:
                print("用法: model start <name>")
                return
            ok, msg = self._mgr.start_model(args[1])
            print(f"{'[OK]' if ok else '[失败]'} {msg}")
            return

        if sub == "stop":
            if len(args) < 2:
                print("用法: model stop <name>")
                return
            ok, msg = self._mgr.stop_model(args[1])
            print(f"{'[OK]' if ok else '[失败]'} {msg}")
            return

        print("未知 model 子命令，支持: list / start / stop")

    def _cmd_record(self, args: list[str]) -> None:
        if not args:
            print("用法: record start [path] | record stop | record status")
            return

        sub = args[0].lower()
        if sub == "start":
            path = args[1] if len(args) > 1 else None
            ok, msg = self._mgr.start_recording(path)
            print(f"{'[OK]' if ok else '[失败]'} {msg}")
            return

        if sub == "stop":
            ok, msg, report = self._mgr.stop_recording()
            print(f"{'[OK]' if ok else '[失败]'} {msg}")
            if ok and report is not None:
                print("--- 录制质量 ---")
                print(report.summary_message())
            return

        if sub == "status":
            rec = self._mgr.get_recording_status()
            if rec.get("active"):
                print(
                    f"[录制] ON  path={rec.get('path')}  "
                    f"samples={rec.get('samples_written', 0)}"
                )
            else:
                print("[录制] OFF")
            return

        print("未知 record 子命令，支持: start / stop / status")
