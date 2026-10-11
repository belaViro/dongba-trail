"""AI-02 experiment only: pack existing 200 glyphs without dropping candidates.

Not imported by the production app. ASCII IDs are rendered beside each unchanged
128px reference; the existing IDs/glosses remain in the provider text input.
"""

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

COLUMNS = 4
ROWS = 5
TILE_WIDTH = 160
TILE_HEIGHT = 160
PER_SHEET = COLUMNS * ROWS


def build_sheets(references):
    sheets = []
    for start in range(0, len(references), PER_SHEET):
        group = references[start : start + PER_SHEET]
        rows = (len(group) + COLUMNS - 1) // COLUMNS
        canvas = Image.new("RGB", (COLUMNS * TILE_WIDTH, rows * TILE_HEIGHT), "white")
        draw = ImageDraw.Draw(canvas)
        font = ImageFont.load_default(size=16)
        for index, ref in enumerate(group):
            x, y = index % COLUMNS * TILE_WIDTH, index // COLUMNS * TILE_HEIGHT
            draw.rectangle((x, y, x + TILE_WIDTH - 1, y + TILE_HEIGHT - 1), outline="#dddddd")
            # DB1404 IDs are ASCII; reject oversized IDs rather than silently truncate.
            if not ref.character_id.isascii() or draw.textlength(ref.character_id, font) > 152:
                raise ValueError("reference ID cannot fit in the experiment sheet")
            draw.text((x + 4, y + 3), ref.character_id, fill="black", font=font)
            with Image.open(BytesIO(ref.image)) as glyph:
                clean = glyph.convert("RGB")
                if clean.width > 128 or clean.height > 128:
                    raise ValueError("reference dimensions changed")
                canvas.paste(clean, (x + (TILE_WIDTH - clean.width) // 2, y + 25))
        buffer = BytesIO()
        canvas.save(buffer, format="PNG")
        sheets.append((tuple(group), buffer.getvalue()))
    return sheets


def message_content(prompt, image, media_type, references=()):
    from backend.app.volcengine_provider import image_part

    if not references:
        return [{"type": "text", "text": prompt}, image_part(image, media_type)]
    content = [
        {
            "type": "text",
            "text": prompt
            + (
                "\n参考字形以网格对照图提供；每格顶部的DB1404编号只标识该格字形，"
                "不是字形笔画。严格按格内字形与待识别照片比较，返回该格顶部编号。"
            ),
        }
    ]
    for index, (group, png) in enumerate(build_sheets(references), start=1):
        content.append(
            {
                "type": "text",
                "text": f"参考对照图{index}：\n"
                + "\n".join(f"{ref.character_id}（{ref.cn_name}）" for ref in group),
            }
        )
        content.append(image_part(png, "image/png"))
    content.append({"type": "text", "text": "以下是待识别照片（不是参考网格）："})
    content.append(image_part(image, media_type))
    return content
