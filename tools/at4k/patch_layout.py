"""Apply hash-pinned small-screen edits to a fresh decoded AT4K 1.2 tree."""
import argparse
import hashlib
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]
BASE_SHA = "700276cb79c1e11e974c3fc10ab2edebbb2d381e5af8c60a241b52d3f6e039af"
WALLPAPER_SHA = "0d99ad08346620e240fa6eb7e765bb55996d4a311c8141a209626e08cad88997"


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError(f"Expected unique patch context: {before[:100]!r}")
    return text.replace(before, after, 1)


def patch_method(text, name, edit):
    matches = list(re.finditer(r"(?ms)^\.method [^\n]* " + re.escape(name) +
                              r"\([^\n]*\n.*?^\.end method$", text))
    if len(matches) != 1:
        raise ValueError(f"Expected one method {name}")
    match = matches[0]
    return text[:match.start()] + edit(match[0]) + text[match.end():]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("decoded", type=Path)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--wallpaper", type=Path, default=ROOT /
                        "android/h700-android10/device/roc/rgsp/wallpapers/IMG_3111.jpg")
    args = parser.parse_args()
    if hashlib.sha256(args.source.read_bytes()).hexdigest() != BASE_SHA:
        raise ValueError("Expected the pristine layout baseline APK")
    if hashlib.sha256(args.wallpaper.read_bytes()).hexdigest() != WALLPAPER_SHA:
        raise ValueError("Bundled default wallpaper does not match the selected original")
    root = args.decoded / "smali"
    path = root / "R3/T5.smali"
    text = path.read_text()
    text = replace_once(text, """    invoke-static {v11, v1}, Lr4/a;->P(LZ/o;Ls/D0;)LZ/o;

    move-result-object v2
""", """    invoke-static {v11, v1}, Lr4/a;->P(LZ/o;Ls/D0;)LZ/o;

    move-result-object v2

    iget-object v3, v0, LR3/T5;->A:Landroid/content/Context;

    invoke-static {v3, v2}, Lcom/overdevs/at4k/RgspLayout;->liftApps(Landroid/content/Context;LZ/o;)LZ/o;

    move-result-object v2
""")
    text = replace_once(text, """    invoke-static {v4, v2}, Landroidx/compose/foundation/layout/d;->e(LZ/o;F)LZ/o;

    move-result-object v2

    sget-object v5, LZ/b;->j:LZ/g;
""", """    invoke-static {v4, v2}, Landroidx/compose/foundation/layout/d;->e(LZ/o;F)LZ/o;

    move-result-object v2

    iget-object v5, v0, LR3/T5;->A:Landroid/content/Context;

    invoke-static {v5, v2}, Lcom/overdevs/at4k/RgspLayout;->restoreToolbar(Landroid/content/Context;LZ/o;)LZ/o;

    move-result-object v2

    sget-object v5, LZ/b;->j:LZ/g;
""")
    path.write_text(text)
    path = root / "R3/J7.smali"
    text = path.read_text()

    def categories(method):
        return replace_once(method, """    int-to-float v9, v9

    invoke-static {v8, v9, v9, v9, v9}, Landroidx/compose/foundation/layout/a;->l(LZ/o;FFFF)LZ/o;""",
                            """    invoke-static {v10}, Lr4/a;->I(LN/p;)Ls/D0;

    move-result-object v9

    invoke-static {v8, v9}, Lr4/a;->P(LZ/o;Ls/D0;)LZ/o;

    move-result-object v8

    const/16 v9, 0xc

    int-to-float v9, v9

    invoke-static {v8, v9, v9, v9, v9}, Landroidx/compose/foundation/layout/a;->l(LZ/o;FFFF)LZ/o;""")

    def subpages(method):
        return replace_once(method, """    const/16 v1, 0x20

    int-to-float v1, v1

    invoke-static {v0, v1, v1, v1, v1}, Landroidx/compose/foundation/layout/a;->l(LZ/o;FFFF)LZ/o;""",
                            """    const/16 v1, 0xc

    int-to-float v1, v1

    invoke-static {v0, v1, v1, v1, v1}, Landroidx/compose/foundation/layout/a;->l(LZ/o;FFFF)LZ/o;""")

    text = patch_method(text, "G", categories)
    text = patch_method(text, "B", subpages)
    path.write_text(text)
    shutil.copyfile(Path(__file__).with_name("RgspLayout.smali"),
                    root / "com/overdevs/at4k/RgspLayout.smali")
    path = root / "com/overdevs/at4k/MainActivity.smali"
    text = replace_once(path.read_text(), """    invoke-super {p0, p1}, Lc/k;->onCreate(Landroid/os/Bundle;)V
""", """    invoke-super {p0, p1}, Lc/k;->onCreate(Landroid/os/Bundle;)V

    invoke-static {p0}, Lcom/overdevs/at4k/RgspDefaults;->seed(Landroid/content/Context;)V
""")
    path.write_text(text)
    shutil.copyfile(Path(__file__).with_name("RgspDefaults.smali"),
                    root / "com/overdevs/at4k/RgspDefaults.smali")
    raw = args.decoded / "res/raw"
    raw.mkdir(exist_ok=True)
    shutil.copyfile(args.wallpaper, raw / "rgsp_wallpaper.jpg")
    print("PATCHED: dock, menus, bundled wallpaper and first-launch custom image theme")


if __name__ == "__main__":
    main()
