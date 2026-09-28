#!/usr/bin/env python3
"""
PolyView - 3D File Browser Server
Jalankan (dari root project):
    gunicorn -w 2 -b 127.0.0.1:5000 app.server:app
  atau:
    python3 app/server.py  (dev mode, langsung port 5000)

Nginx akan reverse proxy dari port 8080 → 5000.

Konfigurasi (environment variable):
    POLYVIEW_DATA_DIR   folder data yang dijelajahi (default: /data)

Dependensi:
    pip3 install -r requirements.txt
"""

import os
import io
import logging
import zipfile
import mimetypes
from flask import Flask, jsonify, request, send_file, send_from_directory, abort

# ── Konfigurasi ──────────────────────────────────────────────
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR  = os.path.join(PROJECT_DIR, 'static')
ICONS_DIR   = os.path.join(STATIC_DIR, 'icons')
BASE_DIR    = os.environ.get('POLYVIEW_DATA_DIR') or '/data'
# ─────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
log = logging.getLogger('polyview')

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='/static')

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False
    log.warning('Pillow tidak terinstall — file TIF tidak bisa dipreview. '
                'Jalankan: pip3 install pillow')


def safe_path(filepath):
    safe = os.path.realpath(os.path.join(BASE_DIR, filepath))
    base = os.path.realpath(BASE_DIR)
    if safe != base and not safe.startswith(base + os.sep):
        abort(403)
    return safe


def open_tif_with_alpha(path):
    """Buka TIF dengan channel ke-4 'unspecified' (ExtraSamples=0) sebagai RGBA.

    Pillow membuka TIF seperti itu sebagai RGB (raw mode RGBX, channel ke-4 dibuang),
    padahal 3ds Max/Photoshop memakainya sebagai alpha (mask cutout). Jika TIF bukan
    kasus ini, atau pembacaan gagal, kembalikan gambar apa adanya.
    """
    img = Image.open(path)
    rawmodes = {t[3][0] if isinstance(t[3], tuple) else t[3] for t in img.tile}
    if img.mode != 'RGB' or rawmodes != {'RGBX'}:
        return img
    img.close()
    alt = Image.open(path)
    try:
        tiles = []
        for t in alt.tile:
            args = ('RGBA',) + tuple(t[3][1:]) if isinstance(t[3], tuple) else 'RGBA'
            tiles.append(t._replace(args=args) if hasattr(t, '_replace') else (t[0], t[1], t[2], args))
        alt._mode = 'RGBA'  # detail internal Pillow (teruji di Pillow 12.x)
        alt.tile = tiles
        alt.load()
        return alt
    except Exception as e:
        log.warning('TIF alpha fallback ke RGB (%s): %s', os.path.basename(path), e)
        alt.close()
        return Image.open(path)


def get_tree(path, rel=''):
    entries = []
    try:
        items = sorted(os.listdir(path),
                       key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower()))
        for item in items:
            full  = os.path.join(path, item)
            rpath = os.path.join(rel, item).lstrip('/')
            if os.path.isdir(full):
                entries.append({'name': item, 'type': 'folder',
                                 'path': rpath, 'children': get_tree(full, rpath)})
            else:
                ext = os.path.splitext(item)[1].lower().lstrip('.')
                entries.append({'name': item, 'type': 'file', 'ext': ext,
                                 'path': rpath, 'size': os.path.getsize(full)})
    except PermissionError:
        pass
    return entries


@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')

@app.route('/manifest.json')
def manifest():
    return send_from_directory(STATIC_DIR, 'manifest.json', mimetype='application/manifest+json')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(ICONS_DIR, 'favicon.ico')

@app.route('/sw.js')
def service_worker():
    # SW harus served dari root agar scope-nya benar
    resp = send_from_directory(STATIC_DIR, 'sw.js', mimetype='application/javascript')
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


@app.route('/healthz')
def healthz():
    # Ringan: tidak men-scan isi folder, hanya cek folder data bisa dibaca
    data_ok = os.path.isdir(BASE_DIR) and os.access(BASE_DIR, os.R_OK | os.X_OK)
    body = {'status': 'ok' if data_ok else 'error', 'data_dir': data_ok}
    return jsonify(body), (200 if data_ok else 503)


@app.route('/api/tree')
def api_tree():
    return jsonify(get_tree(BASE_DIR))


@app.route('/api/file/<path:filepath>')
def api_file(filepath):
    safe = safe_path(filepath)
    if not os.path.isfile(safe):
        abort(404)

    ext = os.path.splitext(safe)[1].lower()

    # TIF/TIFF → PNG on-the-fly (browser tidak support TIF natively)
    # ?alpha=1 (dipakai tekstur model 3D): pertahankan channel ke-4 sebagai alpha
    if ext in ('.tif', '.tiff'):
        if not HAS_PILLOW:
            abort(415)
        try:
            if request.args.get('alpha') == '1':
                img = open_tif_with_alpha(safe)
            else:
                img = Image.open(safe)
            mode = 'RGBA' if img.mode in ('RGBA', 'LA', 'PA') else 'RGB'
            buf = io.BytesIO()
            img.convert(mode).save(buf, format='PNG', optimize=False)
            buf.seek(0)
            return send_file(buf, mimetype='image/png')
        except Exception as e:
            log.error('TIF convert: %s', e)
            abort(500)

    # File 3D
    if ext in ('.fbx', '.obj', '.mtl'):
        return send_file(safe, mimetype='application/octet-stream')

    mime, _ = mimetypes.guess_type(safe)
    return send_file(safe, mimetype=mime or 'application/octet-stream')


@app.route('/api/download/<path:filepath>')
def api_download(filepath):
    safe = safe_path(filepath)
    if os.path.isfile(safe):
        return send_file(safe, as_attachment=True,
                         download_name=os.path.basename(safe))
    elif os.path.isdir(safe):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(safe):
                for f in files:
                    fp = os.path.join(root, f)
                    zf.write(fp, os.path.relpath(fp, os.path.dirname(safe)))
        buf.seek(0)
        return send_file(buf, as_attachment=True,
                         download_name=f'{os.path.basename(safe)}.zip',
                         mimetype='application/zip')
    abort(404)


if __name__ == '__main__':
    log.info('PolyView dev server → http://localhost:5000')
    log.info('BASE_DIR : %s', BASE_DIR)
    log.info('Pillow   : %s', HAS_PILLOW)
    app.run(host='127.0.0.1', port=5000, debug=True)
