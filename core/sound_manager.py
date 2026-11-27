import os
import json
import math
import time
import random
import threading
from array import array
from PyQt6.QtCore import (
    QObject, QThread, QIODevice, QTimer, pyqtSignal, pyqtSlot, QCoreApplication, Qt
)
from PyQt6.QtMultimedia import QAudio, QAudioSink, QAudioFormat, QMediaDevices


class _WaveformSynthesizer:
    """위상 연속성 및 0-크로싱 페이드를 적용한 무클릭 PCM 파형 합성기"""

    def __init__(self, sample_rate: int = 44100):
        self.sr = max(8000, int(sample_rate))

    def _apply_edge_fade(
        self,
        samples: list[float],
        fade_in_ms: float = 3.0,
        fade_out_ms: float = 14.0,
    ) -> list[float]:
        n = len(samples)
        if n == 0:
            return samples
        fi = min(n // 2, max(1, int(self.sr * fade_in_ms / 1000.0)))
        fo = min(n // 2, max(1, int(self.sr * fade_out_ms / 1000.0)))
        for i in range(fi):
            samples[i] *= (i / fi)
        for i in range(fo):
            samples[n - 1 - i] *= (i / fo)
        samples[0] = 0.0
        samples[-1] = 0.0
        return samples

    def synth_key_tick(self, pitch_mult: float = 1.0) -> list[float]:
        dur = 0.022
        n = int(self.sr * dur)
        out = [0.0] * n
        rng = random.Random(int(pitch_mult * 1000))
        prev_noise = 0.0
        for i in range(n):
            t = i / self.sr
            env = math.exp(-t * 200.0)
            body = math.sin(2 * math.pi * (240.0 * pitch_mult) * t) * 0.65
            sub = math.sin(2 * math.pi * (115.0 * pitch_mult) * t) * 0.45
            prev_noise = 0.72 * prev_noise + 0.28 * rng.uniform(-1.0, 1.0)
            out[i] = (body + sub + prev_noise * 0.35) * env * 0.55
        return self._apply_edge_fade(out, fade_in_ms=1.5, fade_out_ms=5.0)

    def synth_cooldown_block(self) -> list[float]:
        dur = 0.080
        n = int(self.sr * dur)
        out = [0.0] * n
        phase = 0.0
        for i in range(n):
            t = i / self.sr
            freq = 150.0 if t < 0.038 else 105.0
            phase += 2 * math.pi * freq / self.sr
            env = math.exp(-t * 34.0)
            wave_val = math.sin(phase) + 0.33 * math.sin(3 * phase)
            out[i] = wave_val * env * 0.20
        return self._apply_edge_fade(out, fade_in_ms=3.0, fade_out_ms=12.0)

    def synth_cmd_done(self) -> list[float]:
        notes = [523.25, 783.99]
        step = 0.052
        note_dur = 0.11
        n = int(self.sr * (step + note_dur))
        out = [0.0] * n
        for idx, freq in enumerate(notes):
            start_i = int(idx * step * self.sr)
            span = min(n - start_i, int(note_dur * self.sr))
            for j in range(span):
                lt = j / self.sr
                atk = min(1.0, lt / 0.004)
                env = atk * math.exp(-lt * 30.0)
                s = math.sin(2 * math.pi * freq * lt) + 0.28 * math.sin(4 * math.pi * freq * lt)
                out[start_i + j] += s * env * 0.28
        return self._apply_edge_fade(out, fade_in_ms=2.0, fade_out_ms=15.0)

    def synth_cooling_ok(self) -> list[float]:
        dur = 0.16
        n = int(self.sr * dur)
        out = [0.0] * n
        rng = random.Random(42)
        lp = 0.0
        for i in range(n):
            t = i / self.sr
            lp = 0.65 * lp + 0.35 * rng.uniform(-1.0, 1.0)
            noise_env = math.exp(-t * 28.0)
            ping_env = math.exp(-t * 24.0)
            ping = math.sin(2 * math.pi * 880.0 * t)
            out[i] = (lp * noise_env * 0.40 + ping * ping_env * 0.45) * 0.40
        return self._apply_edge_fade(out, fade_in_ms=3.0, fade_out_ms=18.0)

    def synth_harvest(self, synced: bool = False) -> list[float]:
        """부드럽게 겹치는 가산 아르페지오 — 음 전환 시 클릭·끊김 완전 제거"""
        notes = [329.63, 493.88, 659.25, 987.77] if synced else [329.63, 493.88, 659.25]
        step = 0.048
        note_dur = 0.17
        n = int(self.sr * (step * (len(notes) - 1) + note_dur))
        out = [0.0] * n
        for idx, freq in enumerate(notes):
            start_i = int(idx * step * self.sr)
            span = min(n - start_i, int(note_dur * self.sr))
            for j in range(span):
                lt = j / self.sr
                atk = min(1.0, lt / 0.006)
                rem = note_dur - lt
                rel = min(1.0, max(0.0, rem / 0.025))
                env = atk * math.exp(-lt * 15.0) * rel
                s = (
                    math.sin(2 * math.pi * freq * lt)
                    + 0.22 * math.sin(2 * math.pi * (freq * 1.5) * lt)
                )
                out[start_i + j] += s * env * 0.26
        return self._apply_edge_fade(out, fade_in_ms=4.0, fade_out_ms=22.0)

    def synth_upgrade_buy(self) -> list[float]:
        dur = 0.17
        n = int(self.sr * dur)
        out = [0.0] * n
        for i in range(n):
            t = i / self.sr
            click = math.sin(2 * math.pi * 1400.0 * t) * math.exp(-t * 150.0)
            chord_env = math.exp(-t * 20.0)
            chord = (
                math.sin(2 * math.pi * 440.0 * t) * 0.5
                + math.sin(2 * math.pi * 659.25 * t) * 0.4
            ) * chord_env
            out[i] = (click * 0.45 + chord * 0.55) * 0.36
        return self._apply_edge_fade(out, fade_in_ms=2.5, fade_out_ms=18.0)

    def synth_story_unlock(self) -> list[float]:
        notes = [261.63, 329.63, 392.00, 493.88, 587.33]
        step = 0.070
        note_dur = 0.28
        n = int(self.sr * (step * (len(notes) - 1) + note_dur))
        out = [0.0] * n
        for idx, freq in enumerate(notes):
            start_i = int(idx * step * self.sr)
            span = min(n - start_i, int(note_dur * self.sr))
            for j in range(span):
                lt = j / self.sr
                atk = min(1.0, lt / 0.008)
                env = atk * math.exp(-lt * 9.0)
                out[start_i + j] += math.sin(2 * math.pi * freq * lt) * env * 0.16
        return self._apply_edge_fade(out, fade_in_ms=4.0, fade_out_ms=30.0)

    def synth_news_good(self) -> list[float]:
        notes = [659.25, 880.0]
        step = 0.080
        note_dur = 0.14
        n = int(self.sr * (step + note_dur))
        out = [0.0] * n
        for idx, freq in enumerate(notes):
            start_i = int(idx * step * self.sr)
            span = min(n - start_i, int(note_dur * self.sr))
            for j in range(span):
                lt = j / self.sr
                atk = min(1.0, lt / 0.005)
                env = atk * math.exp(-lt * 22.0)
                out[start_i + j] += math.sin(2 * math.pi * freq * lt) * env * 0.28
        return self._apply_edge_fade(out, fade_in_ms=3.0, fade_out_ms=18.0)

    def synth_news_bad(self) -> list[float]:
        dur = 0.28
        n = int(self.sr * dur)
        out = [0.0] * n
        phase = 0.0
        for i in range(n):
            t = i / self.sr
            cycle = int(t / 0.068) % 2
            freq = 440.0 if cycle == 0 else 369.99
            phase += 2 * math.pi * freq / self.sr
            env = math.sin(math.pi * min(1.0, t / dur))
            s = math.sin(phase) + 0.30 * math.sin(2 * phase)
            out[i] = s * env * 0.24
        return self._apply_edge_fade(out, fade_in_ms=5.0, fade_out_ms=20.0)

    def synth_glitch(self) -> list[float]:
        dur = 0.11
        n = int(self.sr * dur)
        rng = random.Random(54812)
        out = [0.0] * n
        freq = 1800.0
        phase = 0.0
        for i in range(n):
            if i % 220 == 0:
                freq = rng.uniform(900.0, 3200.0)
            phase += 2 * math.pi * freq / self.sr
            env = 1.0 if (i // 350) % 2 == 0 else 0.30
            s = math.sin(phase) + 0.35 * math.sin(3 * phase)
            out[i] = s * env * 0.18
        return self._apply_edge_fade(out, fade_in_ms=3.0, fade_out_ms=15.0)

    def build_all_encoded(self, channels: int, fmt_key: str) -> dict[str, list[tuple[array, bytes]]]:
        raw_map = {
            "key_tick": [
                self.synth_key_tick(0.95),
                self.synth_key_tick(1.00),
                self.synth_key_tick(1.05),
            ],
            "cooldown_block": [self.synth_cooldown_block()],
            "cmd_done": [self.synth_cmd_done()],
            "cooling_ok": [self.synth_cooling_ok()],
            "harvest": [self.synth_harvest(False)],
            "harvest_sync": [self.synth_harvest(True)],
            "upgrade_buy": [self.synth_upgrade_buy()],
            "story_unlock": [self.synth_story_unlock()],
            "news_good": [self.synth_news_good()],
            "news_bad": [self.synth_news_bad()],
            "glitch": [self.synth_glitch()],
        }
        return {
            k: [self._encode_pcm(s, channels, fmt_key) for s in v]
            for k, v in raw_map.items()
        }

    @staticmethod
    def _encode_pcm(samples: list[float], channels: int, fmt_key: str) -> tuple[array, bytes]:
        if fmt_key == "float":
            if channels == 1:
                arr = array("f", (max(-1.0, min(1.0, s)) for s in samples))
            else:
                buf = []
                for s in samples:
                    c = max(-1.0, min(1.0, s))
                    buf.extend([c] * channels)
                arr = array("f", buf)
            return arr, arr.tobytes()

        if fmt_key == "int32":
            scale = 2147483647
            if channels == 1:
                arr = array("i", (int(max(-1.0, min(1.0, s)) * scale) for s in samples))
            else:
                buf = []
                for s in samples:
                    v = int(max(-1.0, min(1.0, s)) * scale)
                    buf.extend([v] * channels)
                arr = array("i", buf)
            return arr, arr.tobytes()

        scale = 32767
        if channels == 1:
            arr = array("h", (int(max(-1.0, min(1.0, s)) * scale) for s in samples))
        else:
            buf = []
            for s in samples:
                v = int(max(-1.0, min(1.0, s)) * scale)
                buf.extend([v] * channels)
            arr = array("h", buf)
        return arr, arr.tobytes()


def _negotiate_audio_format(dev) -> tuple[QAudioFormat, int, int, str]:
    """장치 지원 포맷을 우선순위에 따라 안전하게 협상 (Int16 모노 -> Int16 스테레오 -> 장치 기본 포맷)"""
    candidates = [
        (44100, 1, QAudioFormat.SampleFormat.Int16, "int16"),
        (48000, 2, QAudioFormat.SampleFormat.Int16, "int16"),
        (44100, 2, QAudioFormat.SampleFormat.Int16, "int16"),
    ]
    if not dev.isNull():
        for sr, ch, qfmt, key in candidates:
            fmt = QAudioFormat()
            fmt.setSampleRate(sr)
            fmt.setChannelCount(ch)
            fmt.setSampleFormat(qfmt)
            if dev.isFormatSupported(fmt):
                return fmt, sr, ch, key

        pref = dev.preferredFormat()
        sf = pref.sampleFormat()
        if sf == QAudioFormat.SampleFormat.Float:
            key = "float"
        elif sf == QAudioFormat.SampleFormat.Int32:
            key = "int32"
        else:
            key = "int16"
            pref.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        sr = max(8000, pref.sampleRate())
        ch = max(1, min(2, pref.channelCount()))
        pref.setSampleRate(sr)
        pref.setChannelCount(ch)
        return pref, sr, ch, key

    fallback = QAudioFormat()
    fallback.setSampleRate(44100)
    fallback.setChannelCount(1)
    fallback.setSampleFormat(QAudioFormat.SampleFormat.Int16)
    return fallback, 44100, 1, "int16"


class _AudioMixerDevice(QIODevice):
    """락 경합을 최소화한 멀티포맷 상시 스트림 인메모리 PCM 믹서"""

    MAX_VOICES = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._voices: list[list] = []
        self._channels: int = 1
        self._fmt_key: str = "int16"
        self._sample_bytes: int = 2
        self._frame_bytes: int = 2
        self._avail_hint: int = 8192
        self._zero_buf: bytes = b"\x00" * 16384

    def configure_format(self, channels: int, fmt_key: str, buffer_bytes: int):
        sample_bytes = 2 if fmt_key == "int16" else 4
        with self._lock:
            self._voices.clear()
            self._channels = max(1, channels)
            self._fmt_key = fmt_key
            self._sample_bytes = sample_bytes
            self._frame_bytes = self._channels * sample_bytes
            self._avail_hint = max(4096, buffer_bytes)

    def isSequential(self) -> bool:
        return True

    def atEnd(self) -> bool:
        return False

    def bytesAvailable(self) -> int:
        return max(self._avail_hint, super().bytesAvailable())

    def enqueue_voice(self, samples_arr: array, raw_bytes: bytes):
        with self._lock:
            if len(self._voices) >= self.MAX_VOICES:
                self._voices.pop(0)
            self._voices.append([samples_arr, raw_bytes, 0])

    def clear_voices(self):
        with self._lock:
            self._voices.clear()

    def _silence(self, n_bytes: int) -> bytes:
        if n_bytes > len(self._zero_buf):
            self._zero_buf = b"\x00" * n_bytes
        return self._zero_buf[:n_bytes]

    def readData(self, maxlen: int) -> bytes:
        with self._lock:
            frame_bytes = self._frame_bytes
            sample_bytes = self._sample_bytes
            fmt_key = self._fmt_key

            n_bytes = maxlen - (maxlen % frame_bytes)
            if n_bytes <= 0:
                return b""

            if not self._voices:
                return self._silence(n_bytes)

            n_elems = n_bytes // sample_bytes

            # 단일 음원(대부분의 케이스): C 레벨 슬라이싱으로 즉시 반환
            if len(self._voices) == 1:
                arr, raw, pos = self._voices[0]
                b_start = pos * sample_bytes
                chunk = raw[b_start:b_start + n_bytes]
                new_pos = pos + n_elems
                if new_pos >= len(arr):
                    self._voices.clear()
                else:
                    self._voices[0][2] = new_pos
                if len(chunk) < n_bytes:
                    chunk = chunk + self._silence(n_bytes - len(chunk))
                return chunk

            # 다중 음원: 락 내부에서는 슬라이스만 꺼내고 실제 합산은 락 밖에서 처리
            slices = []
            survivors = []
            for v in self._voices:
                arr, raw, pos = v
                avail = len(arr) - pos
                take = n_elems if avail >= n_elems else avail
                slices.append(arr[pos:pos + take])
                new_pos = pos + take
                if new_pos < len(arr):
                    v[2] = new_pos
                    survivors.append(v)
            self._voices = survivors

        if fmt_key == "float":
            mix = [0.0] * n_elems
            for seg in slices:
                for i, val in enumerate(seg):
                    mix[i] += val
            out = array(
                "f",
                (1.0 if x > 1.0 else (-1.0 if x < -1.0 else x) for x in mix),
            )
            return out.tobytes()

        if fmt_key == "int32":
            mix = [0] * n_elems
            for seg in slices:
                for i, val in enumerate(seg):
                    mix[i] += val
            out = array(
                "i",
                (2147483647 if x > 2147483647 else (-2147483648 if x < -2147483648 else x) for x in mix),
            )
            return out.tobytes()

        mix = [0] * n_elems
        for seg in slices:
            for i, val in enumerate(seg):
                mix[i] += val
        out = array(
            "h",
            (32767 if x > 32767 else (-32768 if x < -32768 else x) for x in mix),
        )
        return out.tobytes()

    def writeData(self, data) -> int:
        return 0


class _AudioWorker(QObject):
    """전용 오디오 스레드에서 단일 QAudioSink와 포맷 동기화·오류 복구를 담당"""

    format_changed = pyqtSignal(int, int, str)

    def __init__(self, initial_volume: float, mixer: _AudioMixerDevice):
        super().__init__()
        self._volume = initial_volume
        self._mixer = mixer
        self._sink: QAudioSink | None = None
        self._media_devices: QMediaDevices | None = None
        self._current_sig: tuple[int, int, str] | None = None
        self._stopped_intentionally: bool = False

    @pyqtSlot()
    def start_engine(self):
        self._stopped_intentionally = False
        self._mixer.setParent(self)
        if not self._mixer.isOpen():
            self._mixer.open(QIODevice.OpenModeFlag.ReadOnly)

        self._media_devices = QMediaDevices(self)
        self._media_devices.audioOutputsChanged.connect(self.restart_sink)
        self._open_sink()

    def _open_sink(self):
        self._close_sink()
        if self._stopped_intentionally:
            return
        try:
            dev = QMediaDevices.defaultAudioOutput()
            if dev.isNull():
                return

            fmt, sr, ch, fmt_key = _negotiate_audio_format(dev)
            sample_bytes = 2 if fmt_key == "int16" else 4
            frame_bytes = ch * sample_bytes
            bytes_per_sec = sr * frame_bytes

            # 약 85ms 분량 버퍼로 GIL 지연·UI 갱신 중에도 WASAPI 언더런 방지
            raw_buf = int(bytes_per_sec * 0.085)
            buf_bytes = max(8192, (raw_buf // frame_bytes) * frame_bytes)

            self._mixer.configure_format(ch, fmt_key, buf_bytes)

            sig = (sr, ch, fmt_key)
            if self._current_sig != sig:
                self._current_sig = sig
                self.format_changed.emit(sr, ch, fmt_key)

            sink = QAudioSink(dev, fmt, self)
            sink.setBufferSize(buf_bytes)
            sink.setVolume(self._volume)
            sink.stateChanged.connect(self._on_sink_state_changed)
            sink.start(self._mixer)
            self._sink = sink
        except Exception:
            self._sink = None

    def _on_sink_state_changed(self, state):
        if self._stopped_intentionally or self._sink is None:
            return
        if state == QAudio.State.StoppedState and self._sink.error() != QAudio.Error.NoError:
            QTimer.singleShot(180, self.restart_sink)

    def _close_sink(self):
        if self._sink is not None:
            try:
                self._sink.stateChanged.disconnect(self._on_sink_state_changed)
            except Exception:
                pass
            try:
                self._sink.stop()
                self._sink.deleteLater()
            except Exception:
                pass
            self._sink = None

    @pyqtSlot()
    def restart_sink(self):
        if self._stopped_intentionally:
            return
        self._mixer.clear_voices()
        self._open_sink()

    @pyqtSlot(float)
    def apply_volume(self, vol: float):
        self._volume = max(0.0, min(1.0, float(vol)))
        if self._sink is not None:
            self._sink.setVolume(self._volume)

    @pyqtSlot()
    def stop_engine(self):
        self._stopped_intentionally = True
        self._close_sink()
        self._mixer.clear_voices()
        if self._mixer.isOpen():
            self._mixer.close()


class SoundManager(QObject):
    """전용 QThread + 단일 QAudioSink 멀티포맷 인메모리 믹서 기반 무끊김 합성 SFX 매니저"""

    MIN_INTERVAL_SEC = 0.040

    _sig_set_volume = pyqtSignal(float)
    _sig_stop_engine = pyqtSignal()

    def __init__(self, settings_dir: str = "saves", parent=None):
        super().__init__(parent)
        self.settings_dir = settings_dir
        self.settings_path = os.path.join(settings_dir, "audio_settings.json")

        self.muted: bool = False
        self.volume: float = 0.65
        self._load_settings()

        self._buf_lock = threading.Lock()
        self._buffers: dict[str, list[tuple[array, bytes]]] = {}
        self._variant_idx: dict[str, int] = {}
        self._last_play_time: dict[str, float] = {}
        self._is_shutdown: bool = False
        self._built_sig: tuple[int, int, str] | None = None

        # 기본 장치 포맷에 맞춰 초기 PCM 버퍼 합성
        default_dev = QMediaDevices.defaultAudioOutput()
        _, init_sr, init_ch, init_fmt_key = _negotiate_audio_format(default_dev)
        self._rebuild_buffers(init_sr, init_ch, init_fmt_key)

        # 오디오 엔진을 별도 스레드로 완전 격리
        self._mixer = _AudioMixerDevice()
        self._thread = QThread(self)
        eff_vol = 0.0 if self.muted else self.volume
        self._worker = _AudioWorker(eff_vol, self._mixer)
        self._worker.moveToThread(self._thread)
        self._mixer.moveToThread(self._thread)

        self._thread.started.connect(self._worker.start_engine)
        self._worker.format_changed.connect(self._on_worker_format_changed, Qt.ConnectionType.QueuedConnection)
        self._sig_set_volume.connect(self._worker.apply_volume, Qt.ConnectionType.QueuedConnection)
        self._sig_stop_engine.connect(self._worker.stop_engine, Qt.ConnectionType.QueuedConnection)
        self._thread.start()

        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown)

    def _rebuild_buffers(self, sr: int, channels: int, fmt_key: str):
        sig = (sr, channels, fmt_key)
        if self._built_sig == sig:
            return
        synth = _WaveformSynthesizer(sr)
        encoded = synth.build_all_encoded(channels, fmt_key)
        with self._buf_lock:
            self._buffers = encoded
            for k in encoded:
                self._variant_idx.setdefault(k, 0)
            self._built_sig = sig

    @pyqtSlot(int, int, str)
    def _on_worker_format_changed(self, sr: int, channels: int, fmt_key: str):
        self._rebuild_buffers(sr, channels, fmt_key)

    def shutdown(self):
        if self._is_shutdown:
            return
        self._is_shutdown = True
        try:
            self._sig_stop_engine.emit()
            self._thread.quit()
            self._thread.wait(800)
        except Exception:
            pass

    # ---------------- 설정 로드 / 저장 ----------------
    def _load_settings(self):
        if not os.path.exists(self.settings_path):
            return
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self.muted = bool(data.get("muted", False))
                vol = float(data.get("volume", 0.65))
                self.volume = max(0.0, min(1.0, vol))
        except Exception:
            pass

    def save_settings(self):
        try:
            os.makedirs(self.settings_dir, exist_ok=True)
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(
                    {"muted": self.muted, "volume": round(self.volume, 3)},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception:
            pass

    def set_volume(self, vol: float):
        self.volume = max(0.0, min(1.0, float(vol)))
        self._sig_set_volume.emit(0.0 if self.muted else self.volume)
        self.save_settings()

    def set_muted(self, muted: bool):
        self.muted = bool(muted)
        self._sig_set_volume.emit(0.0 if self.muted else self.volume)
        self.save_settings()

    def play(self, key: str):
        if self._is_shutdown or self.muted or self.volume <= 0.001:
            return

        now = time.monotonic()
        if (now - self._last_play_time.get(key, 0.0)) < self.MIN_INTERVAL_SEC:
            return
        self._last_play_time[key] = now

        with self._buf_lock:
            variants = self._buffers.get(key)
            if not variants:
                return
            idx = self._variant_idx[key] % len(variants)
            self._variant_idx[key] = idx + 1
            arr, raw = variants[idx]

        self._mixer.enqueue_voice(arr, raw)