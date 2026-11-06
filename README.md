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
│   ├── tc/                     testcase SV hoặc dữ liệu sinh từ model/gen
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
- `tb` là harness dùng chung: DUT, clock/reset, BFM, task API, monitor và scoreboard. Testcase là `tc.sv` chứa task `run_tc()` hoặc dữ liệu do Python sinh.
- TB đặt dòng `` `include "tc.sv" `` trong module và gọi `run_tc()`. Nếu thư mục TC có `tc.sv`, Makefile chọn nó và build riêng; nếu không, dùng `<thư mục tb>/default_tc/tc.sv` và build chung cho các TC dữ liệu.
- Không đặt `tc.sv` ngay cạnh TB, không khai báo module/DUT trong `tc.sv` và không thêm nó như source riêng vào filelist. Thêm pattern dùng API sẵn có không cần sửa TB; hành vi mới có thể cần bổ sung API/checker.
- tb nhận testcase qua plusarg `+TC_DIR=<thư mục>` (Makefile tự truyền) và `+SEED=<n>`.
- tb kết thúc bằng đúng **một dòng** `TEST PASSED (...)` hoặc `TEST FAILED: ...`; script regress chỉ đọc dòng này.
- Filelist của tb nằm cạnh tb, cùng tên: `src/tb/**/tb_<x>.f`.
- Expected của mọi testcase sinh từ `model/`, không viết tay.

**Git**
- `main` được bảo vệ: chỉ merge qua Pull Request, CI phải xanh, có ít nhất một người review.
- Nhánh: `feat/<module>-<việc>`, `fix/<module>-<việc>`, `docs/<việc>`.
- Không commit thư mục `out/`, waveform, file tạm của Questa/Vivado (đã có `.gitignore`).

## Tổ chức testcase SV và dữ liệu Python

Questa là simulator mặc định. Cùng harness và testcase có thể chạy bằng Verilator khi thêm `SIM=verilator`. Dùng directed test theo vplan và random bổ sung; không bắt buộc UVM. Expected tính toán vẫn lấy từ model Python chung.

```text
src/tb/unit/vpu/
├── tb_gemm_vpu.sv
├── tb_gemm_vpu.f
└── default_tc/tc.sv             # run_tc() đọc dữ liệu từ TC_DIR
src/tc/unit/vpu/
├── basic/tc.sv                  # run_tc() viết riêng bằng SV
└── random_s7/                   # không có tc.sv → dùng default_tc
    ├── stim.hex
    └── expected.hex
```

Trong module `tb_gemm_vpu`, khai báo API, biến `tc_dir`, seed và scoreboard, sau đó include testcase:

```systemverilog
// Bên trong module TB; các task này do người viết harness hiện thực.
`include "tc.sv"
initial begin
  if (!$value$plusargs("TC_DIR=%s", tc_dir))
    $fatal(1, "TEST FAILED: thiếu TC_DIR");
  if (!$value$plusargs("SEED=%d", seed)) seed = 1;
  do_reset();
  run_tc();
  drain_and_check(); // đợi đủ output, kiểm scoreboard trước khi báo kết quả
  finish_test();     // một dòng TEST PASSED hoặc TEST FAILED, rồi kết thúc
end
```

Trong `basic/tc.sv` chỉ định nghĩa `task automatic run_tc(); ... endtask`; gọi thẳng các task API như `set_cfg`, `send_row`, `request_soft_clear` của harness. Driver/monitor phải chạy đồng thời khi giao tiếp yêu cầu; harness cần timeout để phát hiện treo. Bản `default_tc/tc.sv` cũng định nghĩa `run_tc()`, nhưng đọc file tại `tc_dir` và dùng cùng API/checker. Format file do TB và generator thống nhất, không tự động được Makefile đọc.

RTL riêng của khối đặt trong `src/rtl/<module>/`, thêm vào `<module>.f`, package trước file dùng nó. TB unit đặt trong `src/tb/unit/<module>/`, BFM dùng chung ở `src/tb/common/`, integration ở `src/tb/integ/`, top ở `src/tb/top/`. Ví dụ `src/tb/unit/vpu/tb_gemm_vpu.f`:

```text
-F ../../../rtl/pkg/pkg.f
-F ../../../rtl/vpu/vpu.f
tb_gemm_vpu.sv
```

Filelist dùng `-F`: đường dẫn tương đối theo file `.f` chứa dòng đó. Include path tới `tc.sv` được backend truyền từ Makefile; không hardcode một TC vào filelist.

Các lệnh sau yêu cầu đã hiện thực TB/TC; repo hiện mới có các thư mục trống:

```bash
# Từ gốc repo: mặc định Questa
make sim TB=tb_gemm_vpu TC=unit/vpu/basic
make gui TB=tb_gemm_vpu TC=unit/vpu/basic
make -C src/sim comp TB=tb_gemm_vpu TC=unit/vpu/basic

# Máy chỉ có Verilator
make sim SIM=verilator TB=tb_gemm_vpu TC=unit/vpu/basic SEED=7
make sim SIM=verilator TB=tb_gemm_vpu TC=unit/vpu/random_s7 WAVES=1
make regress SIM=verilator LIST=unit SEEDS=1,2,3
```

`PARAMS="P=4"` đặt parameter của **TB**, TB phải truyền xuống DUT. Để có FST, TB cần `$dumpfile("waves.fst")` và `$dumpvars(0, tb_gemm_vpu)` dưới `` `ifdef WAVES ``. Verilator cần compiler C++ hỗ trợ timing/coroutine phù hợp với phiên bản đã cài.

Build ở `src/sim/out/<sim>/<TB><PTAG>/build_<TCTAG>/` nếu TC có SV riêng, hoặc `build_default/` nếu dùng default. Log/wave ở `.../<TB><PTAG>/run/<TCTAG>_s<seed>/`; TCTAG thay `/` trong TC bằng `__`, PTAG ghi các PARAMS. Mỗi lệnh sim vẫn gọi compile; các TC dữ liệu dùng chung đường dẫn build. Không chạy đồng thời các lượt dùng cùng thư mục build/run.

Python generator đặt ở `model/gen/`, sinh dữ liệu vào `src/tc/`. Generator phải dùng `random.Random(data_seed)`, ghi seed/config và gọi golden trong `model/` để tính expected. Data seed quyết định dữ liệu file; `SEED` của mô phỏng chỉ đổi random do TB/BFM thực sự sử dụng (ví dụ stall), không tự sinh lại file. Đưa từng thư mục dữ liệu vào regression list để chạy nhiều data seed. Lưu file gây lỗi để tái hiện.

Ưu tiên task/function, `$readmemh`, `$fscanf`, `$urandom_range` và checker đơn giản để dễ dùng chung tool. Chốt phiên bản Verilator và thử các SVA/tính năng SV cần dùng; không mặc định mọi bản hỗ trợ đầy đủ UVM, class constraint hay covergroup. Với random phức tạp, sinh trước bằng Python. Random không thay thế directed test biên/reset/lỗi trong vplan.

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
