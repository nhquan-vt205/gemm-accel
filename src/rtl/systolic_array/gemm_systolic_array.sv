// =============================================================================
// gemm_systolic_array.sv — STUB (chưa hiện thực)
// Spec : docs/modules/systolic_array/gemm_systolic_array_spec.pdf
// Module con cần viết: gemm_pe, gemm_tile_seq, gemm_skew, gemm_pe_grid, gemm_drain
//
// Port list dưới đây đã khớp spec và đã được nối trong gemm_accel_top.
// Người phụ trách: giữ nguyên tên/độ rộng port; muốn đổi port thì sửa spec trong cùng PR.
// Khi bắt đầu hiện thực: xóa khối 'STUB' và hai dòng lint_off bên dưới.
// =============================================================================
/* verilator lint_off UNUSEDSIGNAL */
/* verilator lint_off UNUSEDPARAM */
module gemm_systolic_array #(
  parameter int P = 8,
  parameter int L_VPU = 4
) (
  input  logic              clk,
  input  logic              rst_n,
  input  logic              i_soft_clr,
  // ---- Điều khiển (FSM)
  input  logic              i_pe_start,
  output logic              o_pe_done,
  output logic              o_busy,
  input  logic [31:0]       i_matrix_dim,
  // ---- Đọc A, B (SRAM, trễ 1)
  output logic              o_a_rd_en,
  output logic [4:0]        o_a_rd_row,
  output logic [4:0]        o_a_rd_k,
  input  logic [8*P-1:0]    i_a_rd_data,
  output logic              o_b_rd_en,
  output logic [4:0]        o_b_rd_k,
  output logic [4:0]        o_b_rd_col,
  input  logic [8*P-1:0]    i_b_rd_data,
  // ---- Luồng hàng kết quả (VPU)
  output logic              o_row_valid,
  output logic [4:0]        o_row_idx,
  output logic [4:0]        o_row_col,
  output logic [32*P-1:0]   o_row_data,
  output logic [P-1:0]      o_row_mask
);

  // ---- STUB: mọi output bằng 0. Xóa khối này khi hiện thực. ----
  assign o_pe_done = '0;
  assign o_busy = '0;
  assign o_a_rd_en = '0;
  assign o_a_rd_row = '0;
  assign o_a_rd_k = '0;
  assign o_b_rd_en = '0;
  assign o_b_rd_k = '0;
  assign o_b_rd_col = '0;
  assign o_row_valid = '0;
  assign o_row_idx = '0;
  assign o_row_col = '0;
  assign o_row_data = '0;
  assign o_row_mask = '0;
  // ---- hết STUB ----

endmodule
/* verilator lint_on UNUSEDPARAM */
/* verilator lint_on UNUSEDSIGNAL */
