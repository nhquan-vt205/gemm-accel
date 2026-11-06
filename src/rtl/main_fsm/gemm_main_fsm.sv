// =============================================================================
// gemm_main_fsm.sv — STUB (chưa hiện thực)
// Spec : docs/modules/main_fsm/gemm_main_fsm_spec.pdf
// Module con cần viết: gemm_fsm_ctrl, gemm_job_check, gemm_rd_engine, gemm_cp_engine, gemm_wr_engine, gemm_bank_sb
//
// Port list dưới đây đã khớp spec và đã được nối trong gemm_accel_top.
// Người phụ trách: giữ nguyên tên/độ rộng port; muốn đổi port thì sửa spec trong cùng PR.
// Khi bắt đầu hiện thực: xóa khối 'STUB' và hai dòng lint_off bên dưới.
// =============================================================================
/* verilator lint_off UNUSEDSIGNAL */
/* verilator lint_off UNUSEDPARAM */
module gemm_main_fsm #(
  parameter int P = 8,
  parameter int HAS_CHAIN = 1,
  parameter int HAS_PINGPONG = 1
) (
  input  logic              clk,
  input  logic              rst_n,
  output logic              o_soft_clr,
  output logic              o_soft_busy,
  // ---- Register File -> FSM
  input  logic              i_start_pulse,
  input  logic [1:0]        i_start_kind,
  input  logic              i_soft_req,
  input  logic [31:0]       i_cfg_dim,
  input  logic [31:0]       i_cfg_a_addr,
  input  logic [31:0]       i_cfg_b_addr,
  input  logic [31:0]       i_cfg_c_addr,
  input  logic [31:0]       i_cfg_post_ctrl,
  input  logic [31:0]       i_cfg_bias_addr,
  input  logic [31:0]       i_cfg_qm0,
  input  logic [31:0]       i_cfg_qshift,
  input  logic [31:0]       i_cfg_desc_ptr,
  // ---- FSM -> Register File
  output logic              o_done_pulse,
  output logic              o_err_pulse,
  output logic [3:0]        o_err_code,
  output logic              o_perf_load,
  output logic              o_perf_comp,
  output logic              o_perf_store,
  output logic [31:0]       o_err_desc_addr,
  output logic [31:0]       o_desc_done_cnt,
  // ---- Lệnh kênh đọc DMA
  output logic              o_rd_start,
  output logic [1:0]        o_rd_dst,
  output logic [31:0]       o_rd_base,
  output logic [5:0]        o_rd_rows,
  output logic [5:0]        o_rd_rwords,
  output logic [15:0]       o_rd_stride,
  output logic              o_rd_bank,
  output logic              o_rd_abort,
  input  logic              i_rd_busy,
  input  logic              i_rd_done,
  input  logic              i_rd_error,
  input  logic              i_desc_valid,
  input  logic [3:0]        i_desc_idx,
  input  logic [31:0]       i_desc_data,
  // ---- Lệnh kênh ghi DMA
  output logic              o_wr_start,
  output logic              o_wr_fmt,
  output logic [31:0]       o_wr_base,
  output logic [5:0]        o_wr_rows,
  output logic [5:0]        o_wr_rwords,
  output logic [15:0]       o_wr_stride,
  output logic              o_wr_bank,
  output logic              o_wr_abort,
  input  logic              i_wr_busy,
  input  logic              i_wr_done,
  input  logic              i_wr_error,
  // ---- Array, VPU, scratchpad phía tính
  output logic              o_pe_start,
  input  logic              i_pe_done,
  input  logic              i_pe_busy,
  output logic [31:0]       o_comp_dim,
  output logic              o_comp_post_en,
  output logic              o_comp_relu_en,
  output logic [31:0]       o_comp_qm0,
  output logic [4:0]        o_comp_qshift,
  output logic              o_comp_bank_a,
  output logic              o_comp_bank_b,
  output logic              o_comp_bank_bias,
  output logic              o_comp_bank_c,
  output logic              o_comp_active
);

  // ---- STUB: mọi output bằng 0. Xóa khối này khi hiện thực. ----
  assign o_soft_clr = '0;
  assign o_soft_busy = '0;
  assign o_done_pulse = '0;
  assign o_err_pulse = '0;
  assign o_err_code = '0;
  assign o_perf_load = '0;
  assign o_perf_comp = '0;
  assign o_perf_store = '0;
  assign o_err_desc_addr = '0;
  assign o_desc_done_cnt = '0;
  assign o_rd_start = '0;
  assign o_rd_dst = '0;
  assign o_rd_base = '0;
  assign o_rd_rows = '0;
  assign o_rd_rwords = '0;
  assign o_rd_stride = '0;
  assign o_rd_bank = '0;
  assign o_rd_abort = '0;
  assign o_wr_start = '0;
  assign o_wr_fmt = '0;
  assign o_wr_base = '0;
  assign o_wr_rows = '0;
  assign o_wr_rwords = '0;
  assign o_wr_stride = '0;
  assign o_wr_bank = '0;
  assign o_wr_abort = '0;
  assign o_pe_start = '0;
  assign o_comp_dim = '0;
  assign o_comp_post_en = '0;
  assign o_comp_relu_en = '0;
  assign o_comp_qm0 = '0;
  assign o_comp_qshift = '0;
  assign o_comp_bank_a = '0;
  assign o_comp_bank_b = '0;
  assign o_comp_bank_bias = '0;
  assign o_comp_bank_c = '0;
  assign o_comp_active = '0;
  // ---- hết STUB ----

endmodule
/* verilator lint_on UNUSEDPARAM */
/* verilator lint_on UNUSEDSIGNAL */
