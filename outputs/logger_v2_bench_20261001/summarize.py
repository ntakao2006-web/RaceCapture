from pathlib import Path
import json,hashlib
p=Path(__file__).parent
summary={
 'date_jst':'2026-10-01',
 'setup':{'board':'Logger_V2 on Arduino UNO Q','imu':'not populated','power':'PC USB 3.0 cable only','gnss_antenna':'passive antenna outdoors','other_cables_and_antennas':'not connected','sd_card_presence':'awaiting user observation'},
 'usb':{'adb_serial':'3263089125','reported_link_speed':'super-speed','mcu_flash_and_rpc':'verified'},
 'led':{'outputs':'U8 QA-QH to D5-D12; D11 data, D13 clock, D7 latch','pattern':'one LED per second, then all on, then all off','commanded_and_rpc_verified':True,'optical_confirmation':'awaiting user observation'},
 'gnss':{'address_7bit':'0x42','mon_ver':'MAX-M10M / ROM SPG 5.10 / PROTVER 34.10','test_rate':'NAV-PVT polled at 1 Hz; higher GNSS rates not tested','coordinates_accuracy':'reported hAcc is receiver estimate, not surveyed accuracy','tests':{name:json.loads((p/'device_logs'/f'gnss_{name}.summary.json').read_text()) for name in ['100k','400k']},'i2c_speed':'requested software configuration; waveform not measured'},
 'can1':{'result':'32/32 recessive and 32/32 dominant GPIO TXD-to-RXD feedback','limit':'not a CAN frame/controller test or external bus test; installed Zephyr core has CONFIG_CAN disabled'},
 'can2':{'result':'SPI/reset/mode response and 32/32 internal loopback payload matches','initial_eflg':'0x00','final_eflg':'0x40 RX0OVR','tec':0,'rec':0,'status':'warning: receive-overflow flag remains; continuous error-free operation not verified','external_bus':'not tested'},
 'sd':{'result':'CMD0/CMD8 return 0xff; card not recognized','writes_performed':False,'limit':'cannot distinguish absent card from socket/card/assembly fault until card presence is confirmed'},
 'recording':{'medium':'UNO Q internal eMMC, not shield microSD','method':'diagnostic JSONL snapshots captured from real MCU sensor readings','files_100k_400k':'4/4 PC copies SHA256 match device copies','not_tested':['power-loss durability','full-rate MCU independent logging','microSD filesystem/write/read']},
 'imu':{'addresses':'0x28 and 0x29 did not respond','interpretation':'expected for unpopulated IMU'},
 'lte':{'commanded_state':'A3 power enable LOW; A2 PWRKEY control LOW','tests':'not powered/registered/transmitted with antenna absent','rails_measured':False},
 'linux':{'temperature_c_range':[39,44.6],'home_free_space':'approximately 17 GiB','evidence':'linux_health.txt'},
 'not_verified':['electrical voltage/current measurements','LED optical output','physical USB unplug/replug and cold-start','external CAN traffic or transceiver signal integrity','LTE/SIM/RF','IMU functions','power fault and endurance tests'],
 'left_on_device':{'firmware':'logger_v2_bench real hardware diagnostic, not production logging firmware','led_mode':'sweep','old_web_app':'ecologger.read unavailable; existing dashboard will show disconnected','original_sketch_backup':'prebench_sketch.bin; first 65536 bytes before test','core':'unchanged'},
 'references':{'GNSS':'https://content.u-blox.com/sites/default/files/documents/MAX-M10M-00B_IntegrationManual_UBX-22038241.pdf','MCP25625':'https://ww1.microchip.com/downloads/en/DeviceDoc/MCP25625-CAN-Controller-Data-Sheet-20005282C.pdf'}
}
(p/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print('Saved summary.json')
