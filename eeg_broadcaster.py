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
from lsl_connect.lsl_streams import BoardToLslTimestampMapper,push_eeg_chunk,push_accel_chunk

#=========配置区域============
SERIAL_PORT = "COM10"    #串口号


# 无硬件时改为 True：使用 BrainFlow 合成数据，不占用串口
USE_SYNTHESIS = False
BOARD_ID=BoardIds.SYNTHETIC_BOARD.value if USE_SYNTHESIS else BoardIds.CYTON_BOARD.value
SAMPLE_RATE = 250
CHANNELS_COUNT=8

FILTER_ENABLED = True
BUFFER_SIZE = 25  # # 方案 A 下：单批最多处理的样本数（不是 get_board_data 的参数）
LOOP_SLEEP_SEC =0.005
STATS_EVERY_N_BATCHES =20  # 每 N 批打印一次统计

# Cyton：ADC -> 微伏
SCALE_EEG =4_500_000/24/(2**23-1)
SCALE_ACCEL =0.002/(2**4)

_ts_mapper =BoardToLslTimestampMapper()

# 时间戳自检（板卡 → LSL 映射是否正常）
TIMESTAMP_SELF_CHECK = True
TIMESTAMP_CHECK_EVERY_N_BATCHES = 20   # 与 STATS 相同或单独设
TIMESTAMP_CHECK_WARN_RATIO = 0.5       # 实测跨度 < 期望*0.5 时打印 [警告]
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
        _ts_mapper.reset()
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


def check_timestamp_batch(
    board_ts: np.ndarray,
    lsl_ts: list[float],
    sample_rate: int = SAMPLE_RATE,
) -> None:
    """
    自检一批时间戳：板卡间隔 + 映射后 LSL 间隔是否接近 (n-1)/fs。
    在采集循环里周期性调用即可。
    """
    n = len(lsl_ts)
    if n < 2:
        print("[时间戳自检] 样本数 < 2，跳过")
        return

    board_ts = np.asarray(board_ts, dtype=np.float64).reshape(-1)
    expected = (n - 1) / float(sample_rate)

    span_board = float(board_ts[-1] - board_ts[0])
    span_lsl = float(lsl_ts[-1] - lsl_ts[0]) if len(lsl_ts) >= 2 else 0.0

    # 板卡时间应单调不减（偶尔相等可容忍）
    mono_ok = bool(np.all(np.diff(board_ts) >= -1e-9))

    print(
        f"[时间戳自检] n={n} 期望跨度≈{expected:.4f}s | "
        f"板卡={span_board:.4f}s LSL={span_lsl:.4f}s | "
        f"单调={'OK' if mono_ok else '异常'}"
    )

    if span_board < expected * TIMESTAMP_CHECK_WARN_RATIO:
        print("  [提示] 板卡戳在本批内几乎相同（Cyton 常见）；若已用 to_lsl_uniform 可忽略")

def run_acquisition_loop(
        board: BoardShim,
        outlet_eeg,
        outlet_accel,
        eeg_channels,
        accel_channels,
        ts_channel:int,
) -> None:
    total_pushed =0
    batch_count =0
    print("-" * 50)
    print("采集循环运行中... Ctrl+C 停止")
    print(f"滤波: {'ON' if FILTER_ENABLED else 'OFF'} | 单批上限: {BUFFER_SIZE}")
    print("-" * 50)

    while True:
        data =board.get_board_data()
        if data.shape[1] == 0:
            time.sleep(LOOP_SLEEP_SEC)
            continue

        # 可选：单批太多时只处理最后一段，避免一次滤波过重
        if data.shape[1] > BUFFER_SIZE:
            data = data[:, -BUFFER_SIZE:]

        #astype数据的数据类型强制转为 64 位浮点数
        eeg_raw =data[eeg_channels,:].astype(np.float64)
        eeg_uv=eeg_raw*SCALE_EEG
        apply_eeg_filter(eeg_uv)
        #得到这一批 25 个点的板卡时间。
        board_ts=data[ts_channel,:]
        #配置区的BoardToLslTimestampMapper()全局映射器
        lsl_ts=_ts_mapper.to_lsl_uniform(board_ts,SAMPLE_RATE)

        n=push_eeg_chunk(outlet_eeg,eeg_uv.astype(np.float32),timepstamps=lsl_ts)
        total_pushed += n
        batch_count += 1

        if TIMESTAMP_SELF_CHECK and batch_count % TIMESTAMP_CHECK_EVERY_N_BATCHES == 0:
            check_timestamp_batch(board_ts, lsl_ts)

        if len(accel_channels)>0 and accel_channels[0] < data.shape[0]:
            accel =data[accel_channels,:].astype(np.float64)*SCALE_ACCEL
            push_accel_chunk(outlet_accel,accel.astype(np.float32),timestamps=lsl_ts)

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
        run_acquisition_loop(board, outlet_eeg, outlet_accel, eeg_ch, accel_ch,ts_ch)
    except KeyboardInterrupt:
        print("\n用户中断，正在停止...")
    finally:
        if board is not None:
            release_board(board)
    print("=" * 50)


if __name__ == "__main__":
    main()


