"""Test konversi TIF di /api/file: alpha hanya dipertahankan dengan ?alpha=1.

Jalankan dari root project:
    python -m unittest discover -s tests -v
"""

import io
import os
import struct
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import server  # noqa: E402

W, H = 4, 2
# RGBA per piksel: baris atas opaque, baris bawah cutout (alpha 0)
PIXELS = [(200, 10, 30, 255), (10, 200, 30, 255), (10, 30, 200, 255), (90, 90, 90, 255),
          (255, 255, 255, 0), (0, 0, 0, 0), (128, 64, 32, 0), (1, 2, 3, 0)]


def write_tif(path, spp, extra_samples=None):
    """TIFF uncompressed minimal (little-endian, satu strip)."""
    data = b''.join(bytes(p[:spp]) for p in PIXELS)
    tags = []  # (tag, type, count, value-or-offset-placeholder)
    bps_offset = 8 + 2 + 12 * (11 if extra_samples is not None else 10) + 4
    data_offset = bps_offset + 2 * spp
    tags += [(256, 4, 1, W), (257, 4, 1, H), (258, 3, spp, bps_offset), (259, 3, 1, 1),
             (262, 3, 1, 2), (273, 4, 1, data_offset), (277, 3, 1, spp), (278, 4, 1, H),
             (279, 4, 1, len(data)), (284, 3, 1, 1)]
    if extra_samples is not None:
        tags.append((338, 3, 1, extra_samples))
    out = bytearray(b'II*\x00' + struct.pack('<I', 8))
    out += struct.pack('<H', len(tags))
    for tag, typ, count, value in tags:
        packed = struct.pack('<H', value) + b'\x00\x00' if typ == 3 and count == 1 else struct.pack('<I', value)
        out += struct.pack('<HHI', tag, typ, count) + packed
    out += struct.pack('<I', 0)
    assert len(out) == bps_offset
    out += struct.pack('<' + 'H' * spp, *([8] * spp))
    out += data
    with open(path, 'wb') as f:
        f.write(out)


class TifAlphaTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = cls.tmp.name
        write_tif(os.path.join(d, 'rgbx.tif'), 4, extra_samples=0)      # kasus 3ds Max/Photoshop
        write_tif(os.path.join(d, 'rgb.tif'), 3)
        Image.new('RGBA', (W, H), (10, 20, 30, 128)).save(os.path.join(d, 'rgba.tif'))  # ExtraSamples=2
        Image.new('RGBA', (W, H), (10, 20, 30, 128)).save(os.path.join(d, 'tex.png'))
        cls._old_base = server.BASE_DIR
        server.BASE_DIR = d
        cls.client = server.app.test_client()

    @classmethod
    def tearDownClass(cls):
        server.BASE_DIR = cls._old_base
        cls.tmp.cleanup()

    def get_png(self, url):
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200, url)
        self.assertEqual(r.mimetype, 'image/png')
        return Image.open(io.BytesIO(r.data))

    def test_sanity_pillow_membuang_channel_ke4(self):
        # Prasyarat bug: Pillow membuka TIF ini sebagai RGB
        self.assertEqual(Image.open(os.path.join(self.tmp.name, 'rgbx.tif')).mode, 'RGB')

    def test_default_tanpa_alpha_tidak_berubah(self):
        img = self.get_png('/api/file/rgbx.tif')
        self.assertEqual(img.mode, 'RGB')
        self.assertEqual(img.tobytes(), b''.join(bytes(p[:3]) for p in PIXELS))

    def test_alpha_1_mempertahankan_channel_ke4(self):
        img = self.get_png('/api/file/rgbx.tif?alpha=1')
        self.assertEqual(img.mode, 'RGBA')
        self.assertEqual(img.tobytes(), b''.join(bytes(p) for p in PIXELS))

    def test_alpha_nilai_lain_diabaikan(self):
        self.assertEqual(self.get_png('/api/file/rgbx.tif?alpha=0').mode, 'RGB')
        self.assertEqual(self.get_png('/api/file/rgbx.tif?alpha=true').mode, 'RGB')

    def test_tif_3_channel_tetap_rgb(self):
        self.assertEqual(self.get_png('/api/file/rgb.tif').mode, 'RGB')
        self.assertEqual(self.get_png('/api/file/rgb.tif?alpha=1').mode, 'RGB')

    def test_tif_rgba_standar_sama_seperti_sebelumnya(self):
        a = self.get_png('/api/file/rgba.tif')
        b = self.get_png('/api/file/rgba.tif?alpha=1')
        self.assertEqual(a.mode, 'RGBA')
        self.assertEqual(a.tobytes(), b.tobytes())

    def test_non_tif_tidak_terpengaruh(self):
        a = self.client.get('/api/file/tex.png')
        b = self.client.get('/api/file/tex.png?alpha=1')
        self.assertEqual(a.data, b.data)

    def test_download_tidak_berubah(self):
        with open(os.path.join(self.tmp.name, 'rgbx.tif'), 'rb') as f:
            original = f.read()
        self.assertEqual(self.client.get('/api/download/rgbx.tif').data, original)
        self.assertEqual(self.client.get('/api/download/rgbx.tif?alpha=1').data, original)


def _real_tif():
    for base in (os.environ.get('POLYVIEW_TEST_DATA'), '/data',
                 os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database3d')):
        if base and os.path.isfile(os.path.join(base, 'Bharata Class', 'KP Bharata.tif')):
            return base
    return None


@unittest.skipUnless(_real_tif(), 'data asli (Bharata Class/KP Bharata.tif) tidak tersedia')
class RealDataTest(unittest.TestCase):
    """TIF asli 3ds Max (LZW, 4 channel, ExtraSamples=0)."""

    def test_kp_bharata_mask_terbaca(self):
        old = server.BASE_DIR
        server.BASE_DIR = _real_tif()
        try:
            client = server.app.test_client()
            default = Image.open(io.BytesIO(client.get('/api/file/Bharata Class/KP Bharata.tif').data))
            self.assertEqual(default.mode, 'RGB')
            img = Image.open(io.BytesIO(client.get('/api/file/Bharata Class/KP Bharata.tif?alpha=1').data))
            self.assertEqual(img.mode, 'RGBA')
            hist = img.getchannel('A').histogram()
            total = sum(hist)
            self.assertAlmostEqual(hist[0] / total, 0.096, delta=0.01)    # area cutout
            self.assertAlmostEqual(hist[255] / total, 0.871, delta=0.01)  # area opaque
            # warna RGB identik dengan output default
            self.assertEqual(img.convert('RGB').tobytes(), default.tobytes())
        finally:
            server.BASE_DIR = old


if __name__ == '__main__':
    unittest.main()
