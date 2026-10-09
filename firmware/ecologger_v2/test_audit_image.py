import tempfile
import unittest
from pathlib import Path
import struct
from audit_image import audit


class ImageAuditTests(unittest.TestCase):
    def test_counts_zero_fill_and_code_without_counting_debug_sections(self):
        # ELF32 with allocated text/BSS, section names, and non-allocated debug.
        names = b'\0.text\0.bss\0.shstrtab\0.debug\0'
        table = 128
        header = struct.pack('<16sHHIIIIIHHHHHH', b'\x7fELF\x01\x01'+b'\0'*10,
                             1,40,1,0,0,table,0,52,0,0,40,5,3)
        image = bytearray(table+5*40)
        image[:52] = header; image[52:68] = b'X'*16; image[68:68+len(names)] = names
        rows = [(0,0,0,0,0,0,0,0,0,0), (1,1,6,0,52,16,0,0,4,0),
                (7,8,3,0,0,65536,0,0,8,0), (12,3,0,0,68,len(names),0,0,1,0),
                (22,1,0,0,100,8,0,0,1,0)]
        for i,row in enumerate(rows): struct.pack_into('<10I',image,table+i*40,*row)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'sketch.bin'; path.write_bytes(image)
            result=audit(path)
        self.assertEqual(result['static_allocated_bytes'],65552)
        self.assertEqual([row['name'] for row in result['sections']],['.text','.bss'])
        self.assertTrue(result['sections'][1]['zero_fill'])

    def test_rejects_non_elf_and_truncated_section_table(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'bad.bin'; path.write_bytes(b'not ELF')
            with self.assertRaises(ValueError): audit(path)
            path.write_bytes(struct.pack('<16sHHIIIIIHHHHHH', b'\x7fELF\x01\x01'+b'\0'*10,
                                         1,40,1,0,0,100,0,52,0,0,40,1,0))
            with self.assertRaises(ValueError): audit(path)


if __name__=='__main__': unittest.main()
