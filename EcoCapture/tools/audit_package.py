"""Verify package contents and architecture without executing downloaded files."""
import hashlib
import json
from pathlib import Path
import struct
import zipfile

root = Path(__file__).resolve().parents[1]
dist = root/"dist"
reports = {}
for tag, directory, binary, expected in (
    ("windows-x64", "EcoCapture", "EcoCapture.exe", 0x8664),
    ("linux-arm64", "EcoCapture-linux-arm64", "EcoCapture.arm64", 183),
):
    path = dist/directory/binary
    data = path.read_bytes()
    if tag == "windows-x64":
        assert data[:2] == b"MZ"
        pe = struct.unpack_from("<I", data, 60)[0]
        assert data[pe:pe+4] == b"PE\0\0"
        machine = struct.unpack_from("<H", data, pe+4)[0]
    else:
        assert data[:6] == b"\x7fELF\x02\x01", "Expected 64-bit little-endian ELF"
        machine = struct.unpack_from("<H", data, 18)[0]
    assert machine == expected
    archive = dist/("EcoCapture-0.3.5-"+tag+".zip")
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        names = [n.replace("\\", "/") for n in z.namelist()]
        assert not any("/artifacts/" in n or "/map-cache/" in n or "/settings.json" in n for n in names)
        assert any(n.endswith("/README.md") for n in names)
        assert any(n.endswith("/SYSTEM_REQUIREMENTS.md") for n in names)
        assert any(n.endswith("/licenses/Godot-third-party.txt") for n in names)
        assert any(n.endswith("/licenses/NotoSansJP-OFL.txt") for n in names)
        assert any(n.endswith("/EcoCapture.dll") for n in names)
        entry = next(n for n in z.namelist() if n.replace("\\", "/") == directory+"/"+binary)
        assert hashlib.sha256(z.read(entry)).digest() == hashlib.sha256(data).digest()
    runtime = next((dist/directory).glob("data_*/EcoCapture.runtimeconfig.json"))
    options = json.loads(runtime.read_text())["runtimeOptions"]
    assert "includedFrameworks" in options, "Runtime must be self-contained"
    reports[tag] = {"binary_bytes": len(data), "machine": machine, "binary_sha256": hashlib.sha256(data).hexdigest(),
                    "zip_bytes": archive.stat().st_size, "zip_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                    "archive_entries": len(names), "runtime": options["includedFrameworks"], "passed": True}
(root/"artifacts/package-audit.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
(dist/"SHA256SUMS.txt").write_text("".join(r["zip_sha256"]+"  EcoCapture-0.3.5-"+tag+".zip\n" for tag, r in reports.items()), encoding="ascii")
print(json.dumps(reports, indent=2))
