// =============================================================================
// gemm_register_file.sv — STUB (chưa hiện thực)
// Spec : docs/modules/register_file/gemm_register_file_spec.pdf
// Module con cần viết: gemm_axil_slave, gemm_rf_regs, gemm_rf_perf
//
// Port list dưới đây đã khớp spec và đã được nối trong gemm_accel_top.
// Người phụ trách: giữ nguyên tên/độ rộng port; muốn đổi port thì sửa spec trong cùng PR.
// Khi bắt đầu hiện thực: xóa khối 'STUB' và hai dòng lint_off bên dưới.
// =============================================================================
/* verilator lint_off UNUSEDSIGNAL */
/* verilator lint_off UNUSEDPARAM */
module gemm_register_file #(
  parameter int P = 8,
  parameter int HAS_CHAIN = 1,
  parameter int HAS_PINGPONG = 1
) (
  input  logic              clk,
  input  logic              rst_n,
  input  logic              i_soft_clr,
  // ---- AXI4-Lite slave (17 port, bảng 6-2 spec hệ thống)
  input  logic [31:0]       s_axi_awaddr,
  input  logic              s_axi_awvalid,
  output logic              s_axi_awready,
  input  logic [31:0]       s_axi_wdata,
  input  logic [3:0]        s_axi_wstrb,
  input  logic              s_axi_wvalid,
  output logic              s_axi_wready,
  output logic [1:0]        s_axi_bresp,
  output logic              s_axi_bvalid,
  input  logic              s_axi_bready,
  input  logic [31:0]       s_axi_araddr,
  input  logic              s_axi_arvalid,
  output logic              s_axi_arready,
  output logic [31:0]       s_axi_rdata,
  output logic [1:0]        s_axi_rresp,
  output logic              s_axi_rvalid,
  input  logic              s_axi_rready,
  // ---- Register File -> FSM
  output logic              o_start_pulse,
  output logic [1:0]        o_start_kind,
  output logic              o_soft_req,
  output logic [31:0]       o_cfg_dim,
  output logic [31:0]       o_cfg_a_addr,
  output logic [31:0]       o_cfg_b_addr,
  output logic [31:0]       o_cfg_c_addr,
  output logic [31:0]       o_cfg_post_ctrl,
  output logic [31:0]       o_cfg_bias_addr,
  output logic [31:0]       o_cfg_qm0,
  output logic [31:0]       o_cfg_qshift,
  output logic [31:0]       o_cfg_desc_ptr,
  // ---- FSM -> Register File
  input  logic              i_soft_busy,
  input  logic              i_done_pulse,
  input  logic              i_err_pulse,
  input  logic [3:0]        i_err_code,
  input  logic              i_perf_load,
  input  logic              i_perf_comp,
  input  logic              i_perf_store,
  input  logic [31:0]       i_err_desc_addr,
  input  logic [31:0]       i_desc_done_cnt
);

  // ---- STUB: mọi output bằng 0. Xóa khối này khi hiện thực. ----
  assign s_axi_awready = '0;
  assign s_axi_wready = '0;
  assign s_axi_bresp = '0;
  assign s_axi_bvalid = '0;
  assign s_axi_arready = '0;
  assign s_axi_rdata = '0;
  assign s_axi_rresp = '0;
  assign s_axi_rvalid = '0;
  assign o_start_pulse = '0;
  assign o_start_kind = '0;
  assign o_soft_req = '0;
  assign o_cfg_dim = '0;
  assign o_cfg_a_addr = '0;
  assign o_cfg_b_addr = '0;
  assign o_cfg_c_addr = '0;
  assign o_cfg_post_ctrl = '0;
  assign o_cfg_bias_addr = '0;
  assign o_cfg_qm0 = '0;
  assign o_cfg_qshift = '0;
  assign o_cfg_desc_ptr = '0;
  // ---- hết STUB ----

endmodule
/* verilator lint_on UNUSEDPARAM */
/* verilator lint_on UNUSEDSIGNAL */
