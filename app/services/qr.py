import base64
import io
import os

import qrcode


def qr_image_data_uri(token: str) -> str:
    base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    image = qrcode.make(f"{base_url}/validator?code={token}")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
