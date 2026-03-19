from pathlib import Path
import struct
import zipfile

tmp = Path("mismatch.zip")

with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_STORED) as z:
    z.writestr("START HERE.TXT", b"hello")

data = bytearray(tmp.read_bytes())
name_len = struct.unpack_from("<H", data, 26)[0]
replacement = b"START THER.TXT"
assert len(replacement) == name_len
start = 30
data[start:start + name_len] = replacement
tmp.write_bytes(data)

print(tmp.resolve())