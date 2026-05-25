"""
脑电数据实时广播脚本 - OpenBCI Cyton 8通道 + LSL
功能：占有串口采集数据，通过LSL广播，供GUI和多个模型同时订阅
"""
import time
import sys
from brainflow.board_shim import BoardShim,BrainFlowInputParams,BoardIds
from brainflow.data_filter import DataFilter,FilterTypes
from pylsl import StreamInfo, StreamOutlet, local_clock
import numpy as np


#=========配置区域============
SERIAL_PORT = "COM10"    #串口号


# 无硬件时改为 True：使用 BrainFlow 合成数据，不占用串口
USE_SYNTHESIS = True
BOARD_ID=BoardIds.SYNTHETIC_BOARD.value if USE_SYNTHESIS else BoardIds.CYTON_BOARD.value
SAMPLE_RATE = 250
CHANNELS_COUNT=8

FILTER_ENABLED = True
BUFFER_SIZE = 25  # 每轮拉取样本数，约 100ms @ 250Hz
LOOP_SLEEP_SEC =0.005
STATS_EVERY_N_BATCHES =20  # 每 N 批打印一次统计

# Cyton：ADC -> 微伏
SCALE_EEG =4_500_000/24/(2**23-1)
SCALE_ACCEL =0.002/(2**4)

# =============================

def get_channel_indices(board_id):
    """获取 EEG、加速度计、时间戳在 BoardShim 矩阵中的行索引。"""
    eeg_channels = BoardShim.get_eeg_channels(board_id)
    accel_channels = BoardShim.get_accel_channels(board_id)
    timestamp_channels = BoardShim.get_timestamp_channel(board_id)
    return eeg_channels, accel_channels, timestamp_channels



def setup_lsl_streams(channel_count: int):
    """创建 LSL 数据流；channel_count 与当前板卡 EEG 通道数一致（合成板为 16，Cyton 为 8）。"""
    info_eeg = StreamInfo(
        name="OpenBCI_EEG",
        type="EEG",
        channel_count=channel_count,
        nominal_srate=SAMPLE_RATE,
        channel_format="float32",
        source_id="openbci_synthetic_eeg" if USE_SYNTHESIS else "openbci_cyton_8ch",
    )

    channels_desc = info_eeg.desc().append_child("channels")
    default_labels = ["Fp1", "Fp2", "C3", "C4", "P7", "P8", "O1", "O2"]
    for i in range(channel_count):
        label = default_labels[i] if i < len(default_labels) else f"Ch{i + 1}"
        ch = channels_desc.append_child("channel")
        ch.append_child_value("label", label)
        ch.append_child_value("unit", "microvolts")
        ch.append_child_value("type", "EEG")
    outlet_eeg = StreamOutlet(info_eeg)

    info_accel = StreamInfo(
        name='OpenBCI_Accel',
        type='ACC',  # 加速度计
        channel_count=3,  # X/Y/Z 3轴
        nominal_srate=SAMPLE_RATE,
        channel_format='float32',
        source_id='openbci_cyton_accel'
    )
    outlet_accel = StreamOutlet(info_accel)
    #会有lsl网络日志


    return outlet_eeg, outlet_accel

def initialize_board() -> BoardShim:
    """初始化并启动OpenBCI CYton版"""
    params=BrainFlowInputParams()
    if not USE_SYNTHESIS:
        params.serial_port=SERIAL_PORT
    board=BoardShim(BOARD_ID,params)


    try:
        board.prepare_session()
        #打印json日志信息
        board.start_stream(45000)
        if USE_SYNTHESIS:
            print("[OK] 已启动 BrainFlow 合成板（无硬件测试模式）")
        else:
            print(f"[OK] 已连接 OpenBCI Cyton，串口: {SERIAL_PORT}")
        return board
    except Exception as e:
        print(f"✗ 连接失败: {e}")
        if not USE_SYNTHESIS:
            print("  请检查: 1) COM 口  2) GUI 是否占用串口  3) Dongle 是否插入")
            print("  无设备时可设 USE_SYNTHESIS = True 做 LSL 推流测试")

        sys.exit(1)

def release_board(board :BoardShim) -> None:
    """停止推流并释放会话。"""
    try:
        board.stop_stream()
    except Exception :
        pass
    try:
        board.release_session()
    except Exception :
        pass
    print("[OK] 已释放硬件资源")

def apply_eeg_filter(eeg_data:np.ndarray) -> None:
    """原地滤波，形状 (n_channels, n_samples)。"""
    if not FILTER_ENABLED:
       # print("FILTER_ENABLED = False")
        return
    n_ch,_ = eeg_data.shape
    #0.5~45Hz 零相位二阶巴特沃斯带通滤波
    for ch in range(n_ch):
        DataFilter.perform_bandpass(
            eeg_data[ch],
            SAMPLE_RATE,
        0.5,
        45.0,
           2,
            FilterTypes.BUTTERWORTH_ZERO_PHASE.value,
            0,

        )
        #掐掉 50Hz

        DataFilter.perform_bandstop(
            eeg_data[ch],
            SAMPLE_RATE,
            49.0,
            51.0,
            2,
            FilterTypes.BUTTERWORTH_ZERO_PHASE.value,
            0,
        )

def push_eeg_chunk(outlet,eeg_data:np.ndarray) -> int:
    """推送一批 EEG 到 LSL，返回本批样本数。eeg_data: (n_channels, n_samples)。"""
    n_samples =eeg_data.shape[1]
    timestamps = [local_clock() for _ in range(n_samples)]
    # pylsl 的 2D chunk 约定为 (样本数, 通道数)
    chunk = np.ascontiguousarray(eeg_data.T, dtype=np.float32)
    outlet.push_chunk(chunk, timestamps)
    return n_samples

def push_accel_chunk(outlet, accel_data: np.ndarray) -> None:
    n_samples = accel_data.shape[1]
    timestamps = [local_clock() for _ in range(n_samples)]
    # pylsl 的 2D chunk 约定为 (样本数, 通道数)
    chunk = np.ascontiguousarray(accel_data.T, dtype=np.float32)
    outlet.push_chunk(chunk, timestamps)

def run_acquisition_loop(
        board: BoardShim,
        outlet_eeg,
        outlet_accel,
        eeg_channels,
        accel_channels,
) -> None:
    total_pushed =0
    batch_count =0
    print("-" * 50)
    print("采集循环运行中... Ctrl+C 停止")
    print(f"滤波: {'ON' if FILTER_ENABLED else 'OFF'} | 批大小: {BUFFER_SIZE}")
    print("-" * 50)

    while True:
        data =board.get_current_board_data(BUFFER_SIZE)
        if data.shape[1] == 0:
            time.sleep(LOOP_SLEEP_SEC)
            continue

        #astype数据的数据类型强制转为 64 位浮点数
        eeg_raw =data[eeg_channels,:].astype(np.float64)
        eeg_uv=eeg_raw*SCALE_EEG
        apply_eeg_filter(eeg_uv)
        n=push_eeg_chunk(outlet_eeg,eeg_uv.astype(np.float32))
        total_pushed += n
        batch_count += 1

        if len(accel_channels)>0 and accel_channels[0] < data.shape[0]:
            accel =data[accel_channels,:].astype(np.float64)*SCALE_ACCEL
            push_accel_chunk(outlet_accel,accel.astype(np.float32))

        if batch_count % STATS_EVERY_N_BATCHES == 0:
           print(f"[统计] 已累计推送约 {total_pushed} 个EEG 样本")
        time.sleep(LOOP_SLEEP_SEC)



def main() -> None:
    print("=" * 50)
    print("OpenBCI EEG 实时广播 — 第 3 课（P0）")
    print("=" * 50)
    mode = "合成板(无硬件)" if USE_SYNTHESIS else f"Cyton @ {SERIAL_PORT}"
    print(f"模式: {mode}")
    print(f"采样率: {SAMPLE_RATE} Hz")
    print("-" * 50)
    board = None
    try:
        board = initialize_board()
        eeg_ch, accel_ch, ts_ch = get_channel_indices(BOARD_ID)

        eeg_ch_full = BoardShim.get_eeg_channels(BOARD_ID)
        if USE_SYNTHESIS:
            eeg_ch = eeg_ch_full[:CHANNELS_COUNT]  # 只用前 8 路 → [1..8]
        else:
            eeg_ch = eeg_ch_full  # 真 Cyton 本来就是 8 路

        n_eeg = len(eeg_ch)
        print(f"EEG 通道索引: {eeg_ch} (共 {n_eeg} 个)")
        print(f"加速度计通道索引: {accel_ch}")
        print(f"时间戳通道索引: {ts_ch}")
        outlet_eeg, outlet_accel = setup_lsl_streams(n_eeg)
        print("[OK] LSL 数据流已创建")
        run_acquisition_loop(board, outlet_eeg, outlet_accel, eeg_ch, accel_ch)
    except KeyboardInterrupt:
        print("\n用户中断，正在停止...")
    finally:
        if board is not None:
            release_board(board)
    print("=" * 50)


if __name__ == "__main__":
    main()


