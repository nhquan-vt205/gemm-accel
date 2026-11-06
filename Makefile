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

#? CÁC LỆNH (chạy từ gốc repo; [...] là tùy chọn, không gõ dấu ngoặc)
#? make help
#?   Xem hướng dẫn này. Ví dụ: make help
#?
#? THAM SỐ MÔ PHỎNG CHUNG cho comp/sim/gui:
#?   TB=<tên module TB, trùng tên .f>; TC=<đường dẫn dưới src/tc>.
#?   SIM=questa|verilator (mặc định questa); SEED=<simulation seed, mặc định 1>.
#?   PARAMS="NAME=value ...": parameter của TB; TB truyền xuống DUT.
#?   PLUSARGS="+NAME=value ...": tùy chọn runtime do TB đọc.
#?   DEFINES="+define+NAME ...": macro compile; WAVES=1: FST với Verilator.
#?   TB/TC mẫu có sẵn: tb_gemm_reset_sync / unit/reset_sync/TC_RST_001.
#?
#? make comp TB=<tb> [TC=<tc>] [SIM=...] [PARAMS=...] [DEFINES=...] [WAVES=1]
#?   Chỉ compile; TC cần nếu dùng tc.sv riêng, có default_tc thì có thể bỏ TC.
#?   Ví dụ: make comp TB=tb_gemm_reset_sync TC=unit/reset_sync/TC_RST_001 SIM=verilator
#?
#? make sim TB=<tb> TC=<tc> [SIM=...] [SEED=...] [PARAMS=...] [PLUSARGS=...] [DEFINES=...] [WAVES=1]
#?   Compile và chạy một TC tự viết (tc.sv cung cấp run_tc).
#?   Ví dụ Questa: make sim TB=tb_gemm_reset_sync TC=unit/reset_sync/TC_RST_001
#?   Ví dụ Verilator: make sim SIM=verilator TB=tb_gemm_reset_sync TC=unit/reset_sync/TC_RST_002 SEED=1
#?   Ví dụ parameter: make sim SIM=verilator TB=tb_gemm_reset_sync TC=unit/reset_sync/TC_RST_001 PARAMS="CLK_HALF_NS=10"
#?
#? make gen-tc GEN=<script Python> [GEN_ARGS="tham số generator"]
#?   Sinh TC dữ liệu; data seed khác simulation seed. Không ghi đè thư mục đã có.
#?   Ví dụ: make gen-tc GEN=model/gen/gen_reset_sync_tc.py GEN_ARGS="--seed 201 --count 2 --vectors 4"
#? make sim TB=<tb> TC=<tc dữ liệu> [các tham số sim như trên]
#?   Python không phải simulator; TB dùng default_tc/tc.sv đọc dữ liệu Python sinh.
#?   Ví dụ: make sim SIM=verilator TB=tb_gemm_reset_sync TC=unit/reset_sync/random_s101 SEED=7
#?
#? make regress [LIST=<tên list>] [PATLIST=<đường dẫn list>] [SIM=...] [SEEDS=1,2,3] [TIMEOUT=300] [PARAMS=...] [PLUSARGS=...] [DEFINES=...] [WAVES=1]
#?   LIST mặc định smoke, ánh xạ src/sim/regress/<LIST>.list; PATLIST ưu tiên nếu đặt.
#?   TIMEOUT: giây mỗi lượt, gồm compile. Tiếp tục sau lỗi, cuối cùng trả lỗi nếu có test không PASS.
#?   List: <TB> <TC> [NAME=value ...]; tùy chọn từng dòng ghi đè tùy chọn chung.
#?   TC tự viết theo unit: make regress LIST=reset_sync/pat
#?   TC tự viết trên Verilator: make regress SIM=verilator LIST=reset_sync/pat SEEDS=1
#?   TC Python: make regress SIM=verilator LIST=reset_sync/random SEEDS=7,8 TIMEOUT=300
#?   List tùy ý: make regress SIM=verilator PATLIST=src/sim/regress/reset_sync/pat.list
#?   Toàn bộ unit: make regress SIM=verilator LIST=unit
#?   Smoke: make regress SIM=verilator LIST=smoke
#?   Integration/top: make regress LIST=integ / make regress LIST=top (cần điền list; hiện rỗng)
#?
#? make report RUN=<thư mục regression hoặc results.json>
#?   Chỉ đọc kết quả đã lưu, không mô phỏng lại; trả lỗi nếu báo cáo có test không PASS.
#?   Ví dụ: make report RUN=src/sim/out/regress/<run_id>
#?   Mỗi đợt regress in đường dẫn thực tế, có report.txt, results.json, pat.list và logs/.
#?
#? make gui TB=<tb> TC=<tc> [SIM=questa] [SEED=...] [PARAMS=...] [PLUSARGS=...] [DEFINES=...]
#?   Questa mở GUI, add wave rồi chạy. Ví dụ: make gui TB=tb_gemm_reset_sync TC=unit/reset_sync/TC_RST_001
#?   GUI với dữ liệu Python: make gui TB=tb_gemm_reset_sync TC=unit/reset_sync/random_s101
#?   Verilator: make sim SIM=verilator TB=tb_gemm_reset_sync TC=unit/reset_sync/TC_RST_001 WAVES=1
#?   Xem FST: gtkwave src/sim/out/verilator/tb_gemm_reset_sync/run/unit__reset_sync__TC_RST_001_s1/waves.fst
#?
#? make lint [LINT_F=<filelist RTL>] [LINT_TOP=<module>] [LINT_PARAMS="NAME=value ..."]
#?   Không đặt LINT_F: lint toàn bộ RTL theo 3 cấu hình hiện có. Ví dụ: make lint
#?   Một module: make lint LINT_F=src/rtl/common/common.f LINT_TOP=gemm_reset_sync
#?   Một module có tham số: make lint LINT_F=src/rtl/vpu/vpu.f LINT_TOP=gemm_vpu LINT_PARAMS="P=4"
#?   Dùng Verilator, không chạy TC và không phụ thuộc SIM; thêm filelist package nếu khối cần package.
#?
#? make synth [TOP=<module>] [GENERICS="NAME=value ..."] [PART=<FPGA>] [CLK_NS=10]
#?   Ví dụ: make synth TOP=gemm_vpu GENERICS="P=4"
#? make schematic [TOP=<module>] [SCHEM=rtl|synth] [GENERICS=...]
#?   Ví dụ: make schematic TOP=gemm_systolic_array
#? make models: tự kiểm model Python, không sinh TC, không mô phỏng RTL. Ví dụ: make models
#? make docs: build PDF spec bằng XeLaTeX/latexmk. Ví dụ: make docs
#? make clean: xóa sim/synth out và file tạm LaTeX, cả báo cáo regression. Ví dụ: make clean

.DEFAULT_GOAL := help
.PHONY: help lint comp sim gui gen-tc regress report synth schematic docs models clean

help:
	@sed -n 's/^#? *//p' $(ROOT)/Makefile

# ---- lint: không cần license, CI cũng chạy lệnh này ----
LINT_F ?=
LINT_TOP ?= gemm_accel_top
LINT_PARAMS ?=
VERILATOR ?= verilator
lint:
ifneq ($(strip $(LINT_F)),)
	$(VERILATOR) --lint-only -Wall -F $(LINT_F) --top-module $(LINT_TOP) $(addprefix -G,$(LINT_PARAMS))
else
	$(VERILATOR) --lint-only -Wall -F src/rtl/top/top.f --top-module gemm_accel_top -GHAS_CHAIN=0 -GHAS_PINGPONG=0 -GPE_ARRAY_SIZE=8
	$(VERILATOR) --lint-only -Wall -F src/rtl/top/top.f --top-module gemm_accel_top -GHAS_CHAIN=1 -GHAS_PINGPONG=1 -GPE_ARRAY_SIZE=8
	$(VERILATOR) --lint-only -Wall -F src/rtl/top/top.f --top-module gemm_accel_top -GHAS_CHAIN=1 -GHAS_PINGPONG=1 -GPE_ARRAY_SIZE=4
endif
	@echo "lint OK"

# ---- mô phỏng ----
comp sim gui:
	$(MAKE) -C src/sim $@ SIM=$(SIM)

LIST  ?= smoke
PATLIST ?=
SEEDS ?= 1
TIMEOUT ?= 300
RUN ?=
GEN ?=
GEN_ARGS ?=
REGRESS_FILE = $(if $(strip $(PATLIST)),$(PATLIST),src/sim/regress/$(LIST).list)
regress:
	python3 src/sim/scripts/run_regress.py $(REGRESS_FILE) --sim $(SIM) --seeds $(SEEDS) --timeout $(TIMEOUT) $(foreach v,PARAMS PLUSARGS DEFINES WAVES,$(if $(strip $($(v))),--var '$(v)=$($(v))'))

report:
	@test -n "$(RUN)" || (echo "thiếu RUN=<thư mục regression hoặc results.json>"; exit 1)
	python3 src/sim/scripts/run_regress.py --report "$(RUN)"

gen-tc:
	@test -f "$(GEN)" || (echo "thiếu GEN=<script Python có thật>"; exit 1)
	python3 "$(GEN)" $(GEN_ARGS)

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
	cd model && for f in gemm_golden.py gemm_systolic_array_model.py gemm_vpu_model.py gemm_sram_model.py gemm_dma_model.py gemm_regfile_model.py gemm_sched_model.py; do \
	  echo "== $$f"; python3 $$f || exit 1; done

clean:
	rm -rf src/sim/out syn/out
	find docs -name '*.aux' -o -name '*.log' -o -name '*.fls' -o -name '*.fdb_latexmk' -o -name '*.xdv' -o -name '*.toc' -o -name '*.out' | xargs rm -f
