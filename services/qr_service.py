import io
import os
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer
from PIL import Image

LOGO_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'static', 'img', 'logo.png'))


def _make_logo_with_background(size: int) -> str:
    """
    Load the logo, remove white background, center it on a white rounded-rect,
    and save a temp PNG that StyledPilImage can embed.
    """
    logo = Image.open(LOGO_PATH).convert('RGBA')

    # Make near-white pixels transparent so only the green icon shows
    data = logo.getdata()
    new_data = []
    for r, g, b, a in data:
        if r > 200 and g > 200 and b > 200:
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append((r, g, b, a))
    logo.putdata(new_data)

    # Shrink logo to 80% of the target size, then place on white square
    icon_size = int(size * 0.8)
    logo = logo.resize((icon_size, icon_size), Image.LANCZOS)

    canvas = Image.new('RGBA', (size, size), (255, 255, 255, 255))
    offset = (size - icon_size) // 2
    canvas.paste(logo, (offset, offset), logo)

    tmp = io.BytesIO()
    canvas.save(tmp, format='PNG')
    tmp.seek(0)
    return tmp


def generate_qr_png(url: str) -> bytes:
    """Return a PNG QR code as bytes for the given URL."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=12,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
    )

    # Embed logo manually after generation for full control
    if os.path.exists(LOGO_PATH):
        pil_img = img.get_image().convert('RGBA')
        qr_size = pil_img.size[0]
        logo_size = qr_size * 3 // 10  # logo occupies ~30% of QR width (within H error correction limit)

        logo_buf = _make_logo_with_background(logo_size)
        logo_img = Image.open(logo_buf).convert('RGBA')

        pos = ((qr_size - logo_size) // 2, (qr_size - logo_size) // 2)
        pil_img.paste(logo_img, pos, logo_img)

        buf = io.BytesIO()
        pil_img.save(buf, format='PNG')
        buf.seek(0)
        return buf.read()

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.read()
