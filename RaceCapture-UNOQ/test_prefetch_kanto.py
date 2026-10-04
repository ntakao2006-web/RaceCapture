import tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
import prefetch_kanto as pack

class PackTests(unittest.TestCase):
    def test_bounded_region(self):
        self.assertEqual(len(pack.positions(14)),15827)
        for lon,lat in [(139.69,35.68),(139.64,35.44),(140.1,35.61),(139.65,35.86),(139.06,36.39),(139.88,36.56),(140.47,36.37)]:
            self.assertIn((14,*pack.tile(lon,lat,14)),pack.positions(14))

    def test_interface_binding_failure_never_connects_elsewhere(self):
        sock=MagicMock();sock.setsockopt.side_effect=OSError('no Wi-Fi')
        with patch.object(pack.socket,'socket',return_value=sock):
            with self.assertRaises(OSError):pack.WifiHTTPS(pack.HOST).connect()
        sock.connect.assert_not_called();sock.close.assert_called_once()

    def test_overviews_generated_from_saved_air_photo(self):
        with tempfile.TemporaryDirectory() as temp:
            def positions(z):return [(z,*pack.tile(139.5,36,z))]
            def fetch(item):
                p=pack.path(*item);p.parent.mkdir(parents=True,exist_ok=True)
                im=pack.GdkPixbuf.Pixbuf.new(pack.GdkPixbuf.Colorspace.RGB,False,8,256,256);im.fill(0xff0000ff)
                im.savev(str(p),'jpeg',[],[]);return 'downloaded',p.stat().st_size
            with patch.object(pack,'ROOT',Path(temp)),patch.object(pack,'positions',positions),patch.object(pack,'fetch',fetch):
                pack.main()
                for z in range(2,15):self.assertTrue(pack.path(*positions(z)[0]).exists())

if __name__=='__main__':unittest.main()
