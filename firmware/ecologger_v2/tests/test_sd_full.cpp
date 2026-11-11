// PC test of sd_logger.h when the SD card fills up (2026-11-07).
// The card is a small FAT32 image in memory with 512-byte clusters, so a 1 MiB file is 2048
// clusters, 6 files fit and the FAT is 99 sectors (big enough to see a whole-FAT scan).
// Built with g++ in WSL:
//   g++ -std=c++17 -O1 -o /tmp/test_sd_full tests/test_sd_full.cpp && /tmp/test_sd_full [image.bin [grown.bin]]
// The optional images are written for a second check with a standard FAT reader (test_sd_full_fat.py):
// a full card, and a card whose root directory grew into a second cluster.
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <set>
#include <string>
#include <vector>

#define SD_LOGGER_TEST_CARD
static bool sdReady = true;
static std::string result;
static uint32_t fakeMs = 0;
static uint32_t millis() { return fakeMs; }

static std::vector<uint8_t> card;
static std::set<uint32_t> fatSectorsRead;
static uint32_t fatFirst = 0, fatLast = 0;
static bool cardRead(uint32_t lba, uint8_t* b) {
  if ((lba + 1) * 512ULL > card.size()) return false;
  if (lba >= fatFirst && lba < fatLast) fatSectorsRead.insert(lba);
  memcpy(b, &card[lba * 512ULL], 512); return true;
}
static bool cardWrite(uint32_t lba, const uint8_t* b) {
  if ((lba + 1) * 512ULL > card.size()) return false;
  memcpy(&card[lba * 512ULL], b, 512); return true;
}
#include "../sd_logger.h"

static const uint32_t PART = 2048, RES = 32, SPC = 1, PER_FILE = 2048, CL = 6 * PER_FILE + 300;
static const uint32_t FATSZ = ((CL + 2) * 4 + 511) / 512;
static uint8_t* sec(uint32_t lba) { return &card[lba * 512ULL]; }
static uint32_t fatAt(uint32_t c) { return u32(sec(PART + RES) + c * 4) & 0x0fffffff; }
static uint32_t dataLba(uint32_t c) { return PART + RES + 2 * FATSZ + (c - 2) * SPC; }
static void setChain(uint32_t from, uint32_t n) {
  for (uint32_t f = 0; f < 2; f++) { uint8_t* fat = sec(PART + RES + f * FATSZ); for (uint32_t c = from; c < from + n; c++) p32(fat + c * 4, c == from + n - 1 ? 0x0fffffff : c + 1); }
  fatCached = 0xffffffff;
}

static void makeCard() {
  uint32_t partSize = RES + 2 * FATSZ + CL * SPC;
  card.assign((PART + partSize) * 512ULL, 0);
  fatFirst = PART + RES; fatLast = PART + RES + 2 * FATSZ;
  uint8_t* m = sec(0); m[446 + 4] = 0x0c; p32(m + 446 + 8, PART); p32(m + 446 + 12, partSize); m[510] = 0x55; m[511] = 0xaa;
  uint8_t* b = sec(PART);
  b[0] = 0xeb; b[1] = 0x58; b[2] = 0x90; memcpy(b + 3, "MSWIN4.1", 8);
  b[11] = 0; b[12] = 2; b[13] = SPC; b[14] = RES; b[16] = 2; b[21] = 0xf8; b[24] = 63; b[26] = 255;
  p32(b + 28, PART); p32(b + 32, partSize); p32(b + 36, FATSZ); p32(b + 44, 2); b[48] = 1; b[50] = 6;
  b[64] = 0x80; b[66] = 0x29; p32(b + 67, 0x12345678); memcpy(b + 71, "ECOLOGGER  ", 11); memcpy(b + 82, "FAT32   ", 8);
  b[510] = 0x55; b[511] = 0xaa;
  uint8_t* fs = sec(PART + 1); p32(fs, 0x41615252); p32(fs + 484, 0x61417272); p32(fs + 488, CL - 1); p32(fs + 492, 3); fs[510] = 0x55; fs[511] = 0xaa;
  memcpy(sec(PART + 6), b, 512); memcpy(sec(PART + 7), fs, 512);
  for (uint32_t f = 0; f < 2; f++) {
    uint8_t* fat = sec(PART + RES + f * FATSZ);
    p32(fat, 0x0ffffff8); p32(fat + 4, 0x0fffffff); p32(fat + 8, 0x0fffffff);
  }
  memcpy(sec(dataLba(2)), "ECOLOGGER  \x08", 12);  // volume label entry like a formatted card
  freeCursor = 2; fatCached = 0xffffffff; sdFull = false; sdLogging = false;
  assert(mountCard()); sdMounted = true;
}

// Writes one whole 1 MiB file: the first sector holds its index so it can be checked later.
static bool logOneFile() {
  if (!newSDLog()) return false;
  uint8_t mark[512] = {0}; snprintf((char*)mark, sizeof(mark), "file %lu", (unsigned long)logIndex);
  assert(partitionWrite(dataBase + (logFirst - 2) * clusterSectors, mark));
  logBytes = logCapacity; assert(logMetadata()); sdLogging = false; fakeMs += 105000;
  return true;
}

struct Entry { std::string name; uint32_t index, first, size; };
static std::vector<uint32_t> rootClusters() {
  std::vector<uint32_t> out; for (uint32_t c = 2; c >= 2 && c < CL + 2; c = fatAt(c)) { out.push_back(c); if (fatAt(c) >= 0x0ffffff8) break; }
  return out;
}
static std::vector<Entry> entries() {
  std::vector<Entry> out;
  for (uint32_t rc : rootClusters()) for (uint32_t s = 0; s < SPC; s++) for (uint32_t off = 0; off < 512; off += 32) {
    uint8_t* p = sec(dataLba(rc) + s) + off;
    if (p[0] == 0 || p[0] == 0xe5 || p[11] == 0x08) continue;
    out.push_back({std::string((char*)p, 11), (uint32_t)strtoul(std::string((char*)p + 2, 6).c_str(), nullptr, 10),
                   ((uint32_t)u16(p + 20) << 16) | u16(p + 26), u32(p + 28)});
  }
  return out;
}

// Every file's chain is one contiguous run, no cluster is shared, everything else is free,
// both FAT copies agree, and each file still holds its own first sector.
static void checkConsistent(unsigned expectFiles, uint32_t otherClusters = 0) {
  assert(!memcmp(sec(PART + RES), sec(PART + RES + FATSZ), FATSZ * 512));
  std::set<uint32_t> used; for (uint32_t rc : rootClusters()) used.insert(rc);
  unsigned el = 0;
  for (auto& e : entries()) {
    uint32_t c = e.first, n = 0;
    while (true) { assert(c >= 3 && c < CL + 2); assert(used.insert(c).second); n++; uint32_t next = fatAt(c); if (next >= 0x0ffffff8) break; assert(next == c + 1); c = next; }
    if (e.name.compare(0, 2, "EL") == 0) {
      el++; assert(n == PER_FILE); assert(e.size == 1024 * 1024);
      char want[32]; snprintf(want, sizeof(want), "file %lu", (unsigned long)e.index);
      assert(!strcmp((char*)sec(dataLba(e.first)), want));
    } else assert(n == otherClusters);
  }
  assert(el == expectFiles);
  for (uint32_t c = 3; c < CL + 2; c++) if (!used.count(c)) assert(fatAt(c) == 0);
}

static void testFillsAndKeepsTheNewest() {
  makeCard();
  for (int i = 1; i <= 6; i++) assert(logOneFile());
  assert(!sdFull);
  checkConsistent(6);
  for (int i = 7; i <= 40; i++) assert(logOneFile());  // used to stop here: newSDLog() returned false
  assert(sdFull);
  checkConsistent(6);
  std::set<uint32_t> kept; for (auto& e : entries()) kept.insert(e.index);
  assert(kept == (std::set<uint32_t>{35, 36, 37, 38, 39, 40}));
  // Once full, a new file reuses the oldest file's run: it reads only the FAT sectors of the
  // removed and the new file (16 each here), not the whole FAT (99 sectors).
  fatSectorsRead.clear(); assert(logOneFile());
  printf("  FAT sectors read for a new file on a full card: %zu of %u\n", fatSectorsRead.size(), FATSZ);
  assert(fatSectorsRead.size() <= 2 * (PER_FILE / 128) + 2);
  puts("PASS: a full card drops the oldest EL files (34 of 40) and keeps the newest 6, FAT consistent");
}

static void testOtherFilesAreNeverRemoved() {
  makeCard();
  // A foreign file (e.g. copied by a PC) taking 3000 clusters right after the root directory.
  uint8_t* p = sec(dataLba(2)) + 32; memcpy(p, "VIDEO   TS ", 11); p[11] = 0x20; p[26] = 3; p32(p + 28, 3000 * SPC * 512);
  setChain(3, 3000);
  for (int i = 1; i <= 20; i++) assert(logOneFile());
  checkConsistent(4, 3000);
  bool video = false; for (auto& e : entries()) video |= e.name == "VIDEO   TS ";
  assert(video);
  puts("PASS: a non-EL file stays; only EL files are removed");
}

static void testNeverRemovesTheOnlyFile() {
  makeCard();
  // Foreign file filling all but one EL file's room: a second EL file never fits.
  uint8_t* p = sec(dataLba(2)) + 32; memcpy(p, "BIG     DAT", 11); p[11] = 0x20; p[26] = 3;
  setChain(3, CL - 1 - PER_FILE - 100);
  assert(logOneFile());
  assert(!newSDLog());  // the newest (only) file is not removed to make room
  assert(!sdFull && entries().size() == 2);  // BIG.DAT and the one EL file
  puts("PASS: the newest file is never removed (it gives up as before)");
}

// The root directory grows into a second cluster (2026-11-11). On the SUGO card (32 KiB clusters)
// this happened at file 1022: the cluster added to the directory was the first cluster of the
// run just reserved for the new file (not yet marked in the FAT), so the file's FAT chain also
// became the directory's, the file's data overwrote its own entry, and later entries were written
// inside that file. Here the 512-byte root cluster is filled with 15 other entries first, so the
// first EL file already needs a second directory cluster.
static void testRootDirectoryGrowsIntoItsOwnCluster() {
  makeCard();
  for (int i = 1; i < 16; i++) {  // slot 0 is the volume label
    uint8_t* p = sec(dataLba(2)) + i * 32; char n[12]; snprintf(n, sizeof(n), "OTHER%03dTXT", i);
    memcpy(p, n, 11); p[11] = 0x20;  // empty files: no clusters
  }
  for (int i = 1; i <= 4; i++) assert(logOneFile());
  std::vector<uint32_t> root = rootClusters();
  assert(root.size() == 2);  // the label + 15 files, then one more cluster for the EL entries
  std::set<uint32_t> dir(root.begin(), root.end());
  unsigned el = 0;
  for (auto& e : entries()) {
    if (e.name.compare(0, 2, "EL") != 0) continue;
    el++;
    for (uint32_t c = e.first, n = 0; n < PER_FILE; n++, c++) assert(!dir.count(c));  // no shared cluster
    assert(fatAt(e.first + PER_FILE - 1) >= 0x0ffffff8);
    char want[32]; snprintf(want, sizeof(want), "file %lu", (unsigned long)e.index);
    assert(!strcmp((char*)sec(dataLba(e.first)), want));  // the file still holds its own data
  }
  assert(el == 4);
  // Full card from here: the oldest are removed and the second directory cluster stays a directory.
  for (int i = 5; i <= 20; i++) assert(logOneFile());
  assert(rootClusters() == root);
  std::set<uint32_t> kept; for (auto& e : entries()) if (e.name.compare(0, 2, "EL") == 0) kept.insert(e.index);
  assert(kept == (std::set<uint32_t>{15, 16, 17, 18, 19, 20}));
  for (auto& e : entries()) if (e.name.compare(0, 2, "EL") == 0)
    for (uint32_t c = e.first, n = 0; n < PER_FILE; n++, c++) assert(!dir.count(c));
  puts("PASS: the root directory grows into its own cluster, never into a new file's run");
}

int main(int argc, char** argv) {
  testFillsAndKeepsTheNewest();
  testOtherFilesAreNeverRemoved();
  testNeverRemovesTheOnlyFile();
  testRootDirectoryGrowsIntoItsOwnCluster();
  std::vector<uint8_t> grown = card;  // two directory clusters, EL000015-EL000020 and 15 other files
  if (argc > 1) {  // the card after filling, for the standard FAT reader
    makeCard(); for (int i = 1; i <= 15; i++) assert(logOneFile());
    FILE* f = fopen(argv[1], "wb"); fwrite(card.data(), 1, card.size(), f); fclose(f);
  }
  if (argc > 2) { FILE* f = fopen(argv[2], "wb"); fwrite(grown.data(), 1, grown.size(), f); fclose(f); }
  return 0;
}
