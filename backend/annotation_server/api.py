from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .config import DataProfile, load_profile
from .services import (
    AnnotationLocks,
    load_dropped_datasets,
    load_visualization_bundle,
    mark_dataset as save_dataset_mark,
    next_available_file,
)
from .storage import (
    get_annotation_for_file,
    list_files_recursive,
    load_annotations,
    write_annotation,
)


def create_app(profile_name: str | None = None, profile: DataProfile | None = None) -> FastAPI:
    settings = profile or load_profile(profile_name)
    locks = AnnotationLocks()
    app = FastAPI(title="Annotation Server")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "raw_data_root": str(settings.raw_data_root),
            "vis_data_root": str(settings.vis_data_root),
            "annotation_file": str(settings.annotation_file),
        }

    @app.get("/serve_image")
    def serve_image(file_path: str = Query(...)):
        path = Path(file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        return FileResponse(path)

    @app.get("/api/file_tree")
    def get_file_tree():
        tree = list_files_recursive(settings.raw_data_root, settings, settings.cache_tree_path)
        annotations = load_annotations(settings.annotation_file)
        dropped_datasets = load_dropped_datasets(settings)

        def add_status(node: dict) -> None:
            if node["type"] == "file":
                node["is_annotated"] = node["path"] in annotations
                active = locks.active.get(node["path"])
                node["is_active"] = bool(active)
                node["active_user"] = active["user"] if active else None
                return

            node["is_discarded"] = node.get("name") in dropped_datasets
            for child in node.get("children", []):
                add_status(child)

        locks.cleanup()
        for item in tree:
            add_status(item)
        return JSONResponse(tree)

    @app.get("/api/visualization/{file_path:path}")
    def get_visualization(
        file_path: str,
        sub_block: int = Query(0),
        optimize: bool = True,
        max_points_per_channel: int = 1500,
    ):
        return JSONResponse(load_visualization_bundle(
            settings,
            file_path,
            sub_block,
            optimize,
            max_points_per_channel,
        ))

    @app.get("/api/annotation/{file_path:path}")
    def get_annotation(file_path: str):
        return JSONResponse(get_annotation_for_file(settings.annotation_file, file_path))

    @app.post("/api/annotate")
    def annotate(record: dict):
        file_path = record.get("file_path")
        user = record.get("user")
        if not file_path or not user:
            raise HTTPException(status_code=400, detail="file_path and user are required")
        if locks.is_occupied_by_other(file_path, user):
            raise HTTPException(status_code=409, detail="File is being annotated by another user")

        write_annotation(settings.annotation_file, record)
        locks.release(file_path, user)
        return {"status": "ok", "action": "updated"}

    @app.get("/api/next_unannotated")
    def get_next_unannotated(user: str = Query(...), current_file: Optional[str] = Query(None)):
        locks.cleanup()
        tree = list_files_recursive(settings.raw_data_root, settings, settings.cache_tree_path)
        file_path = next_available_file(tree, settings.annotation_file, locks, user, current_file)
        if not file_path:
            raise HTTPException(status_code=404, detail="No available unannotated files found")
        return {"file_path": file_path}

    @app.post("/api/datasets/mark")
    def mark_dataset(data: dict):
        dataset_path = data.get("path")
        action = data.get("action")
        if not dataset_path or not action:
            raise HTTPException(status_code=400, detail="dataset_path and action are required")
        if action not in {"discard", "cancel"}:
            raise HTTPException(status_code=400, detail="action must be 'discard' or 'cancel'")
        return save_dataset_mark(settings, dataset_path, action)

    @app.post("/api/start_annotation")
    def start_annotation(data: dict):
        file_path = data.get("file_path")
        user = data.get("user")
        if not file_path or not user:
            raise HTTPException(status_code=400, detail="file_path and user are required")
        if not locks.acquire(file_path, user):
            active_user = locks.active[file_path]["user"]
            raise HTTPException(status_code=409, detail=f"File is being annotated by {active_user}")
        return {"status": "ok", "message": "annotation started"}

    @app.post("/api/end_annotation")
    def end_annotation(data: dict):
        file_path = data.get("file_path")
        user = data.get("user")
        if not file_path or not user:
            raise HTTPException(status_code=400, detail="file_path and user are required")
        locks.release(file_path, user)
        return {"status": "ok", "message": "annotation ended"}

    @app.post("/api/keep_alive")
    def keep_alive(data: dict):
        file_path = data.get("file_path")
        user = data.get("user")
        if not file_path or not user:
            raise HTTPException(status_code=400, detail="file_path and user are required")
        locks.keep_alive(file_path, user)
        return {"status": "ok"}

    return app
