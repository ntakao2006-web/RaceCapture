// PC test of sd_logger.h when the SD card fills up (2026-11-07).
// The card is a small FAT32 image in memory (6 files of 1 MiB fit). Built with g++ in WSL:
//   g++ -std=c++17 -O1 -Wall -o /tmp/test_sd_full tests/test_sd_full.cpp && /tmp/test_sd_full [image.bin]
// The optional image is written for a second check with a standard FAT reader (test_sd_full_fat.py).
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
static unsigned reads = 0, writes = 0;
static bool cardRead(uint32_t lba, uint8_t* b) {
  if ((lba + 1) * 512ULL > card.size()) return false;
  memcpy(b, &card[lba * 512ULL], 512); reads++; return true;
}
static bool cardWrite(uint32_t lba, const uint8_t* b) {
  if ((lba + 1) * 512ULL > card.size()) return false;
  memcpy(&card[lba * 512ULL], b, 512); writes++; return true;
}
#include "../sd_logger.h"

static const uint32_t PART = 2048, RES = 32, SPC = 64, FATSZ = 2, CL = 200;
static uint8_t* sec(uint32_t lba) { return &card[lba * 512ULL]; }
static uint32_t fatAt(uint32_t c) { return u32(sec(PART + RES) + c * 4) & 0x0fffffff; }
static uint32_t dataLba(uint32_t c) { return PART + RES + 2 * FATSZ + (c - 2) * SPC; }

static void makeCard() {
  uint32_t partSize = RES + 2 * FATSZ + CL * SPC;
  card.assign((PART + partSize) * 512ULL, 0);
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
  freeCursor = 2; fatCached = 0xffffffff; sdDeleted = 0; sdFull = false; sdLogging = false;
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
static std::vector<Entry> entries() {
  std::vector<Entry> out;
  for (uint32_t s = 0; s < SPC; s++) for (uint32_t off = 0; off < 512; off += 32) {
    uint8_t* p = sec(dataLba(2) + s) + off;
    if (p[0] == 0 || p[0] == 0xe5 || p[11] == 0x08) continue;
    out.push_back({std::string((char*)p, 11), (uint32_t)strtoul(std::string((char*)p + 2, 6).c_str(), nullptr, 10),
                   ((uint32_t)u16(p + 20) << 16) | u16(p + 26), u32(p + 28)});
  }
  return out;
}

// Every file's chain is 32 contiguous clusters, no cluster is shared, everything else is free,
// both FAT copies agree, and each file still holds its own first sector.
static void checkConsistent(unsigned expectFiles, uint32_t otherClusters = 0) {
  assert(!memcmp(sec(PART + RES), sec(PART + RES + FATSZ), FATSZ * 512));
  std::set<uint32_t> used;
  auto list = entries();
  unsigned el = 0;
  for (auto& e : list) {
    uint32_t c = e.first, n = 0;
    while (true) { assert(c >= 3 && c < CL + 2); assert(used.insert(c).second); n++; uint32_t next = fatAt(c); if (next >= 0x0ffffff8) break; assert(next == c + 1); c = next; }
    if (e.name.compare(0, 2, "EL") == 0) {
      el++; assert(n == 32); assert(e.size == 1024 * 1024);
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
  assert(sdDeleted == 0 && !sdFull);
  checkConsistent(6);
  for (int i = 7; i <= 40; i++) assert(logOneFile());  // used to stop here: newSDLog() returned false
  assert(sdDeleted == 34 && sdFull);
  checkConsistent(6);
  std::set<uint32_t> kept; for (auto& e : entries()) kept.insert(e.index);
  assert(kept == (std::set<uint32_t>{35, 36, 37, 38, 39, 40}));
  // While full, a new file reuses the oldest file's run: no scan of the whole FAT.
  reads = 0; assert(logOneFile()); assert(reads < SPC + 12);
  puts("PASS: a full card drops the oldest EL files (34 of 40) and keeps the newest 6, FAT consistent");
}

static void testOtherFilesAreNeverRemoved() {
  makeCard();
  // A foreign file (e.g. copied by a PC) taking 100 clusters right after the root directory.
  uint8_t* p = sec(dataLba(2)) + 32; memcpy(p, "VIDEO   TS ", 11); p[11] = 0x20; p[26] = 3; p32(p + 28, 100 * SPC * 512);
  for (uint32_t f = 0; f < 2; f++) { uint8_t* fat = sec(PART + RES + f * FATSZ); for (uint32_t c = 3; c < 103; c++) p32(fat + c * 4, c == 102 ? 0x0fffffff : c + 1); }
  fatCached = 0xffffffff;
  for (int i = 1; i <= 20; i++) assert(logOneFile());
  checkConsistent(3, 100);
  bool video = false; for (auto& e : entries()) video |= e.name == "VIDEO   TS ";
  assert(video);
  puts("PASS: a non-EL file stays; only EL files are removed");
}

static void testNeverRemovesTheOnlyFile() {
  makeCard();
  // Foreign file filling all but 40 clusters: one EL file fits, a second one never does.
  uint8_t* p = sec(dataLba(2)) + 32; memcpy(p, "BIG     DAT", 11); p[11] = 0x20; p[26] = 3;
  for (uint32_t f = 0; f < 2; f++) { uint8_t* fat = sec(PART + RES + f * FATSZ); for (uint32_t c = 3; c < 162; c++) p32(fat + c * 4, c == 161 ? 0x0fffffff : c + 1); }
  fatCached = 0xffffffff;
  assert(logOneFile());
  assert(!newSDLog());  // the newest (only) file is not removed to make room
  assert(sdDeleted == 0);
  puts("PASS: the newest file is never removed (it gives up as before)");
}

int main(int argc, char** argv) {
  testFillsAndKeepsTheNewest();
  testOtherFilesAreNeverRemoved();
  testNeverRemovesTheOnlyFile();
  if (argc > 1) {  // the card after filling, for the standard FAT reader
    makeCard(); for (int i = 1; i <= 15; i++) assert(logOneFile());
    FILE* f = fopen(argv[1], "wb"); fwrite(card.data(), 1, card.size(), f); fclose(f);
  }
  return 0;
}
