# Xcelium TCL — interactive VerifCPU console after +console_pause $stop
# Usage:
#   xrun ... +console_pause -input scripts/xcelium/console_probe.tcl
#
# In Tcl console after $stop:
#   call tb_full_campaign.console_help
#   call tb_full_campaign.console_cmd 4'd1 "vsync" 32'd10 0 0

puts "VerifCPU console_probe — paused at +console_pause"
call tb_full_campaign.console_help
puts "Examples:"
puts {call tb_full_campaign.console_cmd 4'd1 "status" 0 0 0}
puts {call tb_full_campaign.console_cmd 4'd1 "vsync" 32'd10 0 0}
puts {call tb_full_campaign.console_sync_cmd "sync_configure" 32'd10 32'd7 0}