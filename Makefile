# =============================================================================
# Makefile gốc — mọi lệnh thường dùng của dự án
#   make help
# =============================================================================
ROOT := $(abspath .)
SIM  ?= questa

# ---- Vivado ----
VIVADO  ?= vivado
TOP     ?= gemm_accel_top
PART    ?= xc7a100tcsg324-1          # đổi theo board của nhóm
CLK_NS  ?= 10.0                      # chu kỳ clock ràng buộc (ns)
GENERICS ?=                          # ví dụ "P=4" hoặc "HAS_CHAIN=1 HAS_PINGPONG=1"
SCHEM   ?= rtl                       # rtl: schematic elaborated; synth: sau synth
SYN_OUT := $(ROOT)/syn/out/$(TOP)
TOP_SV  := $(firstword $(shell find $(ROOT)/src/rtl -name '$(TOP).sv' 2>/dev/null))
MOD_DIR := $(patsubst %/,%,$(dir $(TOP_SV)))
MOD_F   := $(MOD_DIR)/$(notdir $(MOD_DIR)).f

.PHONY: help lint sim gui regress synth schematic docs models clean

help:
	@echo "make lint                                   Verilator lint toàn bộ RTL (3 cấu hình)"
	@echo "make sim  TB=<tb> TC=<tc> [SIM=questa|verilator] [PARAMS=\"..\"]"
	@echo "make gui  TB=<tb> TC=<tc>                   Questa GUI + waveform"
	@echo "make regress LIST=unit [SEEDS=1,2,3]        chạy src/sim/regress/<LIST>.list"
	@echo "make synth     TOP=<module> [GENERICS=..]   Vivado synth OOC, báo cáo ở syn/out/<module>/"
	@echo "make schematic TOP=<module> [SCHEM=synth]   Vivado GUI schematic"
	@echo "make docs                                   build lại toàn bộ PDF spec (xelatex)"
	@echo "make models                                 chạy tự kiểm của các mô hình Python"
	@echo "make clean"

# ---- lint: không cần license, CI cũng chạy lệnh này ----
lint:
	verilator --lint-only -Wall -F src/rtl/top/top.f --top-module gemm_accel_top -GHAS_CHAIN=0 -GHAS_PINGPONG=0 -GPE_ARRAY_SIZE=8
	verilator --lint-only -Wall -F src/rtl/top/top.f --top-module gemm_accel_top -GHAS_CHAIN=1 -GHAS_PINGPONG=1 -GPE_ARRAY_SIZE=8
	verilator --lint-only -Wall -F src/rtl/top/top.f --top-module gemm_accel_top -GHAS_CHAIN=1 -GHAS_PINGPONG=1 -GPE_ARRAY_SIZE=4
	@echo "lint OK"

# ---- mô phỏng ----
sim gui:
	$(MAKE) -C src/sim $@ SIM=$(SIM)

LIST  ?= smoke
SEEDS ?= 1
regress:
	python3 src/sim/scripts/run_regress.py src/sim/regress/$(LIST).list --sim $(SIM) --seeds $(SEEDS)

# ---- Vivado: synth và schematic ----
$(SYN_OUT)/flist.f:
	@test -n "$(TOP_SV)" || (echo "không tìm thấy $(TOP).sv trong src/rtl"; exit 1)
	@mkdir -p $(SYN_OUT)
	@printf -- '-F %s\n-F %s\n-F %s\n' $(ROOT)/src/rtl/pkg/pkg.f $(ROOT)/src/rtl/common/common.f $(MOD_F) > $@

synth: $(SYN_OUT)/flist.f
	cd $(SYN_OUT) && TOP=$(TOP) FLIST=$(SYN_OUT)/flist.f PART=$(strip $(PART)) CLK_NS=$(strip $(CLK_NS)) \
	  GENERICS="$(strip $(GENERICS))" MODE=synth OUT=$(SYN_OUT) \
	  $(VIVADO) -mode batch -nojournal -log vivado.log -source $(ROOT)/syn/vivado/synth.tcl

schematic: $(SYN_OUT)/flist.f
	cd $(SYN_OUT) && TOP=$(TOP) FLIST=$(SYN_OUT)/flist.f PART=$(strip $(PART)) CLK_NS=$(strip $(CLK_NS)) \
	  GENERICS="$(strip $(GENERICS))" MODE=$(if $(filter synth,$(strip $(SCHEM))),synth_gui,rtl) OUT=$(SYN_OUT) \
	  $(VIVADO) -mode tcl -nojournal -log vivado.log -source $(ROOT)/syn/vivado/synth.tcl

# ---- tài liệu và mô hình ----
docs:
	@for d in docs/system/latex docs/algorithm/latex docs/modules/*/latex; do \
	  echo "== $$d"; (cd $$d && latexmk -xelatex -interaction=nonstopmode -quiet main.tex) || exit 1; done

models:
	cd model && for f in gemm_golden.py gemm_vpu_model.py gemm_sram_model.py gemm_dma_model.py gemm_regfile_model.py gemm_sched_model.py; do \
	  echo "== $$f"; python3 $$f || exit 1; done

clean:
	rm -rf src/sim/out syn/out
	find docs -name '*.aux' -o -name '*.log' -o -name '*.fls' -o -name '*.fdb_latexmk' -o -name '*.xdv' -o -name '*.toc' -o -name '*.out' | xargs rm -f
