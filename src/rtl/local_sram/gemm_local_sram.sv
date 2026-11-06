// =============================================================================
// gemm_local_sram.sv — STUB (chưa hiện thực)
// Spec : docs/modules/local_sram/gemm_local_sram_spec.pdf
// Module con cần viết: gemm_spm_ram, gemm_spm_a, gemm_spm_b, gemm_spm_bias, gemm_spm_c
//
// Port list dưới đây đã khớp spec và đã được nối trong gemm_accel_top.
// Người phụ trách: giữ nguyên tên/độ rộng port; muốn đổi port thì sửa spec trong cùng PR.
// Khi bắt đầu hiện thực: xóa khối 'STUB' và hai dòng lint_off bên dưới.
// =============================================================================
/* verilator lint_off UNUSEDSIGNAL */
/* verilator lint_off UNUSEDPARAM */
module gemm_local_sram #(
  parameter int P = 8,
  parameter int HAS_PINGPONG = 1
) (
  input  logic              clk,
  input  logic              rst_n,
  input  logic              i_soft_clr,
  // ---- Cổng ghi phía DMA
  input  logic              i_dw_valid,
  input  logic [1:0]        i_dw_buf,
  input  logic              i_dw_bank,
  input  logic [9:0]        i_dw_addr,
  input  logic [31:0]       i_dw_data,
  output logic              o_dw_ready,
  // ---- Cổng đọc phía DMA
  input  logic              i_dr_valid,
  input  logic              i_dr_bank,
  input  logic [9:0]        i_dr_addr,
  output logic              o_dr_ready,
  output logic              o_dr_rvalid,
  output logic [31:0]       o_dr_rdata,
  // ---- Bank phía tính (từ FSM)
  input  logic              i_comp_bank_a,
  input  logic              i_comp_bank_b,
  input  logic              i_comp_bank_bias,
  input  logic              i_comp_bank_c,
  input  logic              i_comp_active,
  // ---- Cổng đọc A, B (từ array)
  input  logic              i_a_rd_en,
  input  logic [4:0]        i_a_rd_row,
  input  logic [4:0]        i_a_rd_k,
  output logic [8*P-1:0]    o_a_rd_data,
  input  logic              i_b_rd_en,
  input  logic [4:0]        i_b_rd_k,
  input  logic [4:0]        i_b_rd_col,
  output logic [8*P-1:0]    o_b_rd_data,
  // ---- Cổng BIAS và C (từ VPU)
  input  logic              i_bias_rd_en,
  input  logic [4:0]        i_bias_rd_col,
  output logic [32*P-1:0]   o_bias_rd_data,
  input  logic              i_c_wr_en,
  input  logic              i_c_wr_fmt,
  input  logic [4:0]        i_c_wr_row,
  input  logic [4:0]        i_c_wr_col,
  input  logic [32*P-1:0]   i_c_wr_data,
  input  logic [P-1:0]      i_c_wr_mask
);

  // ---- STUB: mọi output bằng 0. Xóa khối này khi hiện thực. ----
  assign o_dw_ready = '0;
  assign o_dr_ready = '0;
  assign o_dr_rvalid = '0;
  assign o_dr_rdata = '0;
  assign o_a_rd_data = '0;
  assign o_b_rd_data = '0;
  assign o_bias_rd_data = '0;
  // ---- hết STUB ----

endmodule
/* verilator lint_on UNUSEDPARAM */
/* verilator lint_on UNUSEDSIGNAL */
