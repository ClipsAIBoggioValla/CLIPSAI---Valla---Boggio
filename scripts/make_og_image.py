"""Genera la imagen Open Graph de la landing pública de ClipsAI (Issue 32).

Salida: 1200x630 PNG con la paleta Cyber-Tech Dark (#0B0F17, #121824, #B4F105).
Uso:    python3 scripts/make_og_image.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

WIDTH, HEIGHT = 1200, 630
BG = "#0B0F17"
CARD = "#121824"
LIME = "#B4F105"
TEXT = "#F1F5F9"
SECONDARY = "#94A3B8"
BORDER = (255, 255, 255, 16)

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    REPO_ROOT / "frontend_react" / "public" / "og-clipsai.png",
    REPO_ROOT / "frontend_vue" / "public" / "og-clipsai.png",
]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def glow(base: Image.Image, center: tuple[int, int], radius: int, color: tuple[int, int, int], alpha: int) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x, y = center
    draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=(*color, alpha))
    blurred = layer.filter(ImageFilter.GaussianBlur(radius // 2))
    base.alpha_composite(blurred)


def build() -> Image.Image:
    image = Image.new("RGBA", (WIDTH, HEIGHT), BG)
    glow(image, (200, 90), 420, (180, 241, 5), 46)
    glow(image, (1080, 600), 360, (16, 185, 129), 34)

    draw = ImageDraw.Draw(image)

    # Grilla de fondo
    for x in range(0, WIDTH, 64):
        draw.line([(x, 0), (x, HEIGHT)], fill=(255, 255, 255, 6), width=1)
    for y in range(0, HEIGHT, 64):
        draw.line([(0, y), (WIDTH, y)], fill=(255, 255, 255, 6), width=1)

    # Marca: asterisco dibujado (no depende del glifo de la fuente) + wordmark
    draw.line([(108, 58), (108, 106)], fill=LIME, width=6)
    draw.line([(83, 72), (133, 92)], fill=LIME, width=6)
    draw.line([(133, 72), (83, 92)], fill=LIME, width=6)
    draw.text((152, 66), "clipsai", font=font(34, bold=True), fill=TEXT)

    # Badge
    badge = "IA · AUDIO · AUTOPUBLICACIÓN"
    draw.rounded_rectangle([80, 150, 80 + 22 * len(badge) + 44, 194], radius=22, fill=(180, 241, 5, 34), outline=(180, 241, 5, 110), width=2)
    draw.text((102, 160), badge, font=font(20, bold=True), fill=LIME)

    # Titular
    draw.text((80, 228), "De un video largo a", font=font(58, bold=True), fill=TEXT)
    draw.text((80, 300), "clips que se publican solos", font=font(58, bold=True), fill=LIME)

    # Bajada
    draw.text((80, 386), "Corte 9:16 · subtítulos ASS palabra por palabra · YouTube, Instagram y TikTok", font=font(24), fill=SECONDARY)

    # CTA
    draw.rounded_rectangle([80, 452, 348, 524], radius=16, fill=LIME)
    draw.text((112, 472), "Probar gratis →", font=font(28, bold=True), fill="#080C14")

    # Mock de clip vertical
    card_x, card_y, card_w, card_h = 880, 96, 240, 428
    draw.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=28, fill=CARD, outline=(180, 241, 5, 90), width=2)
    draw.rounded_rectangle([card_x + 22, card_y + 24, card_x + 118, card_y + 56], radius=16, fill=(180, 241, 5, 40))
    draw.text((card_x + 34, card_y + 30), "SCORE 9.1", font=font(18, bold=True), fill=LIME)
    draw.text((card_x + 150, card_y + 30), "0:46", font=font(18, bold=True), fill=SECONDARY)

    # Forma de onda
    heights = [26, 44, 62, 38, 74, 96, 58, 82, 46, 68, 100, 54, 36, 72, 88, 42, 64, 30]
    bar_x = card_x + 22
    for index, height in enumerate(heights):
        y0 = card_y + 250 - height
        draw.rounded_rectangle([bar_x, y0, bar_x + 8, card_y + 250], radius=4, fill=(180, 241, 5, 200 if index % 2 else 120))
        bar_x += 11

    # Subtítulo quemado
    draw.rounded_rectangle([card_x + 22, card_y + 286, card_x + card_w - 22, card_y + 340], radius=10, fill=(8, 12, 20, 220))
    draw.text((card_x + 36, card_y + 300), "nadie te dice", font=font(22, bold=True), fill=TEXT)
    draw.text((card_x + 36, card_y + 320), "ESTO", font=font(22, bold=True), fill=LIME)

    # Barra de progreso
    draw.rounded_rectangle([card_x + 22, card_y + 366, card_x + card_w - 22, card_y + 374], radius=4, fill=(255, 255, 255, 26))
    draw.rounded_rectangle([card_x + 22, card_y + 366, card_x + 22 + 152, card_y + 374], radius=4, fill=LIME)

    for row in range(3):
        y = card_y + 388 + row * 14
        draw.rounded_rectangle([card_x + 22, y, card_x + 40, y + 6], radius=3, fill=(180, 241, 5, 220))

    return image.convert("RGB")


def main() -> None:
    image = build()
    for target in TARGETS:
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, "PNG", optimize=True)
        print(f"OK {target.relative_to(REPO_ROOT)} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()