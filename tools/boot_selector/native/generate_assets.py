"""Export the canonical model catalog and a small Noto CJK bitmap subset."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reference_model import DEFAULT_MODEL_ID, MODEL_CATALOG

UI_TEXT = ("选择你的机型分辨率翻盖摇杆是否无单双保存为启动默认，下次跳过此页"
           "启动系统切换机型确认该机型尚未接入，请重新选择←→上下A ")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--license", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(str(args.font), 30, index=2)
    if font.getname() != ("Noto Sans CJK SC", "Regular"):
        raise ValueError("Expected Noto Sans CJK SC Regular, TTC index 2")
    models = [model.to_mapping() for model in MODEL_CATALOG]
    chars = sorted(set(UI_TEXT + "".join(m["label"] for m in models) + "0123456789x?"), key=ord)
    glyphs = []
    for char in chars:
        image = Image.new("L", (32, 40))
        ImageDraw.Draw(image).text((0, 0), char, font=font, fill=255)
        advance = round(font.getlength(char))
        if advance < 1 or advance > 32:
            raise ValueError(f"Glyph advance out of range: {char!r}, {advance}")
        rows = []
        for y in range(40):
            row = 0
            for x in range(32):
                if image.getpixel((x, y)) >= 96:
                    row |= 1 << x
            rows.append(row)
        glyphs.append((ord(char), advance, rows))
    lines = ["/* Generated from canonical MODEL_CATALOG and Noto Sans CJK SC. */",
             "#ifndef ROC_SELECTOR_ASSETS_H", "#define ROC_SELECTOR_ASSETS_H",
             "struct model { const char *id, *label, *geometry; unsigned lid, sticks; };",
             "static const struct model models[] = {"]
    for model in models:
        values = [json.dumps(model[key], ensure_ascii=False) for key in ("model_id", "label", "geometry")]
        lines.append("  {" + ",".join(values) + f",{int(model['lid'])},{model['sticks']}" + "},")
    lines += ["};", f'#define DEFAULT_MODEL_ID "{DEFAULT_MODEL_ID}"',
              "#define MODEL_COUNT (sizeof(models)/sizeof(models[0]))",
              "struct glyph { unsigned codepoint, advance; uint32_t rows[40]; };",
              "static const struct glyph glyphs[] = {"]
    for codepoint, advance, rows in glyphs:
        lines.append("  {" + str(codepoint) + "," + str(advance) + ",{" +
                     ",".join(f"0x{row:08x}u" for row in rows) + "}},")
    lines += ["};", "#endif", ""]
    (args.output / "assets.h").write_text("\n".join(lines), encoding="utf-8")
    (args.output / "FONT-NOTICE.txt").write_bytes(args.license.read_bytes())
    manifest = {"font_sha256": hashlib.sha256(args.font.read_bytes()).hexdigest(),
                "font_name": font.getname(), "font_ttc_index": 2,
                "font_height": 40, "font_pixel_size": 30, "glyphs": len(glyphs),
                "models": models, "default_model_id": DEFAULT_MODEL_ID,
                "assets_sha256": hashlib.sha256((args.output / "assets.h").read_bytes()).hexdigest()}
    (args.output / "assets.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "glyphs": len(glyphs), "models": len(models)}))


if __name__ == "__main__":
    main()
