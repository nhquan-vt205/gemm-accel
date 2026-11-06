# =============================================================================
# tools/questa.mk — QuestaSim (simulator chính của nhóm)
# Biến dùng từ Makefile: TB TBF TC TCDIR OUT RUN SEED GFLAGS PLUSARGS DEFINES
# =============================================================================
VLIB ?= vlib
VLOG ?= vlog
VSIM ?= vsim

VLOG_FLAGS ?= -sv -timescale 1ns/1ps +define+SIM $(DEFINES) -lint
VSIM_FLAGS ?= -onfinish exit -sv_seed $(SEED) $(GFLAGS)
RUN_ARGS    = +TC_DIR=$(TCDIR) +SEED=$(SEED) $(PLUSARGS)

comp: check-args
	@mkdir -p $(OUT)
	cd $(OUT) && $(VLIB) work > /dev/null && $(VLOG) $(VLOG_FLAGS) -work work -F $(TBF) -l compile.log

sim: comp
	@test -n "$(TC)" || (echo "thiếu TC=<testcase>"; exit 1)
	@mkdir -p $(RUN)
	cd $(RUN) && $(VSIM) -c $(VSIM_FLAGS) -lib $(OUT)/work $(TB) $(RUN_ARGS) \
	    -do "run -all; quit -f" -l sim.log
	@grep -E "TEST (PASSED|FAILED)" $(RUN)/sim.log || (echo "TEST FAILED: tb không in kết quả"; exit 1)

# GUI: giữ tín hiệu (+acc), log mọi tín hiệu vào vsim.wlf và mở cửa sổ wave
gui: comp
	@mkdir -p $(RUN)
	cd $(RUN) && $(VSIM) $(VSIM_FLAGS) -voptargs=+acc -lib $(OUT)/work $(TB) $(RUN_ARGS) \
	    -do "log -r /*; add wave -r /$(TB)/*; run -all"
