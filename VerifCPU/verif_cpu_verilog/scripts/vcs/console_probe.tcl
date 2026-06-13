# VCS UCLI — interactive VerifCPU console after +console_pause $stop
# Usage:
#   ./scripts/vcs/full_campaign.sh  (add +console_pause to VCS_OPTS)
#   simv +console_pause -ucli -do scripts/vcs/console_probe.tcl
#
# Or manually in UCLI after simulation stops:
#   call tb_full_campaign.console_help()
#   call tb_full_campaign.console_cmd(4'd1, "status", 0, 0, 0)
#   call tb_full_campaign.console_cmd(4'd1, "vsync", 32'd10, 0, 0)
#   call tb_full_campaign.console_sync_cmd("sync_configure", 32'd10, 32'd7, 0)

puts "VerifCPU console_probe — paused at +console_pause"
call tb_full_campaign.console_help()
puts "Examples:"
puts {  call tb_full_campaign.console_cmd(4'd1, "status", 0, 0, 0)}
puts {  call tb_full_campaign.console_cmd(4'd1, "vsync", 32'd10, 0, 0)}
puts {  call tb_full_campaign.console_sync_cmd("sync_configure", 32'd10, 32'd7, 0)}
puts {  call tb_full_campaign.console_sync_cmd("hw_force_set", 32'h10, 32'h40000000, 32'h5000)}
puts {  call tb_full_campaign.console_cmd(4'd1, "vhw_release", 32'h10, 32'h40000000, 0)}
puts "Type 'run' to continue campaign, or keep calling console_cmd."