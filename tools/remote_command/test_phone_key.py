"""スマホへ合言葉を渡すQR（qr.py・phone_key.py）の試験。

QRの絵は、PCに qrcode（別の作り手）があれば全部のマスクで同じ絵になること、pyzbar（読み手）があれば
読み戻せることを確かめる。どちらも無いPCでは、絵の形（目印・大きさ）と覚えてある絵の指紋だけを見る。"""
import hashlib
import importlib.util
import unittest

import phone_key
import qr

SECRET = 'ab' * 32
LOCAL = {'secret': SECRET, 'url': 'wss://relay.example/ws/audio/ncec'}


def sample(n):
    return bytes((i * 37 + n) % 256 for i in range(n))


class QrTest(unittest.TestCase):
    def test_size_and_finders(self):
        for n, version in ((1, 1), (14, 1), (15, 2), (110, 7), (213, 10)):
            m = qr.make(sample(n))
            self.assertEqual(len(m), version * 4 + 17)
            self.assertTrue(all(len(row) == len(m) for row in m))
            for ox, oy in ((0, 0), (len(m) - 7, 0), (0, len(m) - 7)):   # 3すみの目印
                self.assertEqual([m[oy + 3][ox + i] for i in range(7)], [1, 0, 1, 1, 1, 0, 1])

    def test_too_long(self):
        with self.assertRaises(ValueError):
            qr.make(bytes(214))

    def test_known_picture(self):
        """部品が無いPCでも、絵が変わってしまったら気づけるように（qrcode と同じ絵だと確かめた時点の指紋）"""
        m = qr.make(b'https://relay.example/live/home?room=ncec#k=' + SECRET.encode(), mask=2)
        digest = hashlib.sha256(''.join(''.join(map(str, row)) for row in m).encode()).hexdigest()
        self.assertEqual(digest, KNOWN)

    @unittest.skipUnless(importlib.util.find_spec('qrcode'), 'qrcode が無い')
    def test_same_as_qrcode(self):
        import qrcode
        from qrcode.constants import ERROR_CORRECT_M
        for n in [*range(1, 214, 9), 14, 15, 26, 27, 106, 107, 122, 123, 180, 181, 213]:
            data = sample(n)
            for mask in range(8):
                ref = qrcode.QRCode(error_correction=ERROR_CORRECT_M, border=0, mask_pattern=mask)
                ref.add_data(qrcode.util.QRData(data, mode=qrcode.util.MODE_8BIT_BYTE), optimize=0)
                ref.make(fit=True)
                self.assertEqual(qr.make(data, mask=mask), [[int(bool(x)) for x in row] for row in ref.modules], (n, mask))

    @unittest.skipUnless(importlib.util.find_spec('pyzbar') and importlib.util.find_spec('PIL'), 'pyzbar・PIL が無い')
    def test_reads_back(self):
        from PIL import Image
        from pyzbar.pyzbar import decode
        url = phone_key.pair_url(LOCAL)
        m = qr.make(url.encode())   # マスクは自分で選ぶ
        px, quiet = phone_key.MODULE_PX, phone_key.QUIET
        side = (len(m) + quiet * 2) * px
        img = Image.new('L', (side, side), 255)
        for y, row in enumerate(m):
            for x, dark in enumerate(row):
                if dark:
                    img.paste(0, ((x + quiet) * px, (y + quiet) * px, (x + quiet + 1) * px, (y + quiet + 1) * px))
        self.assertEqual([d.data.decode() for d in decode(img)], [url])


class PhoneKeyTest(unittest.TestCase):
    def test_pair_url(self):
        self.assertEqual(phone_key.pair_url(LOCAL), 'https://relay.example/live/home?room=ncec#k=' + SECRET)
        self.assertEqual(phone_key.cover_url({'url': 'ws://127.0.0.1:3010/ws/audio/dev'}), 'http://127.0.0.1:3010/live/home?room=dev')

    def test_home_url_wins(self):
        local = {**LOCAL, 'home_url': 'https://pit.example/live/home?room=eco&sheet=clock#k=old'}
        self.assertEqual(phone_key.pair_url(local), 'https://pit.example/live/home?room=eco&sheet=clock#k=' + SECRET)

    def test_missing(self):
        with self.assertRaises(ValueError):
            phone_key.pair_url({'url': LOCAL['url']})
        with self.assertRaises(ValueError):
            phone_key.pair_url({'secret': SECRET})

    def test_describe_hides_secret_and_host(self):
        text = phone_key.describe(LOCAL)
        self.assertIn('ncec', text)
        self.assertNotIn(SECRET, text)
        self.assertNotIn('relay.example', text)


KNOWN = 'b0672cf6ca64aaddaba6d68aa351a5fd966eccf9c13df0ea5302d0b748b7c67b'

if __name__ == '__main__':
    unittest.main()
