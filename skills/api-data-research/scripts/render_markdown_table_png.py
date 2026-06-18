#!/usr/bin/env python3
import argparse
import os
import re
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:
    raise SystemExit("Missing dependency: Pillow. Install with `python3 -m pip install pillow`.") from exc


def load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def split_md_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]

    cells: list[str] = []
    current: list[str] = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line) and line[i + 1] == "|":
            current.append("|")
            i += 2
            continue
        if ch == "|":
            cells.append("".join(current).strip())
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    cells.append("".join(current).strip())
    return cells


def is_separator(line: str) -> bool:
    cells = split_md_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c.strip()) for c in cells)


def extract_table(markdown: str, heading: str | None) -> list[list[str]]:
    lines = markdown.splitlines()
    start = 0
    if heading:
        for i, line in enumerate(lines):
            if line.lstrip("# ").strip() == heading.strip():
                start = i + 1
                break
        else:
            raise SystemExit(f"Heading not found: {heading}")

    table_lines: list[str] = []
    in_table = False
    for line in lines[start:]:
        if line.strip().startswith("|") and "|" in line.strip()[1:]:
            in_table = True
            table_lines.append(line)
        elif in_table:
            break

    if len(table_lines) < 2:
        raise SystemExit("No Markdown table found after heading")

    rows = [split_md_row(line) for line in table_lines if not is_separator(line)]
    width = max(len(row) for row in rows)
    return [row + [""] * (width - len(row)) for row in rows]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, font: ImageFont.FreeTypeFont) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text).split("\n"):
        cur = ""
        for ch in paragraph:
            test = cur + ch
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] > max_width and cur:
                lines.append(cur)
                cur = ch
            else:
                cur = test
        lines.append(cur)
    return lines or [""]


def ellipsize_lines(lines: list[str], limit: int) -> list[str]:
    if len(lines) <= limit:
        return lines
    if limit <= 0:
        return []
    if limit == 1:
        return ["..."]
    return lines[: limit - 1] + ["..."]


def calculate_layout(
    draw: ImageDraw.ImageDraw,
    rows: list[list[str]],
    col_widths: list[int],
    row_height: int,
    max_row_height: int,
    body_font: ImageFont.FreeTypeFont,
    first_col_font: ImageFont.FreeTypeFont,
    body_font_size: int,
) -> tuple[list[int], list[list[list[str]]], bool]:
    line_h = max(24, body_font_size + 7)
    row_heights: list[int] = []
    wrapped_rows: list[list[list[str]]] = []
    clipped = False

    for row in rows[1:]:
        wrapped_cells: list[list[str]] = []
        required = row_height
        for i, cell in enumerate(row):
            fnt = first_col_font if i == 0 else body_font
            lines = wrap_text(draw, cell, col_widths[i] - 28, fnt)
            wrapped_cells.append(lines)
            required = max(required, len(lines) * line_h + 40)

        actual = required
        if max_row_height > 0 and required > max_row_height:
            actual = max(row_height, max_row_height)
            line_limit = max(1, (actual - 28) // line_h)
            wrapped_cells = [ellipsize_lines(lines, line_limit) for lines in wrapped_cells]
            clipped = True
        row_heights.append(actual)
        wrapped_rows.append(wrapped_cells)

    return row_heights, wrapped_rows, clipped


def render(
    rows: list[list[str]],
    output: Path,
    title: str,
    subtitle: str,
    width: int,
    row_height: int,
    first_col_width: int,
    body_font_size: int,
    note: str,
    max_row_height: int,
    max_image_height: int,
) -> None:
    margin_x = 72
    title_h = 118
    footer_h = 60
    header_h = 72
    title_font = load_font(42)
    sub_font = load_font(23)
    header_font = load_font(23)
    body_font = load_font(body_font_size)
    first_col_font = load_font(body_font_size + 2)
    note_font = load_font(18)

    text = "#1f2937"
    muted = "#4b5563"
    border = "#d9e1ea"
    header_bg = "#1f4e79"
    first_col_bg = "#eef4fb"
    accent = "#0f766e"

    col_count = len(rows[0])
    min_width = margin_x * 2 + first_col_width + max(0, col_count - 1) * 80
    if width < min_width:
        raise SystemExit(
            f"--width is too small for {col_count} columns. Minimum is {min_width}px "
            "or reduce --first-col-width / column count."
        )

    if col_count == 1:
        col_widths = [width - margin_x * 2]
    else:
        first = first_col_width
        remaining = width - margin_x * 2 - first
        col_widths = [first] + [remaining // (col_count - 1)] * (col_count - 1)
        col_widths[-1] += width - margin_x * 2 - sum(col_widths)

    probe = Image.new("RGB", (width, 10), "#ffffff")
    probe_draw = ImageDraw.Draw(probe)
    row_heights, wrapped_rows, clipped = calculate_layout(
        probe_draw,
        rows,
        col_widths,
        row_height,
        max_row_height,
        body_font,
        first_col_font,
        body_font_size,
    )
    height = title_h + header_h + sum(row_heights) + footer_h
    if max_image_height > 0 and height > max_image_height:
        raise SystemExit(
            f"Rendered image would be {height}px high, exceeding --max-image-height={max_image_height}. "
            "Create a shorter picture-friendly table, reduce --row-height / --body-font-size, "
            "or raise --max-image-height."
        )

    img = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(img)
    draw.text((margin_x, 32), title, fill=text, font=title_font)
    draw.text((margin_x, 88), subtitle, fill=muted, font=sub_font)

    y = title_h
    x = margin_x
    for i, cell in enumerate(rows[0]):
        w = col_widths[i]
        draw.rectangle([x, y, x + w, y + header_h], fill=header_bg, outline=border)
        header_lines = ellipsize_lines(wrap_text(draw, cell, w - 28, header_font), 2)
        cy = y + 14
        for line in header_lines:
            draw.text((x + 14, cy), line, fill="#ffffff", font=header_font)
            cy += 26
        x += w

    y += header_h
    line_h = max(24, body_font_size + 7)
    for row, wrapped_cells, actual_row_height in zip(rows[1:], wrapped_rows, row_heights):
        x = margin_x
        for i, cell in enumerate(row):
            w = col_widths[i]
            fill = first_col_bg if i == 0 else "#ffffff"
            draw.rectangle([x, y, x + w, y + actual_row_height], fill=fill, outline=border)
            fnt = first_col_font if i == 0 else body_font
            color = accent if i == 0 else text
            cy = y + 20
            for line in wrapped_cells[i]:
                draw.text((x + 14, cy), line, fill=color, font=fnt)
                cy += line_h
            x += w
        y += actual_row_height

    draw.text(
        (margin_x, height - 38),
        note,
        fill=muted,
        font=note_font,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output)
    if clipped:
        print("Warning: some table cells were clipped. Increase --max-row-height or omit it to render full text.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a Markdown table under a heading to PNG.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--heading", default=None)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--title", default="API 数据方案调研")
    parser.add_argument("--subtitle", default=None)
    parser.add_argument("--width", default=2200, type=int)
    parser.add_argument("--row-height", default=150, type=int, help="Minimum body row height.")
    parser.add_argument(
        "--max-row-height",
        default=0,
        type=int,
        help="Optional maximum body row height. 0 means no cap; capped cells end with ellipsis.",
    )
    parser.add_argument(
        "--max-image-height",
        default=16000,
        type=int,
        help="Abort if rendered image exceeds this height. 0 disables the guard.",
    )
    parser.add_argument("--first-col-width", default=180, type=int)
    parser.add_argument("--body-font-size", default=20, type=int)
    parser.add_argument(
        "--note",
        default="注：如涉及第三方运营年限，优先写明采用公司成立年、域名注册年或最早公开文档年。",
    )
    args = parser.parse_args()

    markdown = args.input.read_text(encoding="utf-8")
    rows = extract_table(markdown, args.heading)
    subtitle = args.subtitle or args.heading or "能力矩阵"
    render(
        rows,
        args.output,
        args.title,
        subtitle,
        args.width,
        args.row_height,
        args.first_col_width,
        args.body_font_size,
        args.note,
        args.max_row_height,
        args.max_image_height,
    )
    print(args.output)


if __name__ == "__main__":
    main()
