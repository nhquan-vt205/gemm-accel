// =============================================================================
// gemm_vpu.sv — STUB (chưa hiện thực)
// Spec : docs/modules/vpu/gemm_vpu_spec.pdf
// Module con cần viết: gemm_vpu_lane (x P), gemm_vpu_requant
//
// Port list dưới đây đã khớp spec và đã được nối trong gemm_accel_top.
// Người phụ trách: giữ nguyên tên/độ rộng port; muốn đổi port thì sửa spec trong cùng PR.
// Khi bắt đầu hiện thực: xóa khối 'STUB' và hai dòng lint_off bên dưới.
// =============================================================================
/* verilator lint_off UNUSEDSIGNAL */
/* verilator lint_off UNUSEDPARAM */
module gemm_vpu #(
  parameter int P = 8,
  parameter int MUL_STAGES = 1
) (
  input  logic              clk,
  input  logic              rst_n,
  input  logic              i_soft_clr,
  // ---- Cấu hình job đang tính (FSM)
  input  logic              i_post_en,
  input  logic              i_relu_en,
  input  logic [31:0]       i_quant_m0,
  input  logic [4:0]        i_quant_shift,
  // ---- Luồng hàng vào (array)
  input  logic              i_row_valid,
  input  logic [4:0]        i_row_idx,
  input  logic [4:0]        i_row_col,
  input  logic [32*P-1:0]   i_row_data,
  input  logic [P-1:0]      i_row_mask,
  // ---- Đọc BIAS (SRAM, trễ 1)
  output logic              o_bias_rd_en,
  output logic [4:0]        o_bias_rd_col,
  input  logic [32*P-1:0]   i_bias_rd_data,
  // ---- Ghi C (SRAM)
  output logic              o_c_wr_en,
  output logic              o_c_wr_fmt,
  output logic [4:0]        o_c_wr_row,
  output logic [4:0]        o_c_wr_col,
  output logic [32*P-1:0]   o_c_wr_data,
  output logic [P-1:0]      o_c_wr_mask
);

  // ---- STUB: mọi output bằng 0. Xóa khối này khi hiện thực. ----
  assign o_bias_rd_en = '0;
  assign o_bias_rd_col = '0;
  assign o_c_wr_en = '0;
  assign o_c_wr_fmt = '0;
  assign o_c_wr_row = '0;
  assign o_c_wr_col = '0;
  assign o_c_wr_data = '0;
  assign o_c_wr_mask = '0;
  // ---- hết STUB ----

endmodule
/* verilator lint_on UNUSEDPARAM */
/* verilator lint_on UNUSEDSIGNAL */
