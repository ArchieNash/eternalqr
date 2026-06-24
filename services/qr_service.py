import io
import os
import qrcode
from PIL import Image
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask

_LOGO_PATH = os.path.join(os.path.dirname(__file__), '..', 'static', 'img', 'logo.png')

# Forest green on white — enough contrast to scan reliably when printed
_COLOR_MASK = SolidFillColorMask(
    back_color=(255, 255, 255),
    front_color=(46, 90, 58),  # #2e5a3a
)


def _load_logo():
    if not os.path.exists(_LOGO_PATH):
        return None
    logo = Image.open(_LOGO_PATH).convert('RGBA')
    # Crop transparent padding so the library centers the actual icon
    bbox = logo.getbbox()
    if bbox:
        logo = logo.crop(bbox)
    return logo


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

    kwargs = dict(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=_COLOR_MASK,
    )
    logo = _load_logo()
    if logo:
        kwargs['embedded_image'] = logo
        kwargs['embedded_image_ratio'] = 0.25

    img = qr.make_image(**kwargs)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.read()
