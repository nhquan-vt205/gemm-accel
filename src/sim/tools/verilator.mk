# =============================================================================
# tools/verilator.mk — Verilator 5 (dùng cho CI trên GitHub, không cần license)
# Biến dùng từ Makefile: TB TBF TC TCDIR BUILD INCDIR RUN SEED GFLAGS PLUSARGS DEFINES
# =============================================================================
VERILATOR ?= verilator
VL_FLAGS  ?= --binary --timing --assert -j 0 -Wno-fatal -Wno-TIMESCALEMOD +define+SIM $(DEFINES)
ifeq ($(WAVES),1)
VL_FLAGS  += --trace-fst +define+WAVES
endif
RUN_ARGS   = +TC_DIR=$(TCDIR) +SEED=$(SEED) +verilator+seed+$(SEED) $(PLUSARGS)

comp: check-args
	@mkdir -p $(BUILD)
	$(VERILATOR) $(VL_FLAGS) $(GFLAGS) --top-module $(TB) +incdir+$(INCDIR) -F $(TBF) --Mdir $(BUILD)/obj -o V$(TB) > $(BUILD)/compile.log 2>&1 \
	    || (cat $(BUILD)/compile.log; exit 1)

sim: comp
	@test -n "$(TC)" || (echo "thiếu TC=<testcase>"; exit 1)
	@mkdir -p $(RUN)
	@cd $(RUN) || exit $$?; status=0; \
	  $(BUILD)/obj/V$(TB) $(RUN_ARGS) > sim.log 2>&1 || status=$$?; \
	  cat sim.log; exit $$status
	@! grep -q "TEST FAILED" $(RUN)/sim.log || (echo "TEST FAILED: xem $(RUN)/sim.log"; exit 1)
	@grep -E "TEST PASSED" $(RUN)/sim.log || (echo "TEST FAILED: tb không in kết quả PASS"; exit 1)

gui:
	@echo "Verilator không có GUI: chạy 'make sim SIM=verilator WAVES=1 ...' rồi mở waves.fst bằng GTKWave"
