import os
import json
import base64
import shutil
from datetime import datetime


class SaveManager:
    """세이브 데이터 영속성, 자동 백업(.bak), 분기 슬롯 및 Base64 인코딩 관리 클래스"""

    def __init__(self, save_dir: str = "saves"):
        self.save_dir = save_dir
        self.autosave_path = os.path.join(self.save_dir, "autosave.json")
        self.backup_path = os.path.join(self.save_dir, "autosave.bak")
        self.last_saved_time: str = "저장 기록 없음"
        self._ensure_save_dir()

    def _ensure_save_dir(self) -> bool:
        try:
            os.makedirs(self.save_dir, exist_ok=True)
            return True
        except PermissionError:
            return False

    def set_save_directory(self, new_dir: str) -> bool:
        """쓰기 권한 부족 시 사용자가 선택한 경로로 저장 폴더 변경 (계획서 2.5.3절)"""
        self.save_dir = new_dir
        self.autosave_path = os.path.join(self.save_dir, "autosave.json")
        self.backup_path = os.path.join(self.save_dir, "autosave.bak")
        return self._ensure_save_dir()

    def save_auto(self, state_dict: dict) -> tuple[bool, str]:
        """
        자동/수동 메인 저장 수행.
        기존 정상 세이브 파일이 존재하면 .bak 백업본으로 먼저 복사해 손상에 대비함.
        """
        try:
            if not self._ensure_save_dir():
                return False, "PERMISSION_ERROR"

            # 기존 세이브 파일이 유효한 JSON인지 확인 후 백업 파일로 복사
            if os.path.exists(self.autosave_path):
                try:
                    with open(self.autosave_path, "r", encoding="utf-8") as f:
                        json.load(f)
                    shutil.copy2(self.autosave_path, self.backup_path)
                except Exception:
                    # 기존 파일이 이미 깨져 있다면 백업본을 덮어쓰지 않고 보존
                    pass

            with open(self.autosave_path, "w", encoding="utf-8") as f:
                json.dump(state_dict, f, ensure_ascii=False, indent=2)

            self.last_saved_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return True, f"저장 완료 ({self.last_saved_time})"

        except PermissionError:
            return False, "PERMISSION_ERROR"
        except Exception as e:
            return False, f"저장 중 오류 발생: {e}"

    def load_auto(self) -> tuple[str, dict | None]:
        """
        메인 세이브 파일 로드. 손상 시 백업 파일(.bak)에서 자동 복구 시도 (계획서 2.5.3절).
        반환 상태 코드: 'NO_SAVE' | 'SUCCESS' | 'RECOVERED_FROM_BACKUP' | 'CORRUPTED_ALL'
        """
        has_main = os.path.exists(self.autosave_path)
        has_bak = os.path.exists(self.backup_path)

        if not has_main and not has_bak:
            return "NO_SAVE", None

        # 1. 메인 세이브 파일 로드 시도
        if has_main:
            try:
                with open(self.autosave_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if self._validate_state_dict(data):
                    return "SUCCESS", data
            except Exception:
                pass

        # 2. 메인 파일이 없거나 손상된 경우 백업 파일(.bak) 로드 시도
        if has_bak:
            try:
                with open(self.backup_path, "r", encoding="utf-8") as f:
                    bak_data = json.load(f)
                if self._validate_state_dict(bak_data):
                    # 복구된 데이터로 메인 파일 덮어쓰기 복원
                    shutil.copy2(self.backup_path, self.autosave_path)
                    return "RECOVERED_FROM_BACKUP", bak_data
            except Exception:
                pass

        # 3. 메인/백업 모두 손상된 경우 초기화 안내 대상
        return "CORRUPTED_ALL", None

    def save_branch(self, slot_num: int, state_dict: dict) -> tuple[bool, str]:
        """엔딩 분기 전 시점 저장을 위한 분기 슬롯 저장 (계획서 2.2.4절)"""
        try:
            if not self._ensure_save_dir():
                return False, "PERMISSION_ERROR"

            branch_data = {
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "bench_score": state_dict.get("specs", {}).get("BENCH_SCORE", 0),
                "tokens": state_dict.get("tokens", 0),
                "state": state_dict
            }
            path = os.path.join(self.save_dir, f"branch_slot_{slot_num}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(branch_data, f, ensure_ascii=False, indent=2)
            return True, f"분기 슬롯 {slot_num}에 저장되었습니다."
        except PermissionError:
            return False, "PERMISSION_ERROR"
        except Exception as e:
            return False, f"분기 저장 실패: {e}"

    def load_branch(self, slot_num: int) -> tuple[bool, dict | str]:
        """분기 슬롯 데이터 불러오기"""
        path = os.path.join(self.save_dir, f"branch_slot_{slot_num}.json")
        if not os.path.exists(path):
            return False, "해당 슬롯에 저장된 분기 데이터가 없습니다."
        try:
            with open(path, "r", encoding="utf-8") as f:
                branch_data = json.load(f)
            state = branch_data.get("state")
            if not self._validate_state_dict(state):
                return False, "분기 세이브 파일이 손상되었습니다."
            return True, state
        except Exception as e:
            return False, f"분기 로드 실패: {e}"

    def get_branch_info(self, slot_num: int) -> str:
        """슬롯 요약 정보 문자열 반환"""
        path = os.path.join(self.save_dir, f"branch_slot_{slot_num}.json")
        if not os.path.exists(path):
            return "비어 있음"
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            saved_at = data.get("saved_at", "알 수 없음")
            bench = int(data.get("bench_score", 0))
            return f"{saved_at} (BENCH: {bench:,})"
        except Exception:
            return "파일 손상됨"

    def export_base64(self, state_dict: dict) -> str:
        """현재 게임 상태를 Base64 문자열로 인코딩하여 반환 (계획서 3.5절)"""
        raw_json = json.dumps(state_dict, ensure_ascii=False, separators=(",", ":"))
        encoded_bytes = base64.b64encode(raw_json.encode("utf-8"))
        return encoded_bytes.decode("ascii")

    def import_base64(self, b64_str: str) -> tuple[bool, dict | str]:
        """Base64 문자열을 디코딩 및 검증하여 상태 딕셔너리 반환"""
        cleaned = b64_str.strip()
        if not cleaned:
            return False, "입력된 Base64 코드가 비어 있습니다."
        try:
            decoded_bytes = base64.b64decode(cleaned.encode("ascii"), validate=True)
            data = json.loads(decoded_bytes.decode("utf-8"))
            if not self._validate_state_dict(data):
                return False, "올바른 AI 키우기 세이브 데이터 형식이 아닙니다."
            return True, data
        except Exception:
            return False, "유효하지 않거나 손상된 Base64 세이브 코드입니다."

    def clear_all_saves(self):
        """초기화 시 자동 저장 및 백업 파일 삭제"""
        for path in (self.autosave_path, self.backup_path):
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

    def _validate_state_dict(self, data: dict) -> bool:
        if not isinstance(data, dict):
            return False
        required_keys = {"tokens", "tokens_per_command", "tokens_per_sec", "specs", "purchased_upgrades"}
        return required_keys.issubset(data.keys())