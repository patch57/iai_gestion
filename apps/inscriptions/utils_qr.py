import io
import base64

def generer_qr_code_data_uri(url_ou_texte):
    """
    Génère un QR Code sous forme de Data URI Base64 ou URL d'API
    à afficher directement dans le template HTML (<img src="...">)
    """
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(url_ou_texte)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#047857", back_color="white")
        
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        b64_img = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{b64_img}"
    except ImportError:
        try:
            from reportlab.graphics.shapes import Drawing
            from reportlab.graphics.barcode.qr import QrCodeWidget
            from reportlab.graphics import renderPM
            
            qr_widget = QrCodeWidget(url_ou_texte)
            bounds = qr_widget.getBounds()
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            d = Drawing(160, 160, transform=[160/width, 0, 0, 160/height, 0, 0])
            d.add(qr_widget)
            
            buffer = io.BytesIO()
            renderPM.drawToFile(d, buffer, fmt='PNG')
            b64_img = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return f"data:image/png;base64,{b64_img}"
        except Exception:
            import urllib.parse
            encoded = urllib.parse.quote(url_ou_texte)
            return f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&color=047857&data={encoded}"
