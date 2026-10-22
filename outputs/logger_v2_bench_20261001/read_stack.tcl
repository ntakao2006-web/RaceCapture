reset_config srst_only srst_push_pull
init
halt 1000
echo "PC=[catch {reg pc} err] $err"
echo "LR=[catch {reg lr} err] $err"
echo "SP=[catch {reg sp} err] $err"
echo "XPSR=[catch {reg xpsr} err] $err"
mdw 0x2002ccf8 64
resume
shutdown
