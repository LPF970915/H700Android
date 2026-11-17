"""Render the host-only preview from the reference model's single catalog.

Writes an HTML fragment only. Does not inspect or modify images or hardware.
"""
import argparse
import json
from pathlib import Path

try:
    from .reference_model import MODEL_CATALOG
except ImportError:
    from reference_model import MODEL_CATALOG


def render_fragment():
    template = Path(__file__).with_name("preview-template.html").read_text(encoding="utf-8")
    token = "__H700_MODEL_CATALOG_JSON__"
    if template.count(token) != 1:
        raise ValueError("preview template must contain exactly one catalog placeholder")
    # ASCII encoding also prevents metadata from closing the inline script tag.
    catalog = json.dumps([model.to_mapping() for model in MODEL_CATALOG],
                         ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")
    return template.replace(token, catalog)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    fragment = render_fragment()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(fragment, encoding="utf-8")
    if args.output.read_text(encoding="utf-8") != fragment:
        raise IOError("preview readback differs")
    print(json.dumps({"output": str(args.output.resolve()), "models": len(MODEL_CATALOG)}))


if __name__ == "__main__":
    main()
