from flask import Flask, request, send_file, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import RequestEntityTooLarge
from PIL import Image, UnidentifiedImageError
import io
import os
import zipfile

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload

@app.errorhandler(RequestEntityTooLarge)
def handle_large_upload(e):
    return jsonify({'error': 'Uploaded file too large. Max is 100MB'}), 413

def format_image(stream, mode="Fill", size=1000):
    img = Image.open(stream).convert("RGBA")
    w, h = img.size

    if mode == "Fill":
        scale = max(size / w, size / h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        left = (img.width - size) // 2
        top = (img.height - size) // 2
        img = img.crop((left, top, left + size, top + size))
    else:
        img.thumbnail((int(size * 0.92), int(size * 0.92)), Image.LANCZOS)
        background = Image.new("RGBA", (size, size), (255, 255, 255, 255))
        x = (size - img.width) // 2
        y = (size - img.height) // 2
        background.paste(img, (x, y), img)
        img = background

    return img.convert("RGB")

@app.route("/format", methods=["POST"])
def format_endpoint():
    if 'images' not in request.files:
        return jsonify({'error': 'No images uploaded'}), 400

    mode = request.form.get('fill_mode', 'Fill')
    files = request.files.getlist('images')
    zip_stream = io.BytesIO()

    with zipfile.ZipFile(zip_stream, "w") as zipf:
        for file in files:
            if not file.filename:
                continue
            try:
                output = io.BytesIO()
                formatted = format_image(file.stream, mode)
                ext = os.path.splitext(file.filename)[1].lower().strip('.') or 'jpg'
                formatted.save(output, format="JPEG" if ext in ['jpg', 'jpeg'] else 'PNG')
                output.seek(0)
                zipf.writestr(f"{os.path.splitext(file.filename)[0]}_formatted.{ext}", output.read())
            except (UnidentifiedImageError, OSError):
                continue

    zip_stream.seek(0)
    return send_file(
        zip_stream,
        as_attachment=True,
        download_name="formatted_images.zip",
        mimetype="application/zip"
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
