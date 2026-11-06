# gemm-accel — Bộ tăng tốc GEMM INT8 trên Chipyard SoC

Đồ án ba thành viên: accelerator INT8, systolic array Output-Stationary P×P, VPU bias/requantize/ReLU, DMA descriptor và scratchpad ping-pong. Kết nối Rocket RV32IMAC qua AXI4-Lite (MMIO) và AXI4 (DMA).

## Cấu trúc thư mục

```text
gemm-accel/
├── docs/
│   ├── system/                         spec hệ thống, PDF + LaTeX
│   ├── algorithm/                      thuật toán
│   ├── modules/<module>/               spec từng khối
│   ├── verification/                   vplan/checklist; hiện có reset_sync_vplan.md
│   └── common/preamble.tex
├── model/
│   ├── gemm_golden.py                  golden GEMM/VPU, hàm ghi dữ liệu
│   ├── gemm_*_model.py                 model từng khối
│   └── gen/gen_reset_sync_tc.py        generator mẫu có thể chạy
├── src/
│   ├── rtl/
│   │   ├── pkg/                        gemm_pkg.sv, pkg.f
│   │   ├── common/                     gemm_reset_sync.sv, common.f
│   │   ├── <module>/                   RTL module con và <module>.f
│   │   └── top/                        gemm_accel_top.sv, top.f
│   ├── tb/
│   │   ├── common/                     BFM/task/package mô phỏng dùng chung
│   │   ├── unit/
│   │   │   ├── reset_sync/             harness mẫu, .f, default_tc/tc.sv
│   │   │   └── <module>/               tb_<module>.sv và filelist cùng tên
│   │   ├── integ/                      harness tích hợp vài khối
│   │   └── top/                        harness toàn accelerator
│   ├── tc/
│   │   ├── unit/
│   │   │   ├── reset_sync/
│   │   │   │   ├── TC_RST_001/tc.sv     directed TC
│   │   │   │   ├── TC_RST_002/tc.sv     directed TC
│   │   │   │   ├── random_s101/         stim.txt + meta.json, không có tc.sv
│   │   │   │   └── random_s102/         dữ liệu Python mẫu đã commit
│   │   │   └── <module>/<TC_ID>/
│   │   ├── integ/<TC_ID>/
│   │   └── top/<TC_ID>/
│   └── sim/
│       ├── Makefile                    chọn TB/TC và backend
│       ├── tools/                      questa.mk (mặc định), verilator.mk
│       ├── regress/
│       │   ├── reset_sync/             pat.list (directed), random.list (Python)
│       │   ├── <module>/pat.list        danh sách riêng từng unit
│       │   ├── unit.list               danh sách tổng, hiện chứa reset mẫu
│       │   ├── smoke.list              bộ ngắn, hiện chứa reset mẫu
│       │   ├── integ.list              chưa có test
│       │   └── top.list                chưa có test
│       ├── scripts/run_regress.py      chạy list, lưu và đọc lại báo cáo
│       └── out/                        build/log/wave/report (gitignore)
├── Makefile                            đầy đủ lệnh, tham số và ví dụ: make help
├── syn/vivado/synth.tcl
├── sw/include/gemm_regs.h
└── .github/                            CI lint và CODEOWNERS
```

## Bắt đầu với ví dụ chạy được

Từ gốc repo:

```bash
make help
make lint LINT_F=src/rtl/common/common.f LINT_TOP=gemm_reset_sync
make sim SIM=verilator TB=tb_gemm_reset_sync TC=unit/reset_sync/TC_RST_001
make regress SIM=verilator LIST=reset_sync/pat
make regress SIM=verilator LIST=reset_sync/random SEEDS=7,8
```

Questa vẫn là simulator mặc định: bỏ `SIM=verilator` nếu máy dùng Questa. Module mà người dùng gọi là sync_rst_n hiện có tên **`gemm_reset_sync`**, output **`rst_n_sync`**; ví dụ kiểm tra chính RTL đó, không đổi tên/port.

RTL sáu khối GEMM chính vẫn là stub; các harness khác chưa được viết. Lệnh reset mẫu chạy được, còn lệnh register file/VPU/DMA cần người phụ trách thêm TB/TC và điền pat.list. Các list unit chưa có test để trống có chủ đích; chạy list rỗng sẽ báo lỗi.

## Phiên bản công cụ đề xuất cho nhóm

Các phiên bản đề xuất dưới đây dựa trên máy hiện tại (kiểm tra ngày **06/11/2026**), không phải yêu cầu tất cả công cụ phải giống chính xác từng phiên bản. NumPy và GTKWave chưa cài trên máy; phiên bản đề xuất là bản có trong kho Ubuntu 24.04.

| Công cụ | Phiên bản đề xuất | Mức cần thiết / yêu cầu thống nhất |
|---|---|---|
| Hệ điều hành | Ubuntu **24.04 LTS**, x86-64 | Môi trường đề xuất, không bắt buộc; Windows có thể dùng Ubuntu 24.04 trong WSL2. Không cần cùng point release. |
| Verilator | **5.020**, gói Ubuntu `5.020-1` | Cả ba cần cho lint/mô phỏng chung; nên dùng **cùng phiên bản** để đối chiếu kết quả. |
| GCC / G++ | **13.3.0** | Bắt buộc để build executable Verilator; cần hỗ trợ C++ coroutine cho `--timing`, không bắt buộc cùng phiên bản chính xác. |
| GNU Make | **4.3** | Bắt buộc cho build và regression; không bắt buộc cùng phiên bản chính xác. |
| Python | **3.12.3** | Cần cho model, generator và regression; nên cùng dòng **3.12.x**. |
| NumPy | **1.26.4** | Cần khi chạy model systolic array; nên cùng phiên bản nếu dùng để sinh random testcase. |
| GTKWave | **3.3.116** | Tùy chọn, dùng xem waveform FST/VCD; không bắt buộc cùng phiên bản. |

Ưu tiên thống nhất Verilator và môi trường sinh dữ liệu Python/NumPy. Các phiên bản compiler và Make là mốc tham chiếu; vẫn cập nhật bản vá hệ điều hành bình thường. Bộ đề xuất chưa phải xác nhận toàn bộ chức năng vì repo chưa có đầy đủ RTL/TB.

Verilator 5.020 đã thử với flow `--binary --timing --assert` của project. Nếu cần tính năng hoặc sửa lỗi ở phiên bản mới, cả nhóm thống nhất nâng và chạy lại lint/regression; không tự đổi một máy sang `latest`/`master`. Các bản mới hỗ trợ SV rộng hơn, nên hạn chế của 5.020 không đại diện cho mọi bản Verilator.

### Cài và kiểm tra môi trường

Trên Ubuntu 24.04 hoặc Ubuntu 24.04 trong WSL2:

```bash
sudo apt update
sudo apt install verilator=5.020-1 gcc-13 g++-13 make python3 python3-numpy
# Tùy chọn nếu cần xem waveform
sudo apt install gtkwave

verilator --version
g++ -dumpfullversion
make --version | head -1
python3 --version
python3 -c 'import numpy; print(numpy.__version__)'
# Chỉ kiểm tra khi đã cài GTKWave
gtkwave --version
```

Nếu máy có nhiều compiler, kiểm tra `g++` mặc định có tương thích flow Verilator. Các lệnh apt ngoài Verilator lấy bản candidate trong kho Ubuntu, không khóa chính xác mọi phiên bản. Không cần cài NumPy bằng pip nếu đã dùng `python3-numpy`; khi dùng venv riêng và cần tái hiện dữ liệu, cài `numpy==1.26.4` trong venv đó.

CI hiện dùng Ubuntu 24.04 và cài Verilator bằng apt nhưng chưa pin phiên bản trong workflow. Trước khi đổi compiler/Verilator, chạy lại `make lint` và các regression đã có. Lưu phiên bản tool, data seed và simulation seed khi báo lỗi.

## Quy ước file nguồn và liên kết TB/TC

| Thành phần | Đặt ở đâu | Ghi vào file nào |
|---|---|---|
| Module chính và module con | `src/rtl/<module>/<tên_module>.sv` | `<module>.f`, module con trước module chính |
| RTL chung | `src/rtl/common/` | `common.f` |
| Kiểu/hằng số chung | `src/rtl/pkg/gemm_pkg.sv` | `pkg.f`, compile trước nơi dùng |
| Harness unit | `src/tb/unit/<module>/tb_<tên>.sv` | `tb_<tên>.f` cùng thư mục |
| Driver/checker/BFM chung | `src/tb/common/` | Filelist TB cần sử dụng; không đưa vào RTL synth |
| Harness integration/top | `src/tb/integ/`, `src/tb/top/` | Filelist cạnh TB |
| Directed TC | `src/tc/<cấp>/<module hoặc TC_ID>/.../tc.sv` | Không compile riêng, TB include qua Makefile |
| TC dữ liệu | Thư mục TC không có `tc.sv` | TB dùng `default_tc/tc.sv` đọc file qua TC_DIR |
| Generator | `model/gen/` | Sinh dữ liệu vào `src/tc/`, không ghi vào thư mục TB |
| Vplan | `docs/verification/<module>_vplan.md` | TC ID khớp ID trong checklist |
| Pattern list | `src/sim/regress/<module>/pat.list` | Liệt kê các TB/TC muốn chạy |

**Filelist compile và pattern list khác nhau:** `.f` liệt kê source/tùy chọn biên dịch; `pat.list` liệt kê testcase để runner lần lượt gọi mô phỏng. Không đưa toàn bộ `tc.sv` vào `.f`, vì mỗi TC cùng định nghĩa `run_tc()`.

Ví dụ thực tế `src/tb/unit/reset_sync/tb_gemm_reset_sync.f`:

```text
-F ../../../rtl/common/common.f
tb_gemm_reset_sync.sv
```

Đường dẫn trong filelist dùng `-F` tính từ vị trí file `.f` đó. Package phải xuất hiện trước nơi dùng và không compile lặp qua nhiều filelist. Giữ nguyên port top theo spec hệ thống; thay đổi port nội bộ phải cập nhật spec module cùng PR.

### Directed TC viết tay theo vplan

Harness sở hữu DUT, clock/reset, task API, checker, bộ đếm lỗi, timeout và kết thúc test. File TC chỉ định nghĩa `run_tc()` trong scope của harness, không tạo module hoặc `initial` riêng:

```systemverilog
// src/tc/unit/reset_sync/TC_RST_001/tc.sv
task automatic run_tc();
  assert_reset();
  hold_reset(2);
  release_reset();
endtask
```

Trong harness có `` `include "tc.sv" `` và `initial` gọi `run_tc()`. Makefile ưu tiên `<TC_DIR>/tc.sv`; nếu không có, chọn `<thư mục TB>/default_tc/tc.sv`. Không đặt file `tc.sv` ngay cạnh TB để tránh compiler chọn nhầm thay vì include path đã chọn.

Ví dụ reset có các task đơn giản `assert_reset`, `hold_reset`, `release_reset`, `check_reset`. Driver đổi input ngoài posedge, checker sample sau khi nonblocking update hoàn tất. TC thứ hai minh họa reassert và xung reset ngắn hoàn toàn giữa hai cạnh lên. Xem [vplan reset](docs/verification/reset_sync_vplan.md), [harness](src/tb/unit/reset_sync/tb_gemm_reset_sync.sv) và [TC mẫu](src/tc/unit/reset_sync/TC_RST_001/tc.sv).

Với register file, người phụ trách áp dụng cùng cấu trúc: task `axi_lite_write`, `axi_lite_read_check`, check START/snapshot; mỗi TC ID tương ứng item vplan. Driver và monitor chạy đồng thời khi giao thức yêu cầu. Directed test được phép dùng expected theo spec/vplan hoặc reference model SV của harness; dữ liệu GEMM/VPU và random tính toán dùng golden Python chung trong `model/`.

Log mẫu (rút gọn):

```text
[TC] TC_RST_001
[t =    12 ns] [assert                  ] rst_n=0 | rst_n_sync exp=0 act=0 | PASS
[t =    16 ns] [hold                    ] rst_n=0 | rst_n_sync exp=0 act=0 | PASS
...
[t =    46 ns] [release: posedge 2      ] rst_n=1 | rst_n_sync exp=1 act=1 | PASS
TEST PASSED (TC_RST_001)
```

Log check ưu tiên `[t = ...] [action/checkpoint] <input>=... | <output> exp=... act=... | PASS/FAIL`; TC_ID in một lần ở đầu. Thời điểm là lúc capture output; action/checkpoint ghi điều kiện hoặc pha đang kiểm tra, không nhất thiết input đổi ngay lúc đó. Mỗi dòng phải ghi tên output và input/trạng thái cần thiết để khoanh vùng lỗi. Với nhiều output, in từng output một dòng tại cùng checkpoint. Hạn chế mô tả hành động bằng chữ; chỉ thêm ngữ cảnh ngắn khi hành vi phức tạp cần debug. Regression in TC_ID trước mỗi lượt, kết quả ngắn và bảng tổng hợp; chi tiết check nằm trong log từng lượt.

Chỉ một kết luận `TEST PASSED (...)` hoặc `TEST FAILED: ...` từ TB sau khi mọi check hoàn tất; lỗi phải trả mã thoát khác 0. Watchdog in `TEST FAILED: TIMEOUT ...`. Backend có thể nhắc lại kết luận trong stdout; runner ưu tiên mọi FAIL và không suy PASS từ dòng check riêng lẻ. Test chủ động inject lỗi DUT vẫn PASS nếu xử lý lỗi đúng spec. Không báo PASS nếu chưa có check.

### TC dữ liệu do Python sinh

Generator mẫu thực tế `model/gen/gen_reset_sync_tc.py` sinh lịch reset, mỗi dòng `stim.txt` là hai số thập phân `hold_cycles release_delay_ns`. `default_tc/tc.sv` đọc file, kiểm format rồi gọi lại task API của harness. Expected reset là hành vi RST-01 do checker kiểm trực tiếp; ví dụ này không cần file expected số học.

```bash
# Tạo TC random_s201 và random_s202; không ghi đè thư mục đã tồn tại
make gen-tc GEN=model/gen/gen_reset_sync_tc.py GEN_ARGS="--seed 201 --count 2 --vectors 4"

# Chạy một TC Python vừa sinh
make sim SIM=verilator TB=tb_gemm_reset_sync TC=unit/reset_sync/random_s201 SEED=7
```

Data seed `--seed 201` quyết định nội dung file; simulation seed `SEED=7` quyết định random mà TB/BFM sử dụng. TB reset mẫu không random runtime, nên đổi SEED không đổi lịch stimulus. Với AXI có thể random stall theo simulation seed. Generator dùng `random.Random(data_seed)`, lưu `meta.json`; giữ file đầu vào và seed khi có lỗi. Chạy `make models` không tự sinh TC và không chạy RTL.

Với array/VPU, generator gọi `gemm_golden.gemm/post` hoặc model module, ghi input/expected và format cấu hình được TB thống nhất. TB dữ liệu chỉ đọc và drive/check; Makefile không tự hiểu `.hex` hay JSON. Random cần ràng buộc theo spec, không thay thế directed test reset/biên/lỗi trong vplan.

## Các lệnh compile, sim, GUI và lint

`make help` hoặc phần comment đầu Makefile gốc liệt kê toàn bộ cú pháp và ví dụ. Các tùy chọn chung:

| Tham số | Ý nghĩa |
|---|---|
| `TB` | Tên module TB, cũng là tên file `.f` không đuôi; phải duy nhất trong src/tb |
| `TC` | Đường dẫn dưới src/tc; chọn tc.sv riêng hoặc dữ liệu cho default_tc |
| `SIM` | questa mặc định, hoặc verilator |
| `SEED` / `SEEDS` | Một simulation seed / danh sách seed trong regression; số nguyên dương |
| `PARAMS="NAME=value ..."` | Parameter **của TB**, TB truyền xuống DUT; reset mẫu có CLK_HALF_NS >= 5 |
| `PLUSARGS="+NAME=value ..."` | Runtime option, chỉ có tác dụng nếu TB/BFM đọc |
| `DEFINES="+define+NAME ..."` | Macro compile |
| `WAVES=1` | Bật FST cho Verilator, TB phải có khối dump dưới macro WAVES |

```bash
# Chỉ biên dịch directed TC
make comp SIM=verilator TB=tb_gemm_reset_sync TC=unit/reset_sync/TC_RST_001

# Directed TC bằng Questa mặc định / Verilator
make sim TB=tb_gemm_reset_sync TC=unit/reset_sync/TC_RST_001
make sim SIM=verilator TB=tb_gemm_reset_sync TC=unit/reset_sync/TC_RST_002

# Cùng harness, một TC Python có sẵn trong repo
make sim SIM=verilator TB=tb_gemm_reset_sync TC=unit/reset_sync/random_s101 SEED=7

# Parameter compile-time của harness
make sim SIM=verilator TB=tb_gemm_reset_sync TC=unit/reset_sync/TC_RST_001 PARAMS="CLK_HALF_NS=10"

# GUI Questa: directed / Python; add wave và chạy
make gui TB=tb_gemm_reset_sync TC=unit/reset_sync/TC_RST_001
make gui TB=tb_gemm_reset_sync TC=unit/reset_sync/random_s101

# Verilator không có GUI: ghi FST rồi mở GTKWave
make sim SIM=verilator TB=tb_gemm_reset_sync TC=unit/reset_sync/TC_RST_001 WAVES=1
gtkwave src/sim/out/verilator/tb_gemm_reset_sync/run/unit__reset_sync__TC_RST_001_s1/waves.fst

# Lint toàn bộ RTL theo 3 cấu hình hiện tại; không chạy TC
make lint
# Lint một khối: filelist phải chứa đủ dependencies/package nếu có
make lint LINT_F=src/rtl/common/common.f LINT_TOP=gemm_reset_sync
make lint LINT_F=src/rtl/vpu/vpu.f LINT_TOP=gemm_vpu LINT_PARAMS="P=4"
```

`make comp TB=tb_gemm_reset_sync` có thể bỏ TC để compile default reader. `make sim` luôn cần TC hợp lệ. Lint luôn dùng Verilator, không phụ thuộc SIM.

## Pattern list, regression và báo cáo

Format `pat.list` (hoặc bất cứ file list nào):

```text
# <TB> <TC> [NAME=value ...]
tb_gemm_reset_sync unit/reset_sync/TC_RST_001
tb_gemm_reset_sync unit/reset_sync/TC_RST_002 PARAMS="CLK_HALF_NS=10"
```

Hỗ trợ dòng trống, comment `#` (kể cả cuối dòng) và dòng comment bắt đầu `//`. Tùy chọn từng dòng ghi đè tùy chọn chung; TB/TC/SIM/SEED dùng các trường/tham số riêng, không ghi đè bằng assignment cuối dòng. Cùng format cho unit, integ, top, directed và Python. Có thể trộn các loại trong một list.

```bash
# Toàn bộ directed TC của unit reset; Questa mặc định
make regress LIST=reset_sync/pat
# Trên máy dùng Verilator
make regress SIM=verilator LIST=reset_sync/pat

# Regression Python có sẵn: 2 data seed x 2 simulation seed = 4 lượt
make regress SIM=verilator LIST=reset_sync/random SEEDS=7,8 TIMEOUT=300

# Dùng một file danh sách bất kỳ; PATLIST ưu tiên hơn LIST
make regress SIM=verilator PATLIST=src/sim/regress/reset_sync/pat.list

# Bộ tổng unit / smoke; hiện chỉ chứa 2 directed TC reset
make regress SIM=verilator LIST=unit
make regress SIM=verilator LIST=smoke
# Integration/top: điền test vào list tương ứng trước khi chạy
make regress LIST=integ
make regress LIST=top
```

Để regress các TC mới sinh `random_s201/202`, thêm hai dòng tương ứng vào list Python rồi dùng cùng lệnh regress. Không cần generator riêng cho regression. Khi cần truyền WAVES/PARAMS/PLUSARGS/DEFINES chung, đặt trên lệnh `make regress` như trên `make sim`.

Mỗi đợt regression tạo thư mục độc lập và in đường dẫn:

```text
src/sim/out/regress/<run_id>/
├── pat.list                        bản chụp danh sách đã chạy
├── results.json                    từng job, seed, command, status, log, thời gian
├── report.txt                      bảng tổng hợp dễ đọc
└── logs/0001.log ...                stdout/stderr compile + sim của từng lượt
```

Ví dụ bảng:

```text
PATTERN               | SIM    | SEED | RESULT
----------------------+--------+------+-------
reset_sync-TC_RST_001  | questa | 1    | PASS
reset_sync-TC_RST_002  | questa | 1    | PASS
TOTAL=2  PASS=2  FAIL=0  ERROR=0  TIMEOUT=0  NOT_RUN=0
```

- PASS: simulator/build thành công, có kết luận PASS và không có FAIL.
- FAIL: checker báo TEST FAILED; ERROR: compile/simulator lỗi hoặc thiếu kết luận.
- TIMEOUT: watchdog TB hoặc runner quá TIMEOUT giây (gồm cả compile).
- NOT_RUN: lượt chưa được chạy nếu đợt bị ngắt; runner lưu trạng thái ban đầu trước khi chạy.

Runner tiếp tục sau lỗi từng TC; trả mã thoát khác 0 khi có kết quả không PASS. List rỗng/sai format bị từ chối. Log regression riêng tránh dùng nhầm log cũ; log đơn lẻ cũng được backend lưu như bên dưới.

In lại báo cáo, **không mô phỏng lại** (thay `<run_id>` bằng đường dẫn runner đã in):

```bash
make report RUN=src/sim/out/regress/<run_id>
# Hoặc gọi trực tiếp Python
python3 src/sim/scripts/run_regress.py --report src/sim/out/regress/<run_id>/results.json
```

Báo cáo có test không PASS cũng trả mã thoát khác 0. Chạy trực tiếp runner:

```bash
python3 src/sim/scripts/run_regress.py src/sim/regress/reset_sync/pat.list --sim verilator --seeds 1 --timeout 300
```

### Build và log một TC

```text
src/sim/out/<sim>/<TB><PTAG>/
├── build_unit__reset_sync__TC_RST_001/  TC có SV riêng
├── build_default/                     các TC dữ liệu dùng chung reader
└── run/unit__reset_sync__TC_RST_001_s1/
    ├── sim.log
    └── waves.fst hoặc vsim.wlf
```

PTAG biểu diễn PARAMS, dấu `/` trong TC đổi thành `__`. Mỗi sim gọi comp; chia sẻ đường dẫn build không có nghĩa đã cache mọi cấu hình. Không chạy đồng thời các lệnh dùng cùng build/run. Lưu report trước `make clean`, vì clean xóa cả src/sim/out.

## Các lệnh khác và làm việc nhóm

```bash
make synth TOP=gemm_vpu GENERICS="P=4"
make schematic TOP=gemm_systolic_array
make models
make docs
make clean
```

Không commit out/wave/build. Commit generator và các vector regression cần tái hiện. Nhánh `feat/<module>-<việc>`, `fix/<module>-<việc>`, `docs/<việc>`; merge qua PR/review theo quy định nhóm. Không copy checker/clock/DUT vào từng TC; thêm hành vi mới bằng API trong harness rồi dùng lại ở các testcase.

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
