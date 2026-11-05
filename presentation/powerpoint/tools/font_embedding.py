"""Wrap the licensed static TTFs in uncompressed EOT for PowerPoint.

Format: https://www.w3.org/submissions/EOT/#Version01
The complete original font is retained, including characters not in the examples.
Only the bundled, unrestricted TrueType fonts are supported.
"""
import struct


FONTS = {
    "Montserrat": {"regular": "Montserrat-Regular.ttf", "bold": "Montserrat-Bold.ttf",
                   "italic": "Montserrat-Italic.ttf", "boldItalic": "Montserrat-BoldItalic.ttf"},
    "Montserrat Light": {"regular": "Montserrat-Light.ttf"},
    "Montserrat Medium": {"regular": "Montserrat-Medium.ttf"},
    "Montserrat SemiBold": {"regular": "Montserrat-SemiBold.ttf"},
    "JetBrains Mono": {"regular": "JetBrainsMono-Regular.ttf"},
}


def eot(data, family):
    if data[:4] != b"\x00\x01\x00\x00":
        raise ValueError("Expected a static TrueType font")
    tables = {}
    for i in range(struct.unpack_from(">H", data, 4)[0]):
        tag, _, offset, length = struct.unpack_from(">4sIII", data, 12 + 16 * i)
        tables[tag] = data[offset:offset + length]
    if b"fvar" in tables:
        raise ValueError("Use the prepared static font instances")
    os2 = tables[b"OS/2"]
    fs_type = struct.unpack_from(">H", os2, 8)[0]
    if fs_type:
        raise ValueError("Unexpected embedding restriction")
    names = {}
    name = tables[b"name"]
    _, count, strings = struct.unpack_from(">HHH", name)
    for i in range(count):
        platform, encoding, language, ident, length, offset = struct.unpack_from(">6H", name, 6 + 12 * i)
        if (platform, encoding, language) == (3, 1, 0x409):
            names[ident] = name[strings + offset:strings + offset + length].decode("utf-16be")
    if names[1] != family:
        raise ValueError(f"Font family mismatch: {names[1]} != {family}")
    weight = struct.unpack_from(">H", os2, 4)[0]
    italic = struct.unpack_from(">H", os2, 62)[0] & 1
    unicode_ranges = struct.unpack_from(">4I", os2, 42)
    codepages = struct.unpack_from(">2I", os2, 78)
    checksum = struct.unpack_from(">I", tables[b"head"], 8)[0]
    header = bytearray(struct.pack("<4I10sBBIHH11IH", 0, len(data), 0x00020001, 0,
                                  os2[32:42], 1, italic, weight, fs_type, 0x504C,
                                  *unicode_ranges, *codepages, checksum, 0, 0, 0, 0, 0))
    for ident in (1, 2, 5, 4):
        value = names[ident].encode("utf-16le")
        header.extend(struct.pack("<H", len(value)))
        header.extend(value)
        header.extend(b"\x00\x00")
    header.extend(b"\x00\x00")  # No root-string restriction.
    struct.pack_into("<I", header, 0, len(header) + len(data))
    return bytes(header) + data
