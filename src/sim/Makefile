# =============================================================================
# src/sim/Makefile — chạy một testbench với một testcase
#
#   make sim  TB=<tên module tb> TC=<đường dẫn trong src/tc> [SIM=questa|verilator]
#   make gui  TB=... TC=...            # Questa GUI, tự add wave
#   make comp TB=...                   # chỉ biên dịch
#   make clean
#
# Ví dụ:  make sim TB=tb_gemm_vpu TC=unit/vpu/basic
#         make sim TB=tb_gemm_accel_top TC=top/single_basic PARAMS="HAS_CHAIN=1 HAS_PINGPONG=1"
#
# Quy ước (xem README.md ở gốc repo):
#   * filelist của tb nằm cạnh tb, cùng tên: src/tb/**/<TB>.f (dùng -F, đường dẫn tương đối)
#   * tb nhận thư mục testcase qua +TC_DIR, in một dòng "TEST PASSED" / "TEST FAILED"
# =============================================================================
SIM      ?= questa
TB       ?=
TC       ?=
SEED     ?= 1
PARAMS   ?=                 # tham số của tb, dạng "TÊN=giá_trị ..." (→ -G)
PLUSARGS ?=                 # plusarg thêm, ví dụ "+AXI_MAX_GAP=0"
DEFINES  ?=                 # macro thêm, ví dụ "+define+DEBUG"

ROOT  := $(abspath ../..)
TBF   := $(firstword $(shell find $(ROOT)/src/tb -name '$(TB).f' 2>/dev/null))
TCDIR := $(ROOT)/src/tc/$(TC)
TBDIR := $(patsubst %/,%,$(dir $(TBF)))
TC_SV := $(if $(strip $(TC)),$(wildcard $(TCDIR)/tc.sv))
INCDIR := $(if $(TC_SV),$(TCDIR),$(TBDIR)/default_tc)
TCTAG := $(subst /,__,$(strip $(TC)))
space := $(subst ,, )
PTAG  := $(if $(strip $(PARAMS)),_$(subst $(space),_,$(subst =,-,$(strip $(PARAMS)))))
OUTTB := $(ROOT)/src/sim/out/$(SIM)/$(TB)$(PTAG)
BUILD := $(OUTTB)/build_$(if $(TC_SV),$(TCTAG),default)
RUN   := $(OUTTB)/run/$(TCTAG)_s$(SEED)
GFLAGS := $(addprefix -G,$(PARAMS))

.PHONY: sim comp gui clean check-args

check-args:
	@test -n "$(TB)"  || (echo "thiếu TB=<tên tb>"; exit 1)
	@test -n "$(TBF)" || (echo "không tìm thấy $(TB).f trong src/tb"; exit 1)

	@test -f "$(INCDIR)/tc.sv" || (echo "không có tc.sv: tạo $(TCDIR)/tc.sv hoặc $(TBDIR)/default_tc/tc.sv"; exit 1)
	@echo "[sim] $(SIM) TB=$(TB) TC=$(TC) tc.sv=$(INCDIR)/tc.sv"

include tools/$(SIM).mk

clean:
	rm -rf $(ROOT)/src/sim/out
