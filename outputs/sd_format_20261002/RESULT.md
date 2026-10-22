2026-10-02 UNO Q storage maintenance

- Removed device run/history storage: 156 log files, 8 demo files, 1 SD original-sector journal, 49 bench files, 5 LTE measurement reports; total 659094553 bytes. Removed two additional live-verification reports outside the data directory.
- Preserved software, firmware sources and configuration. EcoCapture auto_record is now false.
- Updated and flashed the 57968-byte firmware with an explicit, capacity-checked FORMAT16 maintenance command and stopped-recording queue cleanup. Normal boot still supports autonomous MCU recording; no formatting occurs automatically.
- SD CSD verified SDHC capacity 31116288 sectors = 15931539456 bytes.
- FAT32 partition: LBA 2048, 31114240 sectors = 15930490880 bytes, 32 KiB clusters, 32 reserved sectors, 2 FATs of 3799 sectors each.
- Formatting took 66 seconds. Every cleared management/root sector was read back and compared. Last physical sector passed pattern write/read verification and was cleared afterward.
- Verified MBR, primary/backup boot sectors, initial entries of both FAT copies, empty root cluster, cleared last sector and FILES=[] through the MCU.
- Restarted Web and viewer. Both /api/logs and /api/sd/logs returned []; connected=true, receive_hz=100.3, recording inactive, SD recognized.
- Standard quick format: filesystem reinitialized; this was not a forensic secure erase. PC workspace verification archives were not part of the device-storage deletion.
