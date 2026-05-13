from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class FieldInfo:
    """Describes a vector attribute field discovered from a dataset."""

    name: str
    field_type: str
    alias: str | None = None
    length: int | None = None
    nullable: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SpatialReferenceInfo:
    """Describes a dataset spatial reference."""

    name: str | None = None
    epsg: int | None = None
    wkt: str | None = None
    datum: str | None = None
    unit: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExtentInfo:
    """Geographic bounding coordinates."""

    west: float
    east: float
    south: float
    north: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(slots=True)
class RasterInfo:
    """Raster-specific inspection metadata."""

    width: int
    height: int
    band_count: int
    cell_size_x: float | None = None
    cell_size_y: float | None = None
    nodata_values: list[float | int | str | None] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LayerInfo:
    """Describes one vector layer or raster dataset."""

    name: str
    data_kind: str
    geometry_type: str | None = None
    feature_count: int | None = None
    fields: list[FieldInfo] = field(default_factory=list)
    spatial_reference: SpatialReferenceInfo | None = None
    extent: ExtentInfo | None = None
    raster: RasterInfo | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


@dataclass(slots=True)
class DatasetInspection:
    """Combined inspection result for a dataset and optional selected layer."""

    dataset_path: str
    dataset_name: str
    backend_name: str
    data_format: str
    file_size_bytes: int | None
    modified_date: str | None
    layer_names: list[str] = field(default_factory=list)
    selected_layer: str | None = None
    layer_info: LayerInfo | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
