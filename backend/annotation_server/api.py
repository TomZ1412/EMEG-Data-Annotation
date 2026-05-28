from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .config import DataProfile, load_profile
from .services import (
    AnnotationLocks,
    load_visualization_bundle,
    next_available_file,
)
from .storage import (
    find_annotation,
    get_annotation_for_file,
    list_data_files,
    list_annotation_layers_for_file,
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
            "data_source": settings.data_source,
            "raw_data_root": str(settings.raw_data_root),
            "vis_data_root": str(settings.vis_data_root),
            "annotation_file": str(settings.annotation_file),
            "dataset_filters": list(settings.dataset_filters),
            "allow_open_annotated": settings.allow_open_annotated,
            "show_existing_annotations": settings.show_existing_annotations,
            "annotation_scope": settings.annotation_scope,
        }

    @app.get("/serve_image")
    def serve_image(file_path: str = Query(...)):
        path = Path(file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        return FileResponse(path)

    @app.get("/api/file_tree")
    def get_file_tree(refresh: bool = Query(False), user: Optional[str] = Query(None)):
        tree = list_data_files(settings, use_cache=not refresh)
        annotation_user = user if settings.annotation_scope == "user" else None
        annotations = load_annotations(
            settings.annotation_file,
            user=annotation_user,
            scope=settings.annotation_scope,
        )

        def add_status(node: dict) -> None:
            if node["type"] == "file":
                is_annotated = bool(find_annotation(annotations, node["path"], annotation_user, settings.annotation_scope))
                node["is_annotated"] = is_annotated
                node["can_open"] = settings.allow_open_annotated or not is_annotated
                active = locks.active.get(node["path"])
                node["is_active"] = bool(active)
                node["active_user"] = active["user"] if active else None
                return

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
    def get_annotation(file_path: str, user: Optional[str] = Query(None)):
        if not settings.show_existing_annotations:
            return JSONResponse({
                "bad_channels": [],
                "psd_bad_channels": [],
                "wav_bad_channels": {},
                "subblock_bad_channels": {},
                "artifacts": [],
                "discarded": False,
            })
        annotation_user = user if settings.annotation_scope == "user" else None
        return JSONResponse(get_annotation_for_file(
            settings.annotation_file,
            file_path,
            user=annotation_user,
            scope=settings.annotation_scope,
        ))

    @app.get("/api/annotation_layers/{file_path:path}")
    def get_annotation_layers(file_path: str, user: Optional[str] = Query(None)):
        if not settings.show_existing_annotations:
            return JSONResponse({
                "file_path": file_path,
                "current_user": user or "",
                "layers": [],
            })

        layers = list_annotation_layers_for_file(settings.annotation_file, file_path)
        return JSONResponse({
            "file_path": file_path,
            "current_user": user or "",
            "layers": layers,
        })

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
        tree = list_data_files(settings)
        file_path = next_available_file(tree, settings.annotation_file, locks, user, current_file, settings.annotation_scope)
        if not file_path:
            raise HTTPException(status_code=404, detail="No available unannotated files found")
        return {"file_path": file_path}

    @app.post("/api/start_annotation")
    def start_annotation(data: dict):
        file_path = data.get("file_path")
        user = data.get("user")
        if not file_path or not user:
            raise HTTPException(status_code=400, detail="file_path and user are required")
        annotation_user = user if settings.annotation_scope == "user" else None
        annotations = load_annotations(
            settings.annotation_file,
            user=annotation_user,
            scope=settings.annotation_scope,
        )
        if not settings.allow_open_annotated and find_annotation(annotations, file_path, annotation_user, settings.annotation_scope):
            raise HTTPException(status_code=409, detail="This file has already been annotated")
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
