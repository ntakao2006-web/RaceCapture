reset_config srst_only srst_push_pull
init
echo "STATE=[stm32u5.cpu curstate]"
echo "HALT=[catch {halt 1000} err] $err"
echo "STATE2=[stm32u5.cpu curstate]"
echo "REG=[catch {reg pc} err] $err"
echo "XPSR=[catch {reg xpsr} err] $err"
echo "SP=[catch {reg sp} err] $err"
resume
shutdown
