reset_config srst_only srst_push_pull
init
halt
dump_image /tmp/logger_ram.bin 0x20000000 0x80000
resume
shutdown
