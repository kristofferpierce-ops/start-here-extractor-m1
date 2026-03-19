from __future__ import annotations

import struct
from pathlib import Path
from typing import List

from ..types import StrictZipValidationResult
from ..utils import suspicious_zip_member

_CEN_SIG = 0x02014B50
_LFH_SIG = 0x04034B50
_EOCD_STRUCT = struct.Struct("<IHHHHIIH")
_CEN_STRUCT = struct.Struct("<IHHHHHHIIIHHHHHII")
_LFH_STRUCT = struct.Struct("<IHHHHHIIIHH")
_MAX_EOCD_SCAN = 65557
_FLAG_UTF8 = 0x800
_FLAG_DATA_DESCRIPTOR = 0x08


def _decode_name(raw: bytes, flag_bits: int) -> str:
    if flag_bits & _FLAG_UTF8:
        return raw.decode("utf-8", errors="replace")
    return raw.decode("cp437", errors="replace")


def _find_eocd(data: bytes) -> int | None:
    start = max(0, len(data) - _MAX_EOCD_SCAN)
    for idx in range(len(data) - 4, start - 1, -1):
        if data[idx : idx + 4] == b"PK\x05\x06":
            return idx
    return None


def strict_validate_zip(zip_path: Path, *, strict_mode: bool = True) -> StrictZipValidationResult:
    flags: List[str] = []
    if not strict_mode:
        return StrictZipValidationResult(
            strict_mode=False,
            ok=True,
            suspicious=False,
            flags=[],
            reason="strict-mode-disabled",
        )

    try:
        data = zip_path.read_bytes()
    except Exception as exc:
        return StrictZipValidationResult(
            strict_mode=True,
            ok=False,
            suspicious=True,
            flags=[f"strict-validator-read-failed:{type(exc).__name__}"],
            reason="read-failed",
        )

    eocd_offset = _find_eocd(data)
    if eocd_offset is None:
        return StrictZipValidationResult(
            strict_mode=True,
            ok=False,
            suspicious=True,
            flags=["missing-eocd"],
            reason="missing-eocd",
        )

    try:
        (_sig, _disk_number, _cd_start_disk, _entries_this_disk, total_entries, cd_size, cd_offset, comment_len) = _EOCD_STRUCT.unpack_from(data, eocd_offset)
    except struct.error:
        return StrictZipValidationResult(
            strict_mode=True,
            ok=False,
            suspicious=True,
            flags=["truncated-eocd"],
            reason="truncated-eocd",
        )

    if eocd_offset + _EOCD_STRUCT.size + comment_len != len(data):
        flags.append("eocd-comment-length-mismatch")
    if cd_offset + cd_size > len(data):
        return StrictZipValidationResult(
            strict_mode=True,
            ok=False,
            suspicious=True,
            flags=flags + ["central-directory-out-of-range"],
            reason="central-directory-out-of-range",
        )

    cursor = cd_offset
    exact_names: dict[str, int] = {}

    for _ in range(total_entries):
        if cursor + _CEN_STRUCT.size > len(data):
            flags.append("central-directory-truncated")
            break

        cen = _CEN_STRUCT.unpack_from(data, cursor)
        if cen[0] != _CEN_SIG:
            flags.append("central-directory-signature-mismatch")
            break

        flag_bits = cen[3]
        compression_type = cen[4]
        crc = cen[7]
        compressed_size = cen[8]
        file_size = cen[9]
        name_len = cen[10]
        extra_len = cen[11]
        comment_len = cen[12]
        local_offset = cen[16]

        name_start = cursor + _CEN_STRUCT.size
        name_end = name_start + name_len
        extra_end = name_end + extra_len
        comment_end = extra_end + comment_len
        if comment_end > len(data):
            flags.append("central-directory-record-overflow")
            break

        name_raw = data[name_start:name_end]
        name = _decode_name(name_raw, flag_bits)
        exact_names[name] = exact_names.get(name, 0) + 1

        suspicious, reasons = suspicious_zip_member(name)
        if suspicious:
            for reason in reasons:
                flags.append(f"suspicious-member-path:{reason}:{name}")

        if local_offset + _LFH_STRUCT.size > len(data):
            flags.append(f"local-header-out-of-range:{name}")
            cursor = comment_end
            continue

        lfh = _LFH_STRUCT.unpack_from(data, local_offset)
        if lfh[0] != _LFH_SIG:
            flags.append(f"local-header-signature-mismatch:{name}")
            cursor = comment_end
            continue

        local_flag_bits = lfh[2]
        local_compression_type = lfh[3]
        local_crc = lfh[6]
        local_compressed_size = lfh[7]
        local_file_size = lfh[8]
        local_name_len = lfh[9]
        local_extra_len = lfh[10]

        local_name_start = local_offset + _LFH_STRUCT.size
        local_name_end = local_name_start + local_name_len
        local_extra_end = local_name_end + local_extra_len
        if local_extra_end > len(data):
            flags.append(f"local-header-record-overflow:{name}")
            cursor = comment_end
            continue

        local_name_raw = data[local_name_start:local_name_end]
        local_name = _decode_name(local_name_raw, local_flag_bits)

        if name != local_name:
            flags.append(f"central-local-name-mismatch:{name}")
        if compression_type != local_compression_type:
            flags.append(f"central-local-compression-mismatch:{name}")
        if bool(flag_bits & _FLAG_DATA_DESCRIPTOR) != bool(local_flag_bits & _FLAG_DATA_DESCRIPTOR):
            flags.append(f"central-local-flag-mismatch:{name}")

        if flag_bits & _FLAG_DATA_DESCRIPTOR:
            flags.append(f"data-descriptor-ambiguity:{name}")
        else:
            if crc != local_crc:
                flags.append(f"central-local-crc-mismatch:{name}")
            if compressed_size != local_compressed_size:
                flags.append(f"central-local-compressed-size-mismatch:{name}")
            if file_size != local_file_size:
                flags.append(f"central-local-size-mismatch:{name}")

        if local_offset >= cd_offset:
            flags.append(f"local-header-offset-overlaps-directory:{name}")

        cursor = comment_end

    for name, count in exact_names.items():
        if count > 1:
            flags.append(f"duplicate-entry-name:{name}")

    unique_flags = sorted(set(flags))
    ok = len(unique_flags) == 0
    return StrictZipValidationResult(
        strict_mode=True,
        ok=ok,
        suspicious=not ok,
        flags=unique_flags,
        reason="ok" if ok else unique_flags[0],
    )
