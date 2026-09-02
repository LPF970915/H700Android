#!/usr/bin/env python3
"""Inspect and extract Android logical partitions from a raw super image."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path


SECTOR_SIZE = 512
GEOMETRY_OFFSET = 4096
GEOMETRY_BLOCK_SIZE = 4096
GEOMETRY_MAGIC = 0x616C4467
METADATA_MAGIC = 0x414C5030
METADATA_MAJOR_VERSION = 10
METADATA_HEADER_V1_SIZE = 128
TARGET_LINEAR = 0
TARGET_ZERO = 1


@dataclass(frozen=True)
class Geometry:
    metadata_max_size: int
    metadata_slot_count: int
    logical_block_size: int


@dataclass(frozen=True)
class TableDescriptor:
    offset: int
    num_entries: int
    entry_size: int


@dataclass(frozen=True)
class Partition:
    name: str
    attributes: int
    first_extent_index: int
    num_extents: int
    group_index: int


@dataclass(frozen=True)
class Extent:
    num_sectors: int
    target_type: int
    target_data: int
    target_source: int


@dataclass(frozen=True)
class Group:
    name: str
    flags: int
    maximum_size: int


@dataclass(frozen=True)
class BlockDevice:
    first_logical_sector: int
    alignment: int
    alignment_offset: int
    size: int
    partition_name: str
    flags: int


@dataclass(frozen=True)
class Metadata:
    major: int
    minor: int
    header_size: int
    tables_size: int
    partitions: tuple[Partition, ...]
    extents: tuple[Extent, ...]
    groups: tuple[Group, ...]
    block_devices: tuple[BlockDevice, ...]
    raw: bytes


def read_exact(stream, size: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise ValueError(f"unexpected EOF: wanted {size} bytes, got {len(data)}")
    return data


def decode_name(raw: bytes, field: str) -> str:
    value = raw.split(b"\0", 1)[0]
    if not value:
        raise ValueError(f"empty {field}")
    try:
        return value.decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError(f"non-ASCII {field}") from error


def checked_span(offset: int, count: int, size: int, limit: int, label: str) -> tuple[int, int]:
    if offset < 0 or count < 0 or size <= 0:
        raise ValueError(f"invalid {label} descriptor")
    end = offset + count * size
    if end > limit:
        raise ValueError(f"{label} table exceeds metadata tables")
    return offset, end


def parse_geometry(block: bytes, label: str) -> Geometry:
    if len(block) != GEOMETRY_BLOCK_SIZE:
        raise ValueError(f"short {label} geometry block")
    magic, struct_size = struct.unpack_from("<II", block, 0)
    if magic != GEOMETRY_MAGIC:
        raise ValueError(f"bad {label} geometry magic: 0x{magic:08x}")
    if struct_size < 52 or struct_size > len(block):
        raise ValueError(f"invalid {label} geometry struct size: {struct_size}")

    stored_checksum = block[8:40]
    checked = bytearray(block[:struct_size])
    checked[8:40] = bytes(32)
    actual_checksum = hashlib.sha256(checked).digest()
    if actual_checksum != stored_checksum:
        raise ValueError(f"{label} geometry checksum mismatch")

    metadata_max_size, slot_count, logical_block_size = struct.unpack_from("<III", block, 40)
    if metadata_max_size == 0 or metadata_max_size % SECTOR_SIZE:
        raise ValueError("metadata_max_size is not sector aligned")
    if slot_count == 0:
        raise ValueError("metadata_slot_count is zero")
    if logical_block_size == 0 or logical_block_size % SECTOR_SIZE:
        raise ValueError("logical_block_size is not sector aligned")
    return Geometry(metadata_max_size, slot_count, logical_block_size)


def descriptor(header: bytes, offset: int, name: str, tables_size: int) -> TableDescriptor:
    table_offset, num_entries, entry_size = struct.unpack_from("<III", header, offset)
    checked_span(table_offset, num_entries, entry_size, tables_size, name)
    return TableDescriptor(table_offset, num_entries, entry_size)


def parse_entries(tables: bytes, desc: TableDescriptor, expected_size: int, label: str):
    if desc.entry_size != expected_size:
        raise ValueError(
            f"unsupported {label} entry size: {desc.entry_size}, expected {expected_size}"
        )
    for index in range(desc.num_entries):
        start = desc.offset + index * desc.entry_size
        yield tables[start : start + desc.entry_size]


def parse_metadata(raw: bytes, max_size: int, label: str) -> Metadata:
    if len(raw) != max_size:
        raise ValueError(f"short {label} metadata slot")
    magic, major, minor, header_size = struct.unpack_from("<IHHI", raw, 0)
    if magic != METADATA_MAGIC:
        raise ValueError(f"bad {label} metadata magic: 0x{magic:08x}")
    if major != METADATA_MAJOR_VERSION:
        raise ValueError(f"unsupported metadata version: {major}.{minor}")
    if header_size < METADATA_HEADER_V1_SIZE or header_size > max_size:
        raise ValueError(f"invalid metadata header size: {header_size}")

    stored_header_checksum = raw[12:44]
    checked_header = bytearray(raw[:header_size])
    checked_header[12:44] = bytes(32)
    if hashlib.sha256(checked_header).digest() != stored_header_checksum:
        raise ValueError(f"{label} metadata header checksum mismatch")

    tables_size = struct.unpack_from("<I", raw, 44)[0]
    if tables_size > max_size - header_size:
        raise ValueError(f"{label} metadata tables exceed slot")
    tables = raw[header_size : header_size + tables_size]
    if hashlib.sha256(tables).digest() != raw[48:80]:
        raise ValueError(f"{label} metadata tables checksum mismatch")

    partition_desc = descriptor(raw, 80, "partition", tables_size)
    extent_desc = descriptor(raw, 92, "extent", tables_size)
    group_desc = descriptor(raw, 104, "group", tables_size)
    block_device_desc = descriptor(raw, 116, "block-device", tables_size)

    spans = sorted(
        [
            checked_span(partition_desc.offset, partition_desc.num_entries, partition_desc.entry_size, tables_size, "partition"),
            checked_span(extent_desc.offset, extent_desc.num_entries, extent_desc.entry_size, tables_size, "extent"),
            checked_span(group_desc.offset, group_desc.num_entries, group_desc.entry_size, tables_size, "group"),
            checked_span(block_device_desc.offset, block_device_desc.num_entries, block_device_desc.entry_size, tables_size, "block-device"),
        ]
    )
    for previous, current in zip(spans, spans[1:]):
        if previous[1] > current[0]:
            raise ValueError("metadata tables overlap")

    partitions = tuple(
        Partition(decode_name(entry[:36], "partition name"), *struct.unpack_from("<IIII", entry, 36))
        for entry in parse_entries(tables, partition_desc, 52, "partition")
    )
    extents = tuple(
        Extent(*struct.unpack("<QIQI", entry))
        for entry in parse_entries(tables, extent_desc, 24, "extent")
    )
    groups = tuple(
        Group(decode_name(entry[:36], "group name"), *struct.unpack_from("<IQ", entry, 36))
        for entry in parse_entries(tables, group_desc, 48, "group")
    )
    block_devices = tuple(
        BlockDevice(
            *struct.unpack_from("<QIIQ", entry, 0),
            decode_name(entry[24:60], "block-device partition name"),
            struct.unpack_from("<I", entry, 60)[0],
        )
        for entry in parse_entries(tables, block_device_desc, 64, "block-device")
    )

    if not block_devices:
        raise ValueError("metadata contains no block devices")
    for partition in partitions:
        if partition.first_extent_index + partition.num_extents > len(extents):
            raise ValueError(f"partition {partition.name} has invalid extent range")
        if partition.group_index >= len(groups):
            raise ValueError(f"partition {partition.name} has invalid group index")
    for extent in extents:
        if extent.target_type not in (TARGET_LINEAR, TARGET_ZERO):
            raise ValueError(f"unsupported extent target type: {extent.target_type}")
        if extent.target_type == TARGET_LINEAR:
            if extent.target_source >= len(block_devices):
                raise ValueError("linear extent has invalid block-device index")
            device = block_devices[extent.target_source]
            end_sector = extent.target_data + extent.num_sectors
            if extent.target_data < device.first_logical_sector:
                raise ValueError("linear extent starts before first logical sector")
            if end_sector > device.size // SECTOR_SIZE:
                raise ValueError("linear extent exceeds block device")

    used_names = [partition.name for partition in partitions]
    if len(used_names) != len(set(used_names)):
        raise ValueError("duplicate logical partition name")

    consumed = header_size + tables_size
    return Metadata(
        major,
        minor,
        header_size,
        tables_size,
        partitions,
        extents,
        groups,
        block_devices,
        raw[:consumed],
    )


def load_metadata(stream) -> tuple[Geometry, Metadata]:
    stream.seek(0, os.SEEK_END)
    image_size = stream.tell()
    stream.seek(GEOMETRY_OFFSET)
    primary_geometry_raw = read_exact(stream, GEOMETRY_BLOCK_SIZE)
    backup_geometry_raw = read_exact(stream, GEOMETRY_BLOCK_SIZE)
    primary_geometry = parse_geometry(primary_geometry_raw, "primary")
    backup_geometry = parse_geometry(backup_geometry_raw, "backup")
    if primary_geometry != backup_geometry:
        raise ValueError("primary and backup geometry differ")

    geometry = primary_geometry
    metadata_base = GEOMETRY_OFFSET + 2 * GEOMETRY_BLOCK_SIZE
    backup_base = metadata_base + geometry.metadata_slot_count * geometry.metadata_max_size
    metadata_end = backup_base + geometry.metadata_slot_count * geometry.metadata_max_size
    if metadata_end > image_size:
        raise ValueError("metadata regions exceed image")

    parsed_slots: list[tuple[str, Metadata]] = []
    for copy_name, base in (("primary", metadata_base), ("backup", backup_base)):
        for slot in range(geometry.metadata_slot_count):
            stream.seek(base + slot * geometry.metadata_max_size)
            slot_raw = read_exact(stream, geometry.metadata_max_size)
            parsed_slots.append(
                (
                    f"{copy_name} slot {slot}",
                    parse_metadata(slot_raw, geometry.metadata_max_size, f"{copy_name} slot {slot}"),
                )
            )

    selected = parsed_slots[0][1]
    for label, candidate in parsed_slots[1:]:
        if candidate.raw != selected.raw:
            raise ValueError(f"{label} differs from primary slot 0")
    for device in selected.block_devices:
        if device.size > image_size:
            raise ValueError(f"block device {device.partition_name} exceeds image size")
    return geometry, selected


def partition_size(metadata: Metadata, partition: Partition) -> int:
    subset = metadata.extents[
        partition.first_extent_index : partition.first_extent_index + partition.num_extents
    ]
    return sum(extent.num_sectors for extent in subset) * SECTOR_SIZE


def extract_partition(stream, metadata: Metadata, partition: Partition, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    expected_size = partition_size(metadata, partition)
    with output_path.open("wb") as output:
        subset = metadata.extents[
            partition.first_extent_index : partition.first_extent_index + partition.num_extents
        ]
        for extent in subset:
            extent_size = extent.num_sectors * SECTOR_SIZE
            if extent.target_type == TARGET_ZERO:
                output.seek(extent_size, os.SEEK_CUR)
                continue
            stream.seek(extent.target_data * SECTOR_SIZE)
            remaining = extent_size
            while remaining:
                chunk = read_exact(stream, min(4 * 1024 * 1024, remaining))
                output.write(chunk)
                remaining -= len(chunk)
        output.truncate(expected_size)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--extract", action="append", default=[], metavar="NAME=PATH")
    args = parser.parse_args()

    try:
        with args.image.open("rb") as stream:
            geometry, metadata = load_metadata(stream)
            print(f"metadata_version={metadata.major}.{metadata.minor}")
            print(f"metadata_max_size={geometry.metadata_max_size}")
            print(f"metadata_slot_count={geometry.metadata_slot_count}")
            print(f"logical_block_size={geometry.logical_block_size}")
            for index, device in enumerate(metadata.block_devices):
                print(
                    f"block_device[{index}]={device.partition_name} "
                    f"size={device.size} first_sector={device.first_logical_sector}"
                )
            by_name = {partition.name: partition for partition in metadata.partitions}
            for partition in metadata.partitions:
                print(
                    f"partition={partition.name} size={partition_size(metadata, partition)} "
                    f"extents={partition.num_extents} group={metadata.groups[partition.group_index].name}"
                )

            for request in args.extract:
                if "=" not in request:
                    raise ValueError("--extract must use NAME=PATH")
                name, output_text = request.split("=", 1)
                if name not in by_name:
                    raise ValueError(f"unknown logical partition: {name}")
                output_path = Path(output_text)
                extract_partition(stream, metadata, by_name[name], output_path)
                print(f"extracted={name} path={output_path} size={output_path.stat().st_size}")
    except (OSError, ValueError, struct.error, shutil.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
