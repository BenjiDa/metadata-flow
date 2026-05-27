from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
from typing import Protocol

from metamapper.inspection_types import DatasetInspection, ExtentInfo, FieldInfo, LayerInfo, RasterInfo, SpatialReferenceInfo


class InspectionError(RuntimeError):
    """Raised when dataset inspection fails."""


class InspectionBackend(Protocol):
    """Interface for dataset inspection backends."""

    name: str

    def is_available(self) -> bool:
        """Return True when the backend can be used in the current environment."""

    def supports(self, path: Path) -> bool:
        """Return True when the backend likely supports the dataset path."""

    def list_layers(self, path: Path) -> list[str]:
        """Return available layer names for the dataset path."""

    def inspect(self, path: Path, layer: str | None = None, all_layers: bool = False) -> DatasetInspection:
        """Inspect the dataset path and return structured metadata."""


VECTOR_SUFFIXES = {".shp", ".gpkg", ".geojson", ".json", ".gml", ".kml"}
RASTER_SUFFIXES = {".tif", ".tiff", ".img", ".vrt", ".jp2", ".asc"}


def _modified_date(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    except FileNotFoundError:
        return None


def _file_size(path: Path) -> int | None:
    try:
        if path.is_file():
            return path.stat().st_size
        if path.is_dir():
            return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
    except FileNotFoundError:
        return None
    return None


def _dataset_name(path: Path, layer: str | None = None) -> str:
    return layer or path.stem or path.name


@dataclass(slots=True)
class BasicFileBackend:
    """Fallback backend that provides non-spatial file metadata only."""

    name: str = "basic-file"

    def is_available(self) -> bool:
        return True

    def supports(self, path: Path) -> bool:
        return path.exists()

    def list_layers(self, path: Path) -> list[str]:
        if path.suffix.lower() in VECTOR_SUFFIXES | RASTER_SUFFIXES:
            return [path.stem]
        if path.suffix.lower() == ".gdb" or path.is_dir():
            return []
        return [path.name]

    def inspect(self, path: Path, layer: str | None = None, all_layers: bool = False) -> DatasetInspection:
        if not path.exists():
            raise InspectionError(f"Dataset path does not exist: {path}")
        warning = (
            "Spatial metadata could not be extracted from this dataset with the currently usable inspection backends. "
            "Install ArcPy or the optional open-source inspection dependencies for richer prefill output when supported."
        )
        return DatasetInspection(
            dataset_path=str(path.resolve()),
            dataset_name=_dataset_name(path, layer),
            backend_name=self.name,
            data_format=path.suffix.lower().lstrip(".") or ("directory" if path.is_dir() else "unknown"),
            file_size_bytes=_file_size(path),
            modified_date=_modified_date(path),
            layer_names=self.list_layers(path),
            selected_layer=layer,
            warnings=[warning],
        )


@dataclass(slots=True)
class OpenSourceBackend:
    """Optional pyogrio/rasterio backend."""

    name: str = "open-source"

    def is_available(self) -> bool:
        try:
            import pyogrio  # noqa: F401
            import rasterio  # noqa: F401
        except ImportError:
            try:
                import pyogrio  # noqa: F401
            except ImportError:
                try:
                    import rasterio  # noqa: F401
                except ImportError:
                    return False
        return True

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in VECTOR_SUFFIXES | RASTER_SUFFIXES or path.suffix.lower() == ".gdb"

    def list_layers(self, path: Path) -> list[str]:
        suffix = path.suffix.lower()
        if suffix in RASTER_SUFFIXES:
            return [path.stem]
        if suffix in VECTOR_SUFFIXES or suffix == ".gdb":
            try:
                import pyogrio
            except ImportError as exc:
                raise InspectionError("pyogrio is required to list vector dataset layers.") from exc
            layers = pyogrio.list_layers(path)
            return [str(row[0]) for row in layers]
        return []

    def inspect(self, path: Path, layer: str | None = None, all_layers: bool = False) -> DatasetInspection:
        if not path.exists():
            raise InspectionError(f"Dataset path does not exist: {path}")

        suffix = path.suffix.lower()
        if suffix in RASTER_SUFFIXES:
            return self._inspect_raster(path)
        if suffix in VECTOR_SUFFIXES or suffix == ".gdb":
            return self._inspect_vector(path, layer=layer, all_layers=all_layers)
        raise InspectionError(f"Open-source backend does not support dataset type: {path}")

    def _inspect_vector(self, path: Path, layer: str | None = None, all_layers: bool = False) -> DatasetInspection:
        try:
            import pyogrio
        except ImportError as exc:
            raise InspectionError("pyogrio is required for vector dataset inspection.") from exc

        layer_names = [str(row[0]) for row in pyogrio.list_layers(path)]
        selected_layer = layer
        if all_layers:
            selected_layer = None
        elif selected_layer is None:
            if len(layer_names) == 1:
                selected_layer = layer_names[0]

        layer_details = [self._read_vector_layer(path, layer_name) for layer_name in layer_names]
        if selected_layer is None and len(layer_details) == 1:
            layer_info = layer_details[0]
        elif selected_layer is not None:
            layer_info = next((detail for detail in layer_details if detail.name == selected_layer), None)
            if layer_info is None:
                raise InspectionError(f"Layer '{selected_layer}' was not found in dataset: {path}")
        else:
            layer_info = None

        return DatasetInspection(
            dataset_path=str(path.resolve()),
            dataset_name=_dataset_name(path, selected_layer),
            backend_name=self.name,
            data_format=self._driver_for_vector(path, selected_layer),
            file_size_bytes=_file_size(path),
            modified_date=_modified_date(path),
            layer_names=layer_names,
            selected_layer=selected_layer,
            layer_info=layer_info,
            layer_details=layer_details,
        )

    def _inspect_raster(self, path: Path) -> DatasetInspection:
        try:
            import rasterio
        except ImportError as exc:
            raise InspectionError("rasterio is required for raster dataset inspection.") from exc

        with rasterio.open(path) as dataset:
            crs_info = _coerce_spatial_reference(dataset.crs)
            bounds = dataset.bounds
            extent = ExtentInfo(
                west=float(bounds.left),
                east=float(bounds.right),
                south=float(bounds.bottom),
                north=float(bounds.top),
            )
            raster_info = RasterInfo(
                width=int(dataset.width),
                height=int(dataset.height),
                band_count=int(dataset.count),
                cell_size_x=float(dataset.res[0]) if dataset.res else None,
                cell_size_y=float(dataset.res[1]) if dataset.res else None,
                nodata_values=list(dataset.nodatavals or []),
            )
            layer_info = LayerInfo(
                name=path.stem,
                data_kind="raster",
                spatial_reference=crs_info,
                extent=extent,
                raster=raster_info,
            )
        return DatasetInspection(
            dataset_path=str(path.resolve()),
            dataset_name=path.stem,
            backend_name=self.name,
            data_format=path.suffix.lower().lstrip("."),
            file_size_bytes=_file_size(path),
            modified_date=_modified_date(path),
            layer_names=[path.stem],
            selected_layer=path.stem,
            layer_info=layer_info,
            layer_details=[layer_info],
        )

    def _driver_for_vector(self, path: Path, layer: str | None) -> str:
        suffix = path.suffix.lower()
        if suffix == ".gdb":
            return "OpenFileGDB"
        if suffix == ".shp":
            return "ESRI Shapefile"
        try:
            import pyogrio
        except ImportError as exc:
            raise InspectionError("pyogrio is required for vector dataset inspection.") from exc
        info = pyogrio.read_info(path, layer=layer)
        return str(info.get("driver") or suffix.lstrip("."))

    def _read_vector_layer(self, path: Path, layer_name: str | None) -> LayerInfo:
        try:
            import pyogrio
        except ImportError as exc:
            raise InspectionError("pyogrio is required for vector dataset inspection.") from exc

        info = pyogrio.read_info(path, layer=layer_name)
        crs_info = _coerce_spatial_reference(info.get("crs"))
        extent = None
        bounds = info.get("total_bounds")
        if bounds is not None and len(bounds) == 4:
            extent = ExtentInfo(
                west=float(bounds[0]),
                south=float(bounds[1]),
                east=float(bounds[2]),
                north=float(bounds[3]),
            )

        field_names = _as_list(info.get("fields"))
        field_types = _as_list(info.get("dtypes"))
        fields: list[FieldInfo] = []
        for index, field_name in enumerate(field_names):
            field_type = str(field_types[index]) if index < len(field_types) else "unknown"
            fields.append(FieldInfo(name=str(field_name), field_type=field_type))

        geometry_type = info.get("geometry_type")
        if geometry_type is None:
            geometry_type = info.get("geometry")

        return LayerInfo(
            name=layer_name or _dataset_name(path),
            data_kind="vector",
            geometry_type=str(geometry_type or "None"),
            feature_count=int(info.get("features")) if info.get("features") is not None else None,
            fields=fields,
            spatial_reference=crs_info,
            extent=extent,
        )


@dataclass(slots=True)
class ArcPyBackend:
    """Optional ArcPy backend for ArcGIS-managed datasets."""

    name: str = "arcpy"

    def is_available(self) -> bool:
        try:
            import arcpy  # noqa: F401
        except ImportError:
            return False
        return True

    def supports(self, path: Path) -> bool:
        return path.exists()

    def list_layers(self, path: Path) -> list[str]:
        try:
            import arcpy
        except ImportError as exc:
            raise InspectionError("ArcPy is not available.") from exc

        if path.suffix.lower() != ".gdb":
            return [path.stem]

        previous_workspace = arcpy.env.workspace
        try:
            arcpy.env.workspace = str(path)
            feature_classes = arcpy.ListFeatureClasses() or []
            feature_datasets = arcpy.ListDatasets(feature_type="feature") or []
            tables = arcpy.ListTables() or []
            rasters = arcpy.ListRasters() or []
            nested_feature_classes: list[str] = []
            for dataset in feature_datasets:
                dataset_name = str(dataset)
                dataset_feature_classes = arcpy.ListFeatureClasses(feature_dataset=dataset_name) or []
                nested_feature_classes.extend(f"{dataset_name}/{feature_class}" for feature_class in dataset_feature_classes)
            return [str(name) for name in [*feature_classes, *nested_feature_classes, *tables, *rasters]]
        finally:
            arcpy.env.workspace = previous_workspace

    def inspect(self, path: Path, layer: str | None = None, all_layers: bool = False) -> DatasetInspection:
        try:
            import arcpy
        except ImportError as exc:
            raise InspectionError("ArcPy is not available.") from exc

        if not path.exists():
            raise InspectionError(f"Dataset path does not exist: {path}")

        target = str(path if layer is None else path / layer if path.suffix.lower() == ".gdb" else path)
        if path.suffix.lower() == ".gdb":
            layer_names = self.list_layers(path)
            if all_layers:
                layer_details = [self._inspect_layer_target(arcpy, path / layer_name, layer_name) for layer_name in layer_names]
                return DatasetInspection(
                    dataset_path=str(path.resolve()),
                    dataset_name=path.stem,
                    backend_name=self.name,
                    data_format="FileGDB",
                    file_size_bytes=_file_size(path),
                    modified_date=_modified_date(path),
                    layer_names=layer_names,
                    selected_layer=None,
                    layer_info=None,
                    layer_details=layer_details,
                )
            if layer is None:
                if len(layer_names) == 1:
                    layer = layer_names[0]
                else:
                    raise InspectionError(
                        f"Dataset contains multiple layers. Use `metamapper layers {path}` or specify --layer. "
                        f"Available layers: {', '.join(layer_names)}"
                    )
            resolved_layer = self._resolve_layer_name(layer_names, layer)
            if resolved_layer is None:
                raise InspectionError(f"Layer '{layer}' was not found in dataset: {path}")
            layer = resolved_layer
            target = str(path / layer)
        else:
            layer_names = [path.stem]

        layer_info = self._inspect_layer_target(arcpy, Path(target), layer or path.stem)

        return DatasetInspection(
            dataset_path=str(path.resolve()),
            dataset_name=_dataset_name(path, layer),
            backend_name=self.name,
            data_format=str(getattr(describe, "dataType", path.suffix.lower().lstrip("."))),
            file_size_bytes=_file_size(path),
            modified_date=_modified_date(path),
            layer_names=layer_names,
            selected_layer=layer,
            layer_info=layer_info,
            layer_details=[layer_info],
        )

    def _inspect_layer_target(self, arcpy: object, target: Path, layer_name: str) -> LayerInfo:
        describe = arcpy.Describe(str(target))
        extent = None
        if getattr(describe, "extent", None):
            ext = describe.extent
            extent = ExtentInfo(west=float(ext.XMin), east=float(ext.XMax), south=float(ext.YMin), north=float(ext.YMax))

        spatial_ref = getattr(describe, "spatialReference", None)
        spatial_reference = SpatialReferenceInfo(
            name=getattr(spatial_ref, "name", None),
            epsg=getattr(spatial_ref, "factoryCode", None) or None,
            wkt=spatial_ref.exportToString() if spatial_ref and hasattr(spatial_ref, "exportToString") else None,
            datum=getattr(spatial_ref, "datumName", None),
            unit=getattr(spatial_ref, "linearUnitName", None) or getattr(spatial_ref, "angularUnitName", None),
        )

        describe_type = str(getattr(describe, "dataType", "") or "").lower()
        data_kind = "raster" if "raster" in describe_type else "vector"
        layer_info = LayerInfo(name=layer_name, data_kind=data_kind, spatial_reference=spatial_reference, extent=extent)
        if data_kind == "vector":
            fields = []
            for field in arcpy.ListFields(str(target)):
                fields.append(
                    FieldInfo(
                        name=str(field.name),
                        field_type=str(field.type),
                        alias=str(getattr(field, "aliasName", "")) or None,
                        length=int(field.length) if getattr(field, "length", None) not in (None, 0) else None,
                        nullable=bool(getattr(field, "isNullable", False)),
                    )
                )
            layer_info.geometry_type = str(getattr(describe, "shapeType", "Unknown"))
            layer_info.feature_count = int(arcpy.management.GetCount(str(target))[0])
            layer_info.fields = fields
        else:
            layer_info.raster = RasterInfo(
                width=int(getattr(describe, "width", 0)),
                height=int(getattr(describe, "height", 0)),
                band_count=int(getattr(describe, "bandCount", 0)),
                cell_size_x=float(getattr(describe, "meanCellWidth", 0.0)) or None,
                cell_size_y=float(getattr(describe, "meanCellHeight", 0.0)) or None,
                nodata_values=[],
            )
        return layer_info

    def _resolve_layer_name(self, layer_names: list[str], requested_layer: str | None) -> str | None:
        if requested_layer is None:
            return None
        if requested_layer in layer_names:
            return requested_layer

        basename_matches = [layer_name for layer_name in layer_names if layer_name.split("/")[-1] == requested_layer]
        if len(basename_matches) == 1:
            return basename_matches[0]
        return None


def _coerce_spatial_reference(value: object) -> SpatialReferenceInfo | None:
    if value is None:
        return None

    name: str | None = None
    epsg: int | None = None
    wkt: str | None = None

    if hasattr(value, "to_epsg"):
        try:
            epsg = value.to_epsg()
        except Exception:
            epsg = None
    if hasattr(value, "to_wkt"):
        try:
            wkt = value.to_wkt()
        except Exception:
            wkt = None
    if hasattr(value, "name"):
        try:
            name = value.name
        except Exception:
            name = None
    if isinstance(value, str):
        text = value.strip()
        try:
            from pyproj import CRS

            crs = CRS.from_user_input(text)
            epsg = crs.to_epsg()
            wkt = crs.to_wkt()
            name = crs.name
        except Exception:
            wkt = text
            name = text.split("[", 1)[0].strip() if "[" in text else text
            match = re.match(r"EPSG:(\d+)$", text, re.IGNORECASE)
            if match:
                epsg = int(match.group(1))

    return SpatialReferenceInfo(name=name, epsg=epsg, wkt=wkt)


def _as_list(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    try:
        return list(value)  # type: ignore[arg-type]
    except TypeError:
        return [value]
