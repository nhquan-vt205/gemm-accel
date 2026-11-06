// =============================================================================
// gemm_pkg.sv — hằng số và kiểu dùng chung cho toàn bộ accelerator
// Nguồn: spec hệ thống v1.0 (mục 3, 7), spec gemm_vpu (VPU-P02),
//        spec gemm_main_fsm (bảng 4-2: job_t)
// Quy tắc: mọi hằng số dùng ở hơn một module phải khai báo ở đây, một lần.
// =============================================================================
/* verilator lint_off UNUSEDPARAM */  // hằng số chung: không phải module nào cũng dùng hết
package gemm_pkg;

  // ---- Phiên bản spec (HW_CONFIG[31:24]) -----------------------------------
  localparam logic [7:0] SPEC_VER = 8'h10;
  localparam int         MAX_DIM  = 32;

  // ---- VPU (spec gemm_vpu, VPU-P02) ----------------------------------------
  localparam int VPU_MUL_STAGES = 1;                    // 1 hoặc 2
  localparam int VPU_LATENCY    = 3 + VPU_MUL_STAGES;   // = L_VPU của array

  // ---- Mã lỗi STATUS.ERR_CODE (bảng 3-3 spec hệ thống) ---------------------
  localparam logic [3:0] ERR_NONE   = 4'd0;
  localparam logic [3:0] ERR_CFG    = 4'd1;
  localparam logic [3:0] ERR_AXI_RD = 4'd2;
  localparam logic [3:0] ERR_AXI_WR = 4'd3;
  localparam logic [3:0] ERR_FETCH  = 4'd4;
  localparam logic [3:0] ERR_NOFEAT = 4'd5;

  // ---- Offset thanh ghi MMIO (bảng 3-1 spec hệ thống) ----------------------
  localparam logic [11:0] REG_CTRL          = 12'h000;
  localparam logic [11:0] REG_STATUS        = 12'h004;
  localparam logic [11:0] REG_MATRIX_DIM    = 12'h008;
  localparam logic [11:0] REG_BASE_IN       = 12'h00C;
  localparam logic [11:0] REG_BASE_WEIGHT   = 12'h010;
  localparam logic [11:0] REG_BASE_OUT      = 12'h014;
  localparam logic [11:0] REG_POST_CTRL     = 12'h018;
  localparam logic [11:0] REG_BIAS_ADDR     = 12'h01C;
  localparam logic [11:0] REG_QUANT_M0      = 12'h020;
  localparam logic [11:0] REG_QUANT_SHIFT   = 12'h024;
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
