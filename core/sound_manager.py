import os
import json
import math
import wave
import struct
import random
import tempfile
from PyQt6.QtCore import QObject, QUrl
from PyQt6.QtMultimedia import QSoundEffect


class SoundManager(QObject):
    """Python 표준 wave/math로 PCM WAV를 합성하고 QSoundEffect 풀로 초저지연 재생하는 오디오 매니저"""

    SAMPLE_RATE = 44100

    def __init__(self, settings_dir: str = "saves", parent=None):
        super().__init__(parent)
        self.settings_dir = settings_dir
        self.settings_path = os.path.join(settings_dir, "audio_settings.json")
        self.cache_dir = os.path.join(tempfile.gettempdir(), "ai_tycoon_sfx_v1")
        os.makedirs(self.cache_dir, exist_ok=True)

        self.muted: bool = False
        self.volume: float = 0.65  # 0.0 ~ 1.0
        self._load_settings()

        # 효과음별 QSoundEffect 풀 (연타가 잦은 키는 다중 슬롯 할당)
        self._pools: dict[str, list[QSoundEffect]] = {}
        self._pool_idx: dict[str, int] = {}

        self._init_all_sounds()

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
        self._sync_pool_volumes()
        self.save_settings()

    def set_muted(self, muted: bool):
        self.muted = bool(muted)
        self._sync_pool_volumes()
        self.save_settings()

    def _sync_pool_volumes(self):
        eff_vol = 0.0 if self.muted else self.volume
        for effects in self._pools.values():
            for fx in effects:
                fx.setVolume(eff_vol)

    # ---------------- PCM 파형 합성 헬퍼 ----------------
    def _write_wav(self, filename: str, samples: list[float]) -> str:
        path = os.path.join(self.cache_dir, filename)
        with wave.open(path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.SAMPLE_RATE)
            raw = bytearray()
            for s in samples:
                clamped = max(-1.0, min(1.0, s))
                raw.extend(struct.pack("<h", int(clamped * 32767)))
            wf.writeframes(bytes(raw))
        return path

    def _synth_key_tick(self, pitch_mult: float = 1.0) -> list[float]:
        """저소음 묵직한 자석축/택타일 타건음 (18ms 댐핑 펄스 + 로우패스 노이즈)"""
        dur = 0.020
        n = int(self.SAMPLE_RATE * dur)
        out = []
        rng = random.Random(int(pitch_mult * 1000))
        prev_noise = 0.0
        for i in range(n):
            t = i / self.SAMPLE_RATE
            env = math.exp(-t * 210.0)
            body = math.sin(2 * math.pi * (240.0 * pitch_mult) * t) * 0.65
            sub = math.sin(2 * math.pi * (115.0 * pitch_mult) * t) * 0.45
            white = rng.uniform(-1.0, 1.0)
            prev_noise = 0.72 * prev_noise + 0.28 * white
            out.append((body + sub + prev_noise * 0.35) * env * 0.55)
        return out

    def _synth_cooldown_block(self) -> list[float]:
        """쿨다운 차단 / 입력 잠금 알림음 (150Hz -> 105Hz 짧은 펄스)"""
        dur = 0.075
        n = int(self.SAMPLE_RATE * dur)
        out = []
        for i in range(n):
            t = i / self.SAMPLE_RATE
            env = math.exp(-t * 38.0)
            freq = 150.0 if t < 0.035 else 105.0
            wave_val = 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0
            out.append(wave_val * env * 0.22)
        return out

    def _synth_cmd_done(self) -> list[float]:
        """명령어 완료 승인 차임 (C5 -> G5 2연음)"""
        dur = 0.12
        n = int(self.SAMPLE_RATE * dur)
        out = []
        for i in range(n):
            t = i / self.SAMPLE_RATE
            if t < 0.055:
                freq = 523.25
                local_t = t
            else:
                freq = 783.99
                local_t = t - 0.055
            env = math.exp(-local_t * 34.0)
            s = math.sin(2 * math.pi * freq * local_t) + 0.3 * math.sin(4 * math.pi * freq * local_t)
            out.append(s * env * 0.32)
        return out

    def _synth_cooling_ok(self) -> list[float]:
        """Q/W/E 병목 냉각 에어 벤트 + 확인 핑"""
        dur = 0.16
        n = int(self.SAMPLE_RATE * dur)
        out = []
        rng = random.Random(42)
        lp = 0.0
        for i in range(n):
            t = i / self.SAMPLE_RATE
            noise_env = math.exp(-t * 28.0)
            lp = 0.65 * lp + 0.35 * rng.uniform(-1.0, 1.0)
            ping_env = math.exp(-t * 24.0)
            ping = math.sin(2 * math.pi * 880.0 * t)
            out.append((lp * noise_env * 0.45 + ping * ping_env * 0.45) * 0.42)
        return out

    def _synth_harvest(self, synced: bool = False) -> list[float]:
        """그래디언트 버퍼 일괄 수확 에너지 방전 스윕"""
        dur = 0.24 if synced else 0.19
        n = int(self.SAMPLE_RATE * dur)
        out = []
        notes = [329.63, 493.88, 659.25, 987.77] if synced else [329.63, 493.88, 659.25]
        step_dur = dur / len(notes)
        for i in range(n):
            t = i / self.SAMPLE_RATE
            idx = min(len(notes) - 1, int(t / step_dur))
            local_t = t - idx * step_dur
            freq = notes[idx]
            env = math.exp(-local_t * 18.0) * (1.0 - (t / dur) * 0.35)
            s = math.sin(2 * math.pi * freq * t) + 0.25 * math.sin(2 * math.pi * (freq * 1.5) * t)
            out.append(s * env * 0.38)
        return out

    def _synth_upgrade_buy(self) -> list[float]:
        """업그레이드 노드 회로 결선 클릭 + 화음"""
        dur = 0.16
        n = int(self.SAMPLE_RATE * dur)
        out = []
        for i in range(n):
            t = i / self.SAMPLE_RATE
            click = math.sin(2 * math.pi * 1400.0 * t) * math.exp(-t * 160.0)
            chord_env = math.exp(-t * 22.0)
            chord = (
                math.sin(2 * math.pi * 440.0 * t) * 0.5
                + math.sin(2 * math.pi * 659.25 * t) * 0.4
            ) * chord_env
            out.append((click * 0.5 + chord * 0.5) * 0.38)
        return out

    def _synth_story_unlock(self) -> list[float]:
        """스토리/도감 해금 다크 신스 5연음 아르페지오"""
        dur = 0.46
        n = int(self.SAMPLE_RATE * dur)
        notes = [261.63, 329.63, 392.00, 493.88, 587.33]
        step = 0.075
        out = []
        for i in range(n):
            t = i / self.SAMPLE_RATE
            val = 0.0
            for idx, freq in enumerate(notes):
                start = idx * step
                if t >= start:
                    lt = t - start
                    env = math.exp(-lt * 8.5)
                    val += math.sin(2 * math.pi * freq * lt) * env * 0.28
            out.append(val * 0.55)
        return out

    def _synth_news_good(self) -> list[float]:
        """호재 뉴스 텔레타입 알림음"""
        dur = 0.18
        n = int(self.SAMPLE_RATE * dur)
        out = []
        for i in range(n):
            t = i / self.SAMPLE_RATE
            freq = 659.25 if t < 0.085 else 880.0
            lt = t if t < 0.085 else (t - 0.085)
            env = math.exp(-lt * 24.0)
            out.append(math.sin(2 * math.pi * freq * lt) * env * 0.32)
        return out

    def _synth_news_bad(self) -> list[float]:
        """악재 뉴스 / QWE 동시 과부하 경보 사이렌"""
        dur = 0.28
        n = int(self.SAMPLE_RATE * dur)
        out = []
        for i in range(n):
            t = i / self.SAMPLE_RATE
            cycle = int(t / 0.07) % 2
            freq = 440.0 if cycle == 0 else 369.99
            env = math.sin(math.pi * min(1.0, t / dur))
            s = math.sin(2 * math.pi * freq * t) + 0.35 * math.sin(2 * math.pi * (freq * 2) * t)
            out.append(s * env * 0.28)
        return out

    def _synth_glitch(self) -> list[float]:
        """특이점 진입 및 글리치 버튼 점멸 디지털 노이즈"""
        dur = 0.10
        n = int(self.SAMPLE_RATE * dur)
        rng = random.Random(54812)
        out = []
        freq = 1800.0
        for i in range(n):
            t = i / self.SAMPLE_RATE
            if i % 180 == 0:
                freq = rng.uniform(900.0, 3400.0)
            env = 1.0 if (i // 300) % 2 == 0 else 0.25
            s = 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0
            out.append(s * env * 0.22)
        return out

    # ---------------- 사운드 풀 등록 및 재생 ----------------
    def _register_sound(self, key: str, wav_paths: list[str], pool_size: int = 2):
        effects: list[QSoundEffect] = []
        eff_vol = 0.0 if self.muted else self.volume
        for i in range(pool_size):
            path = wav_paths[i % len(wav_paths)]
            fx = QSoundEffect(self)
            fx.setSource(QUrl.fromLocalFile(path))
            fx.setVolume(eff_vol)
            effects.append(fx)
        self._pools[key] = effects
        self._pool_idx[key] = 0

    def _init_all_sounds(self):
        tick_paths = [
            self._write_wav("key_tick_0.wav", self._synth_key_tick(0.95)),
            self._write_wav("key_tick_1.wav", self._synth_key_tick(1.00)),
            self._write_wav("key_tick_2.wav", self._synth_key_tick(1.05)),
        ]
        self._register_sound("key_tick", tick_paths, pool_size=4)
        self._register_sound("cooldown_block", [self._write_wav("cooldown.wav", self._synth_cooldown_block())], pool_size=2)
        self._register_sound("cmd_done", [self._write_wav("cmd_done.wav", self._synth_cmd_done())], pool_size=2)
        self._register_sound("cooling_ok", [self._write_wav("cooling.wav", self._synth_cooling_ok())], pool_size=3)
        self._register_sound("harvest", [self._write_wav("harvest.wav", self._synth_harvest(False))], pool_size=2)
        self._register_sound("harvest_sync", [self._write_wav("harvest_sync.wav", self._synth_harvest(True))], pool_size=2)
        self._register_sound("upgrade_buy", [self._write_wav("upgrade.wav", self._synth_upgrade_buy())], pool_size=2)
        self._register_sound("story_unlock", [self._write_wav("story.wav", self._synth_story_unlock())], pool_size=2)
        self._register_sound("news_good", [self._write_wav("news_good.wav", self._synth_news_good())], pool_size=2)
        self._register_sound("news_bad", [self._write_wav("news_bad.wav", self._synth_news_bad())], pool_size=2)
        self._register_sound("glitch", [self._write_wav("glitch.wav", self._synth_glitch())], pool_size=2)

    def play(self, key: str):
        if self.muted or self.volume <= 0.001:
            return
        pool = self._pools.get(key)
        if not pool:
            return
        idx = self._pool_idx[key] % len(pool)
        self._pool_idx[key] = idx + 1
        fx = pool[idx]
        if fx.isPlaying():
            fx.stop()
        fx.play()