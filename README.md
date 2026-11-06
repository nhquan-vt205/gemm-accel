# gemm-accel — Bộ tăng tốc GEMM INT8 trên Chipyard SoC

Đồ án tốt nghiệp: accelerator nhân ma trận INT8 (systolic array Output-Stationary P×P, VPU hậu xử lý bias/requantize/ReLU, DMA theo chuỗi descriptor, scratchpad ping-pong) gắn vào Rocket RV32IMAC qua AXI4-Lite (MMIO) và AXI4 (DMA).

## Cấu trúc thư mục

```
gemm-accel/
├── docs/                       spec đã chốt (PDF + mã LaTeX)
│   ├── system/                 spec hệ thống v1.0 — port top level, register map: KHÓA CỨNG
│   ├── algorithm/              thuật toán GEMM, systolic, VPU
│   ├── modules/<module>/       spec chi tiết từng module (port nội bộ, timing, assertion)
│   └── common/preamble.tex     preamble LaTeX dùng chung cho spec module
├── model/                      golden Python dùng chung cho mọi cấp test
│   ├── gemm_golden.py          GEMM + bias/requant/ReLU, ghi file testcase
│   ├── gemm_*_model.py         mô hình từng module (đã kiểm chứng khi viết spec)
│   └── gen/                    script sinh testcase vào src/tc/
├── src/
│   ├── rtl/                    RTL SystemVerilog
│   │   ├── pkg/gemm_pkg.sv     hằng số, job_t, mã lỗi, offset thanh ghi
│   │   ├── common/             khối dùng chung (reset sync, …)
│   │   ├── <module>/           mỗi module một thư mục + <module>.f
│   │   └── top/                gemm_accel_top.sv (đã nối dây đủ) + top.f
│   ├── tb/                     testbench (harness, viết một lần)
│   │   ├── common/             BFM, package tiện ích dùng chung
│   │   ├── unit/<module>/      tb_<module>.sv + tb_<module>.f
│   │   ├── integ/              ghép vài module (vd. array + vpu + sram)
│   │   └── top/                tb_gemm_accel_top
│   ├── tc/                     testcase (chỉ dữ liệu, sinh từ model/gen)
│   │   ├── unit/<module>/<tên>/   integ/<tên>/   top/<tên>/
│   └── sim/                    chạy mô phỏng
│       ├── Makefile            make sim TB=… TC=…
│       ├── tools/              questa.mk (chính), verilator.mk (CI)
│       ├── regress/            *.list: mỗi dòng "<TB> <TC> [BIẾN=…]"
│       ├── scripts/run_regress.py
│       └── out/                (gitignore) log, waveform của từng lượt chạy
├── syn/vivado/synth.tcl        synth OOC và schematic bằng Vivado
├── sw/include/                 header C cho driver bare-metal (register map)
└── .github/                    CI (lint), CODEOWNERS
```

## Bắt đầu

```bash
git clone <url> gemm-accel && cd gemm-accel
make help
make lint                                       # Verilator lint toàn bộ RTL, 3 cấu hình
make sim  TB=tb_gemm_vpu TC=unit/vpu/basic      # QuestaSim (mặc định)
make gui  TB=tb_gemm_vpu TC=unit/vpu/basic      # Questa GUI, tự add wave
make regress LIST=unit SEEDS=1,2,3
make synth     TOP=gemm_vpu GENERICS="P=4"      # Vivado: báo cáo ở syn/out/gemm_vpu/
make schematic TOP=gemm_systolic_array          # Vivado GUI: schematic RTL
```

Công cụ: **QuestaSim** (mô phỏng), **Vivado** (synth, schematic), **Python 3** (mô hình, sinh testcase), Verilator 5 (chỉ để lint và CI), XeLaTeX (build lại spec).

## Quy ước

**RTL**
- Port của `gemm_accel_top` theo spec hệ thống mục 6 — không ai được sửa.
- Port của 6 module chính đã khớp spec module và đã nối trong top. File hiện là **stub** (mọi output bằng 0). Người phụ trách viết module con, thay stub, giữ nguyên port. Muốn đổi port nội bộ thì sửa spec module trong **cùng Pull Request**.
- Mỗi file `.sv` mới phải được thêm vào `<module>.f` của module đó (module con trước, module chính cuối). Filelist dùng `-F`, đường dẫn tương đối theo vị trí file `.f`.
- Hằng số dùng ở hơn một module khai báo trong `gemm_pkg.sv`, một lần (ví dụ `VPU_LATENCY`).
- Tên port: `i_*` vào, `o_*` ra; reset `rst_n` bất đồng bộ tích cực thấp; clock `clk`.

**Testbench và testcase**
- `tb` là harness, `tc` là dữ liệu. Thêm test mới = thêm thư mục trong `src/tc/`, không sửa tb.
- tb nhận testcase qua plusarg `+TC_DIR=<thư mục>` (Makefile tự truyền) và `+SEED=<n>`.
- tb kết thúc bằng đúng **một dòng** `TEST PASSED (...)` hoặc `TEST FAILED: ...`; script regress chỉ đọc dòng này.
- Filelist của tb nằm cạnh tb, cùng tên: `src/tb/**/tb_<x>.f`.
- Expected của mọi testcase sinh từ `model/`, không viết tay.

**Git**
- `main` được bảo vệ: chỉ merge qua Pull Request, CI phải xanh, có ít nhất một người review.
- Nhánh: `feat/<module>-<việc>`, `fix/<module>-<việc>`, `docs/<việc>`.
- Không commit thư mục `out/`, waveform, file tạm của Questa/Vivado (đã có `.gitignore`).

## Phân công

| Module | Thư mục RTL | Spec | Người phụ trách |
|---|---|---|---|
| Systolic array | `src/rtl/systolic_array` | `docs/modules/systolic_array` | |
| VPU | `src/rtl/vpu` | `docs/modules/vpu` | |
| Scratchpad | `src/rtl/local_sram` | `docs/modules/local_sram` | |
| DMA | `src/rtl/dma_engine` | `docs/modules/dma_engine` | |
| Main FSM | `src/rtl/main_fsm` | `docs/modules/main_fsm` | |
| Register File | `src/rtl/register_file` | `docs/modules/register_file` | |
| Top, tích hợp | `src/rtl/top`, `src/tb/top` | `docs/system` | |

Điền tên vào bảng và vào `.github/CODEOWNERS` khi đã chia việc.
