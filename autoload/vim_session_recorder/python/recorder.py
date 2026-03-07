"""Session recording backend for vim-session-recorder plugin."""

import os
import sys
import yaml
import uuid
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Tuple


class SessionRecorder:
    def __init__(self, record_dir: str):
        self.record_dir = Path(record_dir)
        self.session_dir: Optional[Path] = None
        self.files: list[dict[str, Any]] = []

    def create_session_dir(self, start_time: str, first_file: str, uuid_length: int = 8) -> str:
        time_str = start_time
        unique_id = uuid.uuid4().hex[:uuid_length]
        
        if first_file:
            base_name = Path(first_file).stem[:20]
            dir_name = f"{time_str}_{base_name}_{unique_id}"
        else:
            dir_name = f"{time_str}_{unique_id}"
        
        session_path = self.record_dir / dir_name
        session_path.mkdir(parents=True, exist_ok=True)
        
        return str(session_path)

    def rename_session_dir(self, old_dir: str, start_time: str, first_file: str, uuid_length: int = 8) -> str:
        old_path = Path(old_dir)
        if not old_path.exists():
            return old_dir
        
        time_str = start_time
        unique_id = uuid.uuid4().hex[:uuid_length]
        base_name = Path(first_file).stem[:20]
        new_dir_name = f"{time_str}_{base_name}_{unique_id}"
        new_path = self.record_dir / new_dir_name
        
        try:
            old_path.rename(new_path)
            return str(new_path)
        except Exception:
            return old_dir

    def is_binary_file(self, filepath: Path) -> bool:
        if not filepath.exists():
            return True
        
        try:
            with open(filepath, 'rb') as f:
                chunk = f.read(8192)
            chunk.decode('utf-8')
            return False
        except UnicodeDecodeError:
            return True
        except Exception:
            return True

    def get_file_size(self, filepath: Path) -> int:
        if not filepath.exists():
            return 0
        return filepath.stat().st_size

    def should_copy_original(self, filepath: Path, max_size: int = 1048576) -> bool:
        if not filepath.exists():
            return False
        
        if self.get_file_size(filepath) >= max_size:
            return False
        
        if self.is_binary_file(filepath):
            return False
        
        return True

    def copy_original(self, src: Path, file_id: int, dest_dir: Path) -> Optional[str]:
        if not src.exists():
            return None
        
        ext = src.suffix
        dest_filename = f"{file_id}-original{ext}"
        dest_path = dest_dir / dest_filename
        
        try:
            import shutil
            shutil.copy2(src, dest_path)
            return dest_filename
        except Exception:
            return None

    def generate_diff(self, original_path: str, current_path: str, output_path: str) -> Tuple[bool, int, int]:
        try:
            original = Path(original_path)
            current = Path(current_path)
            
            if not original.exists():
                return (False, 0, 0)
            
            if not current.exists():
                with open(original_path, 'r') as f:
                    original_lines = f.readlines()
                lines_deleted = len(original_lines)
                
                with open(output_path, 'w') as f:
                    f.write(f"--- {original_path}\n")
                    f.write(f"+++ /dev/null\n")
                    for line in original_lines:
                        f.write(f"-{line}")
                return (True, 0, lines_deleted)
            
            result = subprocess.run(
                ['diff', '-u', str(original_path), str(current_path)],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                with open(output_path, 'w') as f:
                    f.write('')
                return (True, 0, 0)
            elif result.returncode == 1:
                with open(output_path, 'w') as f:
                    f.write(result.stdout)
                
                lines_added, lines_deleted = self.parse_diff_stats(result.stdout)
                return (True, lines_added, lines_deleted)
            else:
                return (False, 0, 0)
                
        except Exception:
            return (False, 0, 0)

    def parse_diff_stats(self, diff_content: str) -> Tuple[int, int]:
        lines_added = 0
        lines_deleted = 0
        
        for line in diff_content.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                lines_added += 1
            elif line.startswith('-') and not line.startswith('---'):
                lines_deleted += 1
        
        return lines_added, lines_deleted

    def get_file_info(self, filepath: Path) -> Dict[str, Any]:
        if not filepath.exists():
            return {'exists': False, 'size': 0, 'is_binary': False, 'is_symlink': False}
        
        return {
            'exists': True,
            'size': self.get_file_size(filepath),
            'is_binary': self.is_binary_file(filepath),
            'is_symlink': filepath.is_symlink(),
        }

    def write_record_yaml(self, session_dir: str, session_data: Dict[str, Any]) -> bool:
        try:
            record_path = Path(session_dir) / 'record.yaml'
            with open(record_path, 'w') as f:
                yaml.dump(session_data, f, default_flow_style=False, sort_keys=False)
            return True
        except Exception:
            return False


def generate_uuid() -> str:
    return uuid.uuid4().hex


def get_current_timestamp() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def get_dirname_timestamp() -> str:
    return datetime.now().strftime('%Y-%m-%d-%H-%M-%S')


_recorder: Optional[SessionRecorder] = None


def init_recorder(record_dir: str) -> bool:
    global _recorder
    try:
        _recorder = SessionRecorder(record_dir)
        return True
    except Exception:
        return False


def create_session_dir(record_dir: str, start_time: str, first_file: str, uuid_length: int = 8) -> str:
    global _recorder
    if _recorder is None:
        _recorder = SessionRecorder(record_dir)
    return _recorder.create_session_dir(start_time, first_file, uuid_length)


def rename_session_dir(old_dir: str, start_time: str, first_file: str, uuid_length: int = 8) -> str:
    global _recorder
    if _recorder is None:
        return old_dir
    return _recorder.rename_session_dir(old_dir, start_time, first_file, uuid_length)


def get_file_info_vim(filepath: str) -> Dict[str, Any]:
    global _recorder
    if _recorder is None:
        recorder = SessionRecorder('/tmp')
    else:
        recorder = _recorder
    
    info = recorder.get_file_info(Path(filepath))
    return {
        'exists': 1 if info['exists'] else 0,
        'size': info['size'],
        'is_binary': 1 if info['is_binary'] else 0,
    }


def copy_original_vim(src: str, file_id: int, dest_dir: str) -> str:
    global _recorder
    if _recorder is None:
        return ''
    
    result = _recorder.copy_original(Path(src), file_id, Path(dest_dir))
    return result if result else ''


def generate_diff_vim(original_path: str, current_path: str, output_path: str) -> Dict[str, Any]:
    global _recorder
    if _recorder is None:
        return {'success': False, 'lines_added': 0, 'lines_deleted': 0}
    
    success, lines_added, lines_deleted = _recorder.generate_diff(original_path, current_path, output_path)
    return {'success': success, 'lines_added': lines_added, 'lines_deleted': lines_deleted}


def write_record_yaml_vim(session_dir: str, session_data: Dict[str, Any]) -> bool:
    global _recorder
    if _recorder is None:
        return False
    return _recorder.write_record_yaml(session_dir, session_data)


if __name__ == '__main__':
    import json
    
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    
    if cmd == 'create_session_dir':
        record_dir = sys.argv[2]
        start_time = sys.argv[3]
        first_file = sys.argv[4] if len(sys.argv) > 4 else ''
        uuid_len = int(sys.argv[5]) if len(sys.argv) > 5 else 8
        print(create_session_dir(record_dir, start_time, first_file, uuid_len))
    
    elif cmd == 'get_file_info':
        filepath = sys.argv[2]
        print(json.dumps(get_file_info_vim(filepath)))
    
    elif cmd == 'copy_original':
        src = sys.argv[2]
        file_id = int(sys.argv[3])
        dest_dir = sys.argv[4]
        print(copy_original_vim(src, file_id, dest_dir))
    
    elif cmd == 'generate_diff':
        original = sys.argv[2]
        current = sys.argv[3]
        output = sys.argv[4]
        print(json.dumps(generate_diff_vim(original, current, output)))
    
    elif cmd == 'write_record':
        session_dir = sys.argv[2]
        data = json.loads(sys.argv[3])
        print('true' if write_record_yaml_vim(session_dir, data) else 'false')
    
    elif cmd == 'generate_uuid':
        print(generate_uuid())
    
    elif cmd == 'get_timestamp':
        print(get_current_timestamp())
    
    elif cmd == 'get_dirname_timestamp':
        print(get_dirname_timestamp())
