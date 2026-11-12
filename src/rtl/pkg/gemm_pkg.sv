// =============================================================================
// gemm_pkg.sv — hằng số và kiểu dùng chung cho toàn bộ accelerator
// Nguồn: spec hệ thống baseline (mục 2: thanh ghi, mã lỗi; mục 5: descriptor), spec gemm_vpu (mục 2),
//        spec gemm_main_fsm (bảng 4-2: job_t)
// Quy tắc: mọi hằng số dùng ở hơn một module phải khai báo ở đây, một lần.
// =============================================================================
/* verilator lint_off UNUSEDPARAM */  // hằng số chung: không phải module nào cũng dùng hết
package gemm_pkg;

  // ---- Phiên bản spec (HW_CONFIG[31:24]) -----------------------------------
  localparam logic [7:0] SPEC_VER = 8'h11;   // 0x11: chỉ chuỗi descriptor + ping-pong (D-03)
  localparam int         MAX_DIM  = 32;

  // ---- VPU (spec gemm_vpu, mục 2) ------------------------------------------
  localparam int VPU_MUL_STAGES = 1;                    // baseline chốt 1; đổi thành 2 là phát hành lại baseline
  localparam int VPU_LATENCY    = 3 + VPU_MUL_STAGES;   // = L_VPU của array

  // ---- Mã lỗi STATUS.ERR_CODE (spec hệ thống, mục 2.2; 5 … 15 dự trữ) ---------------------
  localparam logic [3:0] ERR_NONE   = 4'd0;
  localparam logic [3:0] ERR_CFG    = 4'd1;
  localparam logic [3:0] ERR_AXI_RD = 4'd2;
  localparam logic [3:0] ERR_AXI_WR = 4'd3;
  localparam logic [3:0] ERR_FETCH  = 4'd4;

  // ---- Offset thanh ghi MMIO (spec hệ thống, mục 2.1) ----------------------
  localparam logic [11:0] REG_CTRL          = 12'h000;
  localparam logic [11:0] REG_STATUS        = 12'h004;
  // 0x008 … 0x024 dự trữ (D-01): đọc 0, ghi bị bỏ qua
  localparam logic [11:0] REG_HW_CONFIG     = 12'h028;
  localparam logic [11:0] REG_PERF_TOTAL    = 12'h02C;
  localparam logic [11:0] REG_PERF_LOAD     = 12'h030;
  localparam logic [11:0] REG_PERF_COMPUTE  = 12'h034;
  localparam logic [11:0] REG_PERF_STORE    = 12'h038;
  localparam logic [11:0] REG_DESC_PTR      = 12'h040;
  localparam logic [11:0] REG_ERR_DESC_ADDR = 12'h044;
  localparam logic [11:0] REG_DESC_DONE_CNT = 12'h048;

  // ---- Đích lệnh kênh đọc DMA (spec gemm_dma_engine, i_rd_dst) -------------
  localparam logic [1:0] DST_A    = 2'd0;
  localparam logic [1:0] DST_B    = 2'd1;
  localparam logic [1:0] DST_BIAS = 2'd2;
  localparam logic [1:0] DST_DESC = 2'd3;

  // ---- Định dạng ghi C ------------------------------------------------------
  localparam logic FMT_INT32 = 1'b0;
  localparam logic FMT_INT8  = 1'b1;

  // ---- Job (spec gemm_main_fsm, bảng 4-2) -----------------------------------
  typedef struct packed {
    logic [31:0] idx;
    logic [31:0] daddr;
    logic [5:0]  m, n, k;
    logic [31:0] a, b, c, bias;
    logic [15:0] lda, ldb, ldc;
    logic [31:0] qm0;
    logic [4:0]  qsh;
    logic        post, relu, reuse, waitp, last;
    logic [31:0] next;
    logic        ba, bb, bbias, bc;
  } job_t;

endpackage
/* verilator lint_on UNUSEDPARAM */
