import io
import qrcode
from PIL import Image, ImageDraw
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask

_FG = (46, 90, 58)    # #2e5a3a — forest green
_BG = (255, 255, 255)

_COLOR_MASK = SolidFillColorMask(back_color=_BG, front_color=_FG)


def _draw_rounded_finders(img, module_count, box_size, border):
    """Redraw the three finder patterns with rounded corners."""
    draw = ImageDraw.Draw(img)
    fp = 7 * box_size       # finder size in pixels
    bp = border * box_size  # border offset in pixels
    r = int(box_size * 1.5) # corner radius

    corners = [
        (bp, bp),
        (bp + (module_count - 7) * box_size, bp),
        (bp, bp + (module_count - 7) * box_size),
    ]

    for fx, fy in corners:
        # Erase the square finder the library drew
        draw.rectangle([fx, fy, fx + fp - 1, fy + fp - 1], fill=_BG)
        # Outer ring (dark)
        draw.rounded_rectangle([fx, fy, fx + fp - 1, fy + fp - 1], radius=r, fill=_FG)
        # Middle ring (light)
        s = box_size
        draw.rounded_rectangle(
            [fx + s, fy + s, fx + fp - s - 1, fy + fp - s - 1],
            radius=max(1, r - s // 2), fill=_BG,
        )
        # Centre dot (dark)
        s2 = 2 * box_size
        draw.rounded_rectangle(
            [fx + s2, fy + s2, fx + fp - s2 - 1, fy + fp - s2 - 1],
            radius=max(1, r - s), fill=_FG,
        )

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

    styled = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=_COLOR_MASK,
    )

    # Save styled image to PIL for post-processing
    tmp = io.BytesIO()
    styled.save(tmp, format='PNG')
    tmp.seek(0)
    img = Image.open(tmp).copy()

    img = _draw_rounded_finders(img, module_count, box_size, border)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.read()
