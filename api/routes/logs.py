from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Response

router = APIRouter(
    prefix="/logs",
    tags=["Logs"]
)


def _logs_root() -> Path:
    return Path(__file__).resolve().parents[2] / "logs"


def build_tree(root: Path) -> Dict[str, Any]:
    tree = {}
    if not root.exists():
        return tree
    for p in sorted(root.iterdir()):
        if p.is_dir():
            tree[p.name] = {"files": [f.name for f in sorted(p.rglob('*') if p.exists() else []) if f.is_file()]}
        elif p.is_file():
            tree.setdefault("_root_files", []).append(p.name)
    return tree


def most_recent_file(root: Path) -> Optional[Path]:
    if not root.exists():
        return None
    files = [p for p in root.rglob("*") if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def most_recent_in_module(root: Path, module: str) -> Optional[Path]:
    module_dir = root / module
    if not module_dir.exists():
        return None
    return most_recent_file(module_dir)


def find_file_for_module_task(root: Path, module: str, task_id: str) -> Optional[Path]:
    module_dir = root / module
    if not module_dir.exists():
        return None
    # Prefer files that include the task_id in their filename
    matches = [p for p in module_dir.rglob("*") if p.is_file() and task_id in p.name]
    if matches:
        return max(matches, key=lambda p: p.stat().st_mtime)
    # Otherwise try to find files whose parent folder matches task_id
    matches = [p for p in module_dir.rglob("*") if p.is_file() and p.parent.name == task_id]
    if matches:
        return max(matches, key=lambda p: p.stat().st_mtime)
    return None


@router.get("/tree", summary="Lista el file tree dentro de ./logs")
def get_logs_tree():
    root = _logs_root()
    tree = build_tree(root)
    names = [p.name for p in root.iterdir()] if root.exists() else []
    return {"names": names, "tree": tree}


@router.get(
    "/view",
    summary="Ver logs (opcional: /view/{module} o /view/{module}/{task_id})"
)
@router.get("/view/{module}")
@router.get("/view/{module}/{task_id}")
def view_log(module: Optional[str] = None, task_id: Optional[str] = None):
    root = _logs_root()
    # Neither module nor task_id: return most recent file in whole tree
    if not module and not task_id:
        p = most_recent_file(root)
        if not p:
            raise HTTPException(status_code=404, detail="No log files found")
        try:
            return Response(content=p.read_text(encoding='utf-8', errors='ignore'), media_type='text/plain')
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Module provided but no task_id: return most recent inside module
    if module and not task_id:
        p = most_recent_in_module(root, module)
        if not p:
            raise HTTPException(status_code=404, detail=f"No logs found for module '{module}'")
        try:
            return Response(content=p.read_text(encoding='utf-8', errors='ignore'), media_type='text/plain')
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Both module and task_id provided: find the specific file
    if module and task_id:
        p = find_file_for_module_task(root, module, task_id)
        if not p:
            raise HTTPException(status_code=404, detail=f"No log found for module '{module}' and task '{task_id}'")
        try:
            return Response(content=p.read_text(encoding='utf-8', errors='ignore'), media_type='text/plain')
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=400, detail="Invalid parameters")


@router.get("/api/{limit}", summary="Ver últimos N lines de los logs de la API")
@router.get("/api", summary="Ver últimos 1000 lines de los logs de la API")
def view_api_logs(limit: int = 1000):
    root = _logs_root()
    api_dir = root / "api"
    target = None
    if api_dir.exists():
        target = most_recent_file(api_dir)
    if not target:
        # fallback: try any file with 'api' in name under logs
        candidates = [p for p in root.rglob("*") if p.is_file() and 'api' in p.name.lower()]
        if candidates:
            target = max(candidates, key=lambda p: p.stat().st_mtime)
    if not target:
        target = most_recent_file(root)
    if not target:
        raise HTTPException(status_code=404, detail="No API log files found")

    try:
        text = target.read_text(encoding='utf-8', errors='ignore')
        lines = text.splitlines()
        tail = lines[-limit:] if limit and len(lines) > limit else lines
        return {"file": str(target.relative_to(Path(__file__).resolve().parents[2])), "lines": tail}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
