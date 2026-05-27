from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from metamapper.inspection_backends import ArcPyBackend, BasicFileBackend, InspectionBackend, InspectionError, OpenSourceBackend
from metamapper.inspection_types import DatasetInspection


@dataclass(slots=True)
class DatasetInspector:
    """Coordinates dataset inspection across available backends."""

    backends: list[InspectionBackend] = field(
        default_factory=lambda: [ArcPyBackend(), OpenSourceBackend(), BasicFileBackend()]
    )

    def list_layers(self, dataset_path: str | Path) -> list[str]:
        path = Path(dataset_path)
        errors: list[str] = []
        for backend in self._candidate_backends(path):
            try:
                layer_names = backend.list_layers(path)
                if layer_names or not path.is_dir():
                    return layer_names
                errors.append(f"{backend.name}: discovered no layers")
            except Exception as exc:
                errors.append(f"{backend.name}: {exc}")
                continue
        raise InspectionError(self._format_backend_error(path, errors))

    def inspect(self, dataset_path: str | Path, layer: str | None = None) -> DatasetInspection:
        path = Path(dataset_path)
        errors: list[str] = []
        for backend in self._candidate_backends(path):
            try:
                return backend.inspect(path, layer=layer)
            except Exception as exc:
                errors.append(f"{backend.name}: {exc}")
                continue
        raise InspectionError(self._format_backend_error(path, errors))

    def _candidate_backends(self, path: Path) -> list[InspectionBackend]:
        if not path.exists():
            raise InspectionError(f"Dataset path does not exist: {path}")

        available: list[InspectionBackend] = []
        for backend in self.backends:
            try:
                is_available = backend.is_available()
            except Exception:
                is_available = False
            if is_available:
                available.append(backend)

        candidates: list[InspectionBackend] = []
        for backend in available:
            try:
                if backend.supports(path):
                    candidates.append(backend)
            except Exception:
                continue

        if candidates:
            return candidates

        raise InspectionError(self._format_backend_error(path, []))

    def _format_backend_error(self, path: Path, errors: list[str]) -> str:
        message = (
            f"No inspection backend could successfully handle dataset: {path}. "
            "Install ArcPy or optional open-source GIS dependencies for richer dataset support."
        )
        if errors:
            message += " Backend errors: " + " | ".join(errors)
        return message
