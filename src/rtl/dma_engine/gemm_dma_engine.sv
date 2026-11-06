// =============================================================================
// gemm_dma_engine.sv — STUB (chưa hiện thực)
// Spec : docs/modules/dma_engine/gemm_dma_engine_spec.pdf
// Module con cần viết: gemm_dma_agen (x2), gemm_dma_rd, gemm_dma_wr, gemm_dma_wfifo
//
// Port list dưới đây đã khớp spec và đã được nối trong gemm_accel_top.
// Người phụ trách: giữ nguyên tên/độ rộng port; muốn đổi port thì sửa spec trong cùng PR.
// Khi bắt đầu hiện thực: xóa khối 'STUB' và hai dòng lint_off bên dưới.
// =============================================================================
/* verilator lint_off UNUSEDSIGNAL */
/* verilator lint_off UNUSEDPARAM */
module gemm_dma_engine #(
  parameter int MAX_BURST_BEATS = 16
) (
  input  logic              clk,
  input  logic              rst_n,
  input  logic              i_soft_clr,
  // ---- Lệnh kênh đọc
  input  logic              i_rd_start,
  input  logic [1:0]        i_rd_dst,
  input  logic [31:0]       i_rd_base,
  input  logic [5:0]        i_rd_rows,
  input  logic [5:0]        i_rd_rwords,
  input  logic [15:0]       i_rd_stride,
  input  logic              i_rd_bank,
  input  logic              i_rd_abort,
  output logic              o_rd_busy,
  output logic              o_rd_done,
  output logic              o_rd_error,
  output logic              o_desc_valid,
  output logic [3:0]        o_desc_idx,
  output logic [31:0]       o_desc_data,
  // ---- Lệnh kênh ghi
  input  logic              i_wr_start,
  input  logic              i_wr_fmt,
  input  logic [31:0]       i_wr_base,
  input  logic [5:0]        i_wr_rows,
  input  logic [5:0]        i_wr_rwords,
  input  logic [15:0]       i_wr_stride,
  input  logic              i_wr_bank,
  input  logic              i_wr_abort,
  output logic              o_wr_busy,
  output logic              o_wr_done,
  output logic              o_wr_error,
  // ---- Cổng ghi scratchpad (A, B, BIAS)
  output logic              o_spm_wr_valid,
  output logic [1:0]        o_spm_wr_buf,
  output logic              o_spm_wr_bank,
  output logic [9:0]        o_spm_wr_addr,
  output logic [31:0]       o_spm_wr_data,
  input  logic              i_spm_wr_ready,
  // ---- Cổng đọc scratchpad (C)
  output logic              o_spm_rd_valid,
  output logic              o_spm_rd_bank,
  output logic [9:0]        o_spm_rd_addr,
  input  logic              i_spm_rd_ready,
  input  logic              i_spm_rd_rvalid,
  input  logic [31:0]       i_spm_rd_rdata,
  // ---- AXI4 master (25 port, bảng 6-3 spec hệ thống)
  output logic [31:0]       m_axi_araddr,
  output logic [7:0]        m_axi_arlen,
  output logic [2:0]        m_axi_arsize,
  output logic [1:0]        m_axi_arburst,
  output logic              m_axi_arvalid,
  input  logic              m_axi_arready,
  input  logic [31:0]       m_axi_rdata,
  input  logic [1:0]        m_axi_rresp,
  input  logic              m_axi_rlast,
  input  logic              m_axi_rvalid,
  output logic              m_axi_rready,
  output logic [31:0]       m_axi_awaddr,
  output logic [7:0]        m_axi_awlen,
  output logic [2:0]        m_axi_awsize,
  output logic [1:0]        m_axi_awburst,
  output logic              m_axi_awvalid,
  input  logic              m_axi_awready,
  output logic [31:0]       m_axi_wdata,
  output logic [3:0]        m_axi_wstrb,
  output logic              m_axi_wlast,
  output logic              m_axi_wvalid,
  input  logic              m_axi_wready,
  input  logic [1:0]        m_axi_bresp,
  input  logic              m_axi_bvalid,
  output logic              m_axi_bready
);

  // ---- STUB: mọi output bằng 0. Xóa khối này khi hiện thực. ----
  assign o_rd_busy = '0;
  assign o_rd_done = '0;
  assign o_rd_error = '0;
  assign o_desc_valid = '0;
  assign o_desc_idx = '0;
  assign o_desc_data = '0;
  assign o_wr_busy = '0;
  assign o_wr_done = '0;
  assign o_wr_error = '0;
  assign o_spm_wr_valid = '0;
  assign o_spm_wr_buf = '0;
  assign o_spm_wr_bank = '0;
  assign o_spm_wr_addr = '0;
  assign o_spm_wr_data = '0;
  assign o_spm_rd_valid = '0;
  assign o_spm_rd_bank = '0;
  assign o_spm_rd_addr = '0;
  assign m_axi_araddr = '0;
  assign m_axi_arlen = '0;
  assign m_axi_arsize = '0;
  assign m_axi_arburst = '0;
  assign m_axi_arvalid = '0;
  assign m_axi_rready = '0;
  assign m_axi_awaddr = '0;
  assign m_axi_awlen = '0;
  assign m_axi_awsize = '0;
  assign m_axi_awburst = '0;
  assign m_axi_awvalid = '0;
  assign m_axi_wdata = '0;
  assign m_axi_wstrb = '0;
  assign m_axi_wlast = '0;
  assign m_axi_wvalid = '0;
  assign m_axi_bready = '0;
  // ---- hết STUB ----

endmodule
/* verilator lint_on UNUSEDPARAM */
/* verilator lint_on UNUSEDSIGNAL */
