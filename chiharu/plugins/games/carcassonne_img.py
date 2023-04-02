import json
from PIL import Image, ImageDraw, ImageFont

if __name__ == "__main__":
    from pathlib import Path
    with open(Path(__file__).parent / "carcassonne.json", encoding="utf-8") as f:
        pack = json.load(f)
    path = Path("I:/Temp/")
    tiles = pack["packs"][0]["tiles"]
    img = Image.new("RGBA", (64 * 5, 64 * 5), "white")
    pos = lambda i: ((i % 5) * 64, (i // 5) * 64)
    for tile in tiles:
        dr = ImageDraw.Draw(img)
        poslu = pos(tile["id"])