# =============================================================================
# syn/vivado/synth.tcl — synth out-of-context một module, hoặc mở schematic
#
# Gọi qua Makefile ở gốc repo:
#   make synth     TOP=gemm_vpu                    # batch: báo cáo tài nguyên + timing
#   make schematic TOP=gemm_vpu                    # GUI: schematic RTL (elaborated)
#   make schematic TOP=gemm_vpu SCHEM=synth        # GUI: schematic sau synth
# Biến môi trường (Makefile truyền): TOP FLIST PART CLK_NS GENERICS MODE OUT
# =============================================================================
set top     $::env(TOP)
set flist   $::env(FLIST)
set part    $::env(PART)
set clk_ns  $::env(CLK_NS)
set mode    $::env(MODE)          ;# synth | rtl | synth_gui
set out     $::env(OUT)
set generics {}
if {[info exists ::env(GENERICS)] && $::env(GENERICS) ne ""} {
  foreach g [split [string trim $::env(GENERICS)] " "] { if {$g ne ""} { lappend generics -generic $g } }
}
file mkdir $out

# ---- đọc filelist (-F lồng nhau, đường dẫn tương đối theo vị trí file .f) ----
set ::seen [dict create]
proc read_flist {f} {
  set dir [file dirname [file normalize $f]]
  set fh [open $f r]
  foreach line [split [read $fh] "\n"] {
    set line [string trim $line]
    if {$line eq "" || [string match "//*" $line] || [string match "#*" $line]} { continue }
    if {[string match "-F *" $line] || [string match "-f *" $line]} {
      read_flist [file join $dir [string trim [string range $line 2 end]]]
      continue
    }
    set p [file normalize [file join $dir $line]]
    if {[dict exists $::seen $p]} { continue }
    dict set ::seen $p 1
    read_verilog -sv $p
  }
  close $fh
}

set_part $part
read_flist $flist

# ---- ràng buộc clock cho OOC ----
set xdc [file join $out clk.xdc]
set fh [open $xdc w]
puts $fh "create_clock -name clk -period $clk_ns \[get_ports clk\]"
close $fh
read_xdc -mode out_of_context $xdc

if {$mode eq "rtl"} {
  synth_design -rtl -top $top -part $part {*}$generics
  start_gui
  show_schematic [concat [get_cells] [get_ports]]
  return
}

synth_design -top $top -part $part -mode out_of_context -flatten_hierarchy rebuilt {*}$generics
write_checkpoint -force [file join $out ${top}_synth.dcp]
report_utilization    -file [file join $out ${top}_utilization.rpt]
report_utilization    -hierarchical -file [file join $out ${top}_utilization_hier.rpt]
report_timing_summary -file [file join $out ${top}_timing.rpt]
puts "Báo cáo: $out"

if {$mode eq "synth_gui"} {
  start_gui
  show_schematic [concat [get_cells] [get_ports]]
}
