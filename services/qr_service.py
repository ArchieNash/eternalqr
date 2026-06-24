import io
import os
import qrcode
from PIL import Image, ImageDraw
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers.pil import CircleModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask

_LOGO_PATH = os.path.join(os.path.dirname(__file__), '..', 'static', 'img', 'logo.png')

_FG = (58, 110, 72)    # #3a6e48 — medium forest green
_BG = (247, 243, 236)  # #f7f3ec — warm parchment

_COLOR_MASK = SolidFillColorMask(back_color=_BG, front_color=_FG)


def _load_logo():
    if not os.path.exists(_LOGO_PATH):
        return None
    logo = Image.open(_LOGO_PATH).convert('RGBA')
    bbox = logo.getbbox()
    if bbox:
        logo = logo.crop(bbox)
    return logo


def _draw_bullseye_finders(img, module_count, box_size, border):
    """Replace square finder patterns with concentric-circle (bullseye) style."""
    draw = ImageDraw.Draw(img)
    fp = 7 * box_size       # finder pixel width
    bp = border * box_size  # border offset

    positions = [
        (bp, bp),
        (bp + (module_count - 7) * box_size, bp),
        (bp, bp + (module_count - 7) * box_size),
    ]

    for fx, fy in positions:
        cx, cy = fx + fp // 2, fy + fp // 2
        # Erase the square finder the library drew
        draw.rectangle([fx - 1, fy - 1, fx + fp, fy + fp], fill=_BG)
        # Outer ring (dark)
        r = fp // 2
        draw.ellipse([cx - r, cy - r, cx + r - 1, cy + r - 1], fill=_FG)
        # Middle gap (light) — 5/7 radius
        r2 = fp * 5 // 14
        draw.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], fill=_BG)
        # Centre dot (dark) — 3/7 radius
        r3 = fp * 3 // 14
        draw.ellipse([cx - r3, cy - r3, cx + r3, cy + r3], fill=_FG)

    return img


def generate_qr_png(url: str) -> bytes:
    box_size = 12
    border = 4

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    module_count = qr.modules_count

    kwargs = dict(
        image_factory=StyledPilImage,
        module_drawer=CircleModuleDrawer(),
        color_mask=_COLOR_MASK,
    )
    logo = _load_logo()
    if logo:
        kwargs['embedded_image'] = logo
        kwargs['embedded_image_ratio'] = 0.22

    styled = qr.make_image(**kwargs)

    tmp = io.BytesIO()
    styled.save(tmp, format='PNG')
    tmp.seek(0)
    img = Image.open(tmp).copy()

    img = _draw_bullseye_finders(img, module_count, box_size, border)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.read()
