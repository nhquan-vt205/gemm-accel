# =============================================================================
# tools/verilator.mk — Verilator 5 (dùng cho CI trên GitHub, không cần license)
# Biến dùng từ Makefile: TB TBF TC TCDIR OUT RUN SEED GFLAGS PLUSARGS DEFINES
# =============================================================================
VERILATOR ?= verilator
VL_FLAGS  ?= --binary --timing --assert -j 0 -Wno-fatal -Wno-TIMESCALEMOD +define+SIM $(DEFINES)
ifeq ($(WAVES),1)
VL_FLAGS  += --trace-fst +define+WAVES
endif
RUN_ARGS   = +TC_DIR=$(TCDIR) +SEED=$(SEED) +verilator+seed+$(SEED) $(PLUSARGS)

comp: check-args
	@mkdir -p $(OUT)
	$(VERILATOR) $(VL_FLAGS) $(GFLAGS) --top-module $(TB) -F $(TBF) --Mdir $(OUT)/obj -o V$(TB) > $(OUT)/compile.log 2>&1 \
	    || (cat $(OUT)/compile.log; exit 1)

sim: comp
	@test -n "$(TC)" || (echo "thiếu TC=<testcase>"; exit 1)
	@mkdir -p $(RUN)
	cd $(RUN) && $(OUT)/obj/V$(TB) $(RUN_ARGS) | tee sim.log
	@grep -E "TEST (PASSED|FAILED)" $(RUN)/sim.log || (echo "TEST FAILED: tb không in kết quả"; exit 1)

gui:
	@echo "Verilator không có GUI: chạy 'make sim SIM=verilator WAVES=1 ...' rồi mở waves.fst bằng GTKWave"
