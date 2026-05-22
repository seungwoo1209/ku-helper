#!/usr/bin/env python3
"""cd가 프로젝트 루트를 벗어나는 걸 막는 PreToolUse 훅."""
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

def find_project_root(start: Path) -> Path:
    """git 루트를 우선 사용. 실패 시 마커 파일로 폴백."""
    # 1순위: git
    try:
        result = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=2, check=True,
        )
        return Path(result.stdout.strip()).resolve()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # 2순위: .claude/ 디렉터리가 있는 가장 가까운 상위
    for p in [start, *start.parents]:
        if (p / ".claude").is_dir():
            return p.resolve()

    # 폴백: start 자체
    return start.resolve()

def extract_cd_targets(command: str):
    # 한계: `$(cd /tmp)` / `(cd /tmp && ls)` 같은 명령 치환·서브셸은 분리 대상이 아니라 검출 못 함.
    # 보안 경계가 아닌 실수 방지용 가드이므로 의도된 trade-off.
    targets = []
    for seg in re.split(r'(?:&&|\|\||;|\|)', command):
        seg = seg.strip()
        if not seg:
            continue
        try:
            tokens = shlex.split(seg)
        except ValueError:
            continue
        if not tokens:
            continue
        if tokens[0] in ("cd", "pushd"):
            targets.append(tokens[1] if len(tokens) > 1 else "~")
    return targets

def resolve(target: str, cwd: Path) -> Path:
    target = os.path.expanduser(os.path.expandvars(target))
    p = Path(target)
    if not p.is_absolute():
        p = cwd / p
    return p.resolve()

def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if data.get("tool_name") != "Bash":
        sys.exit(0)

    command = data.get("tool_input", {}).get("command", "")
    cwd = Path(data.get("cwd", os.getcwd()))
    project_root = find_project_root(cwd)

    for t in extract_cd_targets(command):
        resolved = resolve(t, cwd)
        try:
            resolved.relative_to(project_root)
        except ValueError:
            print(
                f"Blocked: cd '{t}' would leave project root\n"
                f"  project: {project_root}\n"
                f"  resolved: {resolved}",
                file=sys.stderr,
            )
            sys.exit(2)

    sys.exit(0)

if __name__ == "__main__":
    main()
