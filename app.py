from flask import Flask, request, send_file, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import RequestEntityTooLarge
from PIL import Image, UnidentifiedImageError
import os
import io
import zipfile

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max

@app.errorhandler(RequestEntityTooLarge)
def handle_large_upload(e):
    return jsonify({'error': 'Uploaded data is too large. Max 100MB.'}), 413

def format_image(file_stream, mode="Fill", canvas_size=1000):
    img = Image.open(file_stream).convert("RGBA")
    w, h = img.size
    if mode == "Fill":
        scale = max(canvas_size / w, canvas_size / h)
        new_size = (int(w * scale), int(h * scale))
        img = img.resize(new_size, Image.LANCZOS)
        left = (img.width - canvas_size) // 2
        top = (img.height - canvas_size) // 2
        img = img.crop((left, top, left + canvas_size, top + canvas_size))
    else:  # Fit mode
        img.thumbnail((int(canvas_size * 0.92), int(canvas_size * 0.92)), Image.LANCZOS)
        background = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 255))
        offset = ((canvas_size - img.width) // 2, (canvas_size - img.height) // 2)
        background.paste(img, offset, img)
        img = background
    return img.convert("RGB")

@app.route("/format", methods=["POST"])
def format_route():
    if 'images' not in request.files:
        return jsonify({"error": "No images uploaded"}), 400

    images = request.files.getlist("images")
    fill_mode = request.form.get("fill_mode", "Fill")

    zip_stream = io.BytesIO()
    with zipfile.ZipFile(zip_stream, "w") as zipf:
        for file in images:
            if not file.filename:
                continue
            try:
                processed = format_image(file, fill_mode)
            except (UnidentifiedImageError, OSError):
                continue
            base_name, ext = os.path.splitext(file.filename)
            ext = ext.lower().replace('.', '')
            img_format = "JPEG" if ext in ["jpg", "jpeg"] else "PNG"
            buffer = io.BytesIO()
            processed.save(buffer, format=img_format)
            buffer.seek(0)
            zipf.writestr(f"{base_name}_formatted.{ext}", buffer.read())
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
