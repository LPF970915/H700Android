"""Extract inspectable camera frames and luminance samples, without device writes."""
import argparse
import csv
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "out/video-analysis-tools"))
import imageio_ffmpeg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    reader = imageio_ffmpeg.read_frames(
        str(args.video), output_params=["-vf", "scale=360:640"])
    metadata = next(reader)
    width, height = metadata["size"]
    print(json.dumps(metadata), flush=True)
    samples = []
    tiles = []
    rapid_tiles = []
    for index, frame in enumerate(reader):
        rgb = np.frombuffer(frame, np.uint8).reshape(height, width, 3)
        seconds = index / metadata["fps"]
        roi = rgb[110:230, 80:250]
        samples.append((index, seconds, float(rgb.mean()),
                        float(roi.mean()), float(np.percentile(roi, 95))))
        if index % 3 == 0:
            tile = Image.fromarray(rgb[:310]).resize((144, 124))
            ImageDraw.Draw(tile).rectangle((0, 0, 75, 16), fill="black")
            ImageDraw.Draw(tile).text((2, 2), f"{seconds:.2f}s", fill="white")
            rapid_tiles.append(tile)
        if index % 30 == 0:
            image = Image.fromarray(rgb)
            image.save(args.output / f"frame-{index:04d}.jpg")
            tile = image.resize((180, 320))
            ImageDraw.Draw(tile).rectangle((0, 0, 100, 20), fill="black")
            ImageDraw.Draw(tile).text((5, 4), f"{seconds:.2f}s", fill="white")
            tiles.append(tile)
    sheet = Image.new("RGB", (180 * 7, 320 * ((len(tiles) + 6) // 7)), "#333333")
    for index, tile in enumerate(tiles):
        sheet.paste(tile, ((index % 7) * 180, (index // 7) * 320))
    sheet.save(args.output / "contact-sheet.jpg")
    for page in range((len(rapid_tiles) + 79) // 80):
        sheet = Image.new("RGB", (144 * 10, 124 * 8), "#333333")
        for index, tile in enumerate(rapid_tiles[page * 80:(page + 1) * 80]):
            sheet.paste(tile, ((index % 10) * 144, (index // 10) * 124))
        sheet.save(args.output / f"rapid-sheet-{page}.jpg")
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2))
    with (args.output / "frame-luminance.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["frame", "seconds", "mean_rgb", "screen_roi_mean", "screen_roi_p95"])
        writer.writerows(samples)
    print(f"frames={len(samples)} output={args.output}", flush=True)


if __name__ == "__main__":
    main()
