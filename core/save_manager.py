import os
import json
import shutil
import base64
from datetime import datetime


class SaveManager:
    """자동 저장, 직전 백업(.bak) 복구, 분기 슬롯(1~3), Base64 내보내기/불러오기 및 영구 엔딩 기록 관리"""

    def __init__(self, save_dir: str = "saves"):
        self.save_dir = save_dir
        self.last_saved_time = "저장 기록 없음"
        self._ensure_dir()

    def _ensure_dir(self) -> bool:
        try:
            os.makedirs(self.save_dir, exist_ok=True)
            return True
        except PermissionError:
            return False
        except OSError:
            return False

    def set_save_directory(self, new_dir: str) -> bool:
        old_dir = self.save_dir
        self.save_dir = new_dir
        if self._ensure_dir():
            return True
        self.save_dir = old_dir
        return False

    @property
    def auto_path(self) -> str:
        return os.path.join(self.save_dir, "autosave.json")

    @property
    def backup_path(self) -> str:
        return os.path.join(self.save_dir, "autosave.json.bak")

    @property
    def meta_endings_path(self) -> str:
        return os.path.join(self.save_dir, "meta_endings.json")

    def branch_path(self, slot: int) -> str:
        return os.path.join(self.save_dir, f"branch_slot_{slot}.json")

    # ---------------- 영구 엔딩 메타 기록 관리 ----------------
    def load_unlocked_endings(self) -> list[str]:
        """초기화나 분기 로드 후에도 유지되는 영구 엔딩 달성 목록 로드"""
        if not os.path.exists(self.meta_endings_path):
            return []
        try:
            with open(self.meta_endings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("unlocked_endings"), list):
                return [str(x) for x in data["unlocked_endings"]]
        except Exception:
            pass
        return []

    def save_unlocked_endings(self, ending_ids: list[str]) -> bool:
        if not self._ensure_dir():
            return False
        try:
            unique_sorted = sorted(set(str(x) for x in ending_ids))
            with open(self.meta_endings_path, "w", encoding="utf-8") as f:
                json.dump({"unlocked_endings": unique_sorted}, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    # ---------------- 자동 저장 & 백업 ----------------
    def save_auto(self, state_dict: dict) -> tuple[bool, str]:
        if not self._ensure_dir():
            return False, "PERMISSION_ERROR"

        try:
            if os.path.exists(self.auto_path):
                try:
                    with open(self.auto_path, "r", encoding="utf-8") as f:
                        json.load(f)
                    shutil.copy2(self.auto_path, self.backup_path)
                except Exception:
                    pass

            tmp_path = self.auto_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state_dict, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.auto_path)

            if isinstance(state_dict.get("unlocked_endings"), list):
                merged = set(self.load_unlocked_endings()) | set(state_dict["unlocked_endings"])
                self.save_unlocked_endings(list(merged))

            self.last_saved_time = datetime.now().strftime("%H:%M:%S")
            return True, f"자동 저장 완료 ({self.last_saved_time})"
        except PermissionError:
            return False, "PERMISSION_ERROR"
        except Exception as e:
            return False, f"저장 실패: {e}"

    def load_auto(self) -> tuple[str, dict | None]:
        """반환값: ('SUCCESS'|'RECOVERED_FROM_BACKUP'|'CORRUPTED_ALL'|'NO_SAVE', data)"""
        has_main = os.path.exists(self.auto_path)
        has_bak = os.path.exists(self.backup_path)

        if not has_main and not has_bak:
            return "NO_SAVE", None

        if has_main:
            try:
                with open(self.auto_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and "tokens" in data:
                    return "SUCCESS", data
            except Exception:
                pass

        if has_bak:
            try:
                with open(self.backup_path, "r", encoding="utf-8") as f:
                    bak_data = json.load(f)
                if isinstance(bak_data, dict) and "tokens" in bak_data:
                    shutil.copy2(self.backup_path, self.auto_path)
                    return "RECOVERED_FROM_BACKUP", bak_data
            except Exception:
                pass

        return "CORRUPTED_ALL", None

    # ---------------- 분기 저장 슬롯 (1~3) ----------------
    def save_branch(self, slot: int, state_dict: dict) -> tuple[bool, str]:
        if not self._ensure_dir():
            return False, "PERMISSION_ERROR"
        try:
            payload = dict(state_dict)
            payload["branch_saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.branch_path(slot), "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return True, f"분기 슬롯 {slot}에 저장되었습니다."
        except PermissionError:
            return False, "PERMISSION_ERROR"
        except Exception as e:
            return False, f"분기 저장 실패: {e}"

    def load_branch(self, slot: int) -> tuple[bool, dict | str]:
        path = self.branch_path(slot)
        if not os.path.exists(path):
            return False, f"분기 슬롯 {slot}에 저장된 데이터가 없습니다."
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "tokens" in data:
                return True, data
            return False, "분기 세이브 파일 형식이 올바르지 않습니다."
        except Exception as e:
            return False, f"분기 파일 손상으로 불러올 수 없습니다: {e}"

    def get_branch_info(self, slot: int) -> str:
        path = self.branch_path(slot)
        if not os.path.exists(path):
            return "비어 있음"
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            saved_at = data.get("branch_saved_at", "시간 미상")
            tokens = int(data.get("tokens", 0))
            return f"{saved_at} (보유: {tokens:,} Token)"
        except Exception:
            return "손상된 데이터"

    # ---------------- Base64 코드 변환 ----------------
    def export_base64(self, state_dict: dict) -> str:
        raw_json = json.dumps(state_dict, ensure_ascii=False).encode("utf-8")
        return base64.b64encode(raw_json).decode("ascii")

    def import_base64(self, b64_str: str) -> tuple[bool, dict | str]:
        try:
            cleaned = b64_str.strip()
            if not cleaned:
                return False, "입력된 코드가 비어 있습니다."
            raw_bytes = base64.b64decode(cleaned.encode("ascii"))
            data = json.loads(raw_bytes.decode("utf-8"))
            if not isinstance(data, dict) or "tokens" not in data:
                return False, "유효한 세이브 데이터 구조가 아닙니다."
            return True, data
        except Exception:
            return False, "잘못되었거나 손상된 Base64 세이브 코드입니다."

    def clear_all_saves(self):
        for p in (self.auto_path, self.backup_path):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass