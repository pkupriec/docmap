from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path


_VERSION_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$", re.IGNORECASE)
_MODE_RE = re.compile(r"^[a-z][a-z0-9_]*$", re.IGNORECASE)


class GeometryArtifactError(RuntimeError):
    def __init__(self, code: str, *, status_code: int = 404) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class GeometryArchive:
    version: str
    mode: str
    path: Path
    byte_size: int


class GeometryArtifactStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or Path(os.getenv("DOCMAP_PRESENTATION_ARTIFACT_ROOT", "/data/presentation_geometry"))).resolve()

    def _safe_segment(self, raw: object, *, pattern: re.Pattern[str], field: str) -> str:
        value = str(raw or "").strip()
        if not value or pattern.fullmatch(value) is None:
            raise GeometryArtifactError(f"baked_geometry_{field}_invalid", status_code=422)
        return value

    def _read_json(self, path: Path, *, missing: str, invalid: str) -> dict[str, object]:
        if not path.is_file():
            raise GeometryArtifactError(missing)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GeometryArtifactError(invalid, status_code=500) from exc
        if not isinstance(payload, dict):
            raise GeometryArtifactError(invalid, status_code=500)
        return payload

    def _inside_root(self, path: Path) -> Path:
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root):
            raise GeometryArtifactError("baked_geometry_path_invalid", status_code=500)
        return resolved

    def load(self, mode: str | None = None) -> tuple[dict[str, object], str, str, str]:
        pointer = self._read_json(
            self.root / "current.json",
            missing="baked_geometry_pointer_not_found",
            invalid="baked_geometry_pointer_invalid",
        )
        version = self._safe_segment(pointer.get("current_version"), pattern=_VERSION_RE, field="version")
        manifest_rel = str(pointer.get("manifest") or f"{version}/manifest.json")
        manifest = self._read_json(
            self._inside_root(self.root / manifest_rel),
            missing="baked_geometry_manifest_not_found",
            invalid="baked_geometry_manifest_invalid",
        )
        modes = manifest.get("modes")
        if not isinstance(modes, dict) or not modes:
            raise GeometryArtifactError("baked_geometry_modes_missing")
        available_modes = sorted(str(item) for item in modes)
        configured = str(os.getenv("DOCMAP_PRESENTATION_DEFAULT_PRECISION_MODE", "")).strip()
        default_mode = configured if configured in available_modes else available_modes[0]
        selected_mode = self._safe_segment(mode or default_mode, pattern=_MODE_RE, field="mode")
        if selected_mode not in modes:
            raise GeometryArtifactError("baked_geometry_mode_not_found")
        return manifest, version, selected_mode, default_mode

    def archive(self, *, version: str, mode: str) -> GeometryArchive:
        manifest, current_version, selected_mode, _ = self.load(mode)
        safe_version = self._safe_segment(version, pattern=_VERSION_RE, field="version")
        if safe_version != current_version:
            raise GeometryArtifactError("baked_geometry_archive_not_found")
        modes = manifest["modes"]
        assert isinstance(modes, dict)
        mode_payload = modes[selected_mode]
        if not isinstance(mode_payload, dict):
            raise GeometryArtifactError("baked_geometry_mode_not_found")
        relative_path = str(mode_payload.get("path") or f"{safe_version}/{selected_mode}.pmtiles")
        path = self._inside_root(self.root / relative_path)
        if path.suffix.lower() != ".pmtiles" or not path.is_file():
            raise GeometryArtifactError("baked_geometry_archive_not_found")
        return GeometryArchive(version=safe_version, mode=selected_mode, path=path, byte_size=path.stat().st_size)

    def manifest_response(self, mode: str | None = None) -> dict[str, object]:
        manifest, version, selected_mode, default_mode = self.load(mode)
        modes = manifest["modes"]
        assert isinstance(modes, dict)
        selected = modes[selected_mode]
        if not isinstance(selected, dict):
            raise GeometryArtifactError("baked_geometry_mode_not_found")
        archive = self.archive(version=version, mode=selected_mode)
        return {
            "schema_version": manifest.get("schema_version"),
            "version": version,
            "mode": selected_mode,
            "default_mode": default_mode,
            "available_modes": sorted(str(item) for item in modes),
            "tile_format": "pmtiles",
            "min_zoom": manifest.get("min_zoom"),
            "max_zoom": manifest.get("max_zoom"),
            "archive_url": f"/api/map/baked/archives/{version}/{selected_mode}.pmtiles",
            "byte_size": selected.get("byte_size", archive.byte_size),
        }
