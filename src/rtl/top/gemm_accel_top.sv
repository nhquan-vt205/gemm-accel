// =============================================================================
// gemm_accel_top.sv — top level của accelerator
// Port top (44 port) KHÓA CỨNG theo spec hệ thống v1.0 mục 6 — không được sửa.
// Nối dây nội bộ theo spec gemm_main_fsm, phụ lục A (bảng A-1).
// =============================================================================
module gemm_accel_top #(
  parameter int PE_ARRAY_SIZE   = 8,   // P: 4 hoặc 8
  parameter int MAX_BURST_BEATS = 16,  // 1 … 256
  parameter int HAS_CHAIN       = 0,   // 1: chế độ chuỗi descriptor (mục 7.2)
  parameter int HAS_PINGPONG    = 0    // 1: scratchpad ping-pong (mục 7.3), cần HAS_CHAIN = 1
) (
  input  logic        clk,
  input  logic        rst_n,
  // ---- AXI4-Lite slave (MMIO) ----
  input  logic [31:0] s_axi_awaddr,
  input  logic        s_axi_awvalid,
  output logic        s_axi_awready,
  input  logic [31:0] s_axi_wdata,
  input  logic [3:0]  s_axi_wstrb,
  input  logic        s_axi_wvalid,
  output logic        s_axi_wready,
  output logic [1:0]  s_axi_bresp,
  output logic        s_axi_bvalid,
  input  logic        s_axi_bready,
  input  logic [31:0] s_axi_araddr,
  input  logic        s_axi_arvalid,
  output logic        s_axi_arready,
  output logic [31:0] s_axi_rdata,
  output logic [1:0]  s_axi_rresp,
  output logic        s_axi_rvalid,
  input  logic        s_axi_rready,
  // ---- AXI4 master (DMA) ----
  output logic [31:0] m_axi_araddr,
  output logic [7:0]  m_axi_arlen,
  output logic [2:0]  m_axi_arsize,
  output logic [1:0]  m_axi_arburst,
  output logic        m_axi_arvalid,
  input  logic        m_axi_arready,
  input  logic [31:0] m_axi_rdata,
  input  logic [1:0]  m_axi_rresp,
  input  logic        m_axi_rlast,
  input  logic        m_axi_rvalid,
  output logic        m_axi_rready,
  output logic [31:0] m_axi_awaddr,
  output logic [7:0]  m_axi_awlen,
  output logic [2:0]  m_axi_awsize,
  output logic [1:0]  m_axi_awburst,
  output logic        m_axi_awvalid,
  input  logic        m_axi_awready,
  output logic [31:0] m_axi_wdata,
  output logic [3:0]  m_axi_wstrb,
  output logic        m_axi_wlast,
  output logic        m_axi_wvalid,
  input  logic        m_axi_wready,
  input  logic [1:0]  m_axi_bresp,
  input  logic        m_axi_bvalid,
  output logic        m_axi_bready
);
  localparam int P = PE_ARRAY_SIZE;

  // ---- Kiểm tra tham số lúc elaboration ----
  if (P != 4 && P != 8) begin : g_bad_p
    $error("PE_ARRAY_SIZE phải là 4 hoặc 8");
  end
  if (MAX_BURST_BEATS < 1 || MAX_BURST_BEATS > 256) begin : g_bad_burst
    $error("MAX_BURST_BEATS phải trong 1 … 256");
  end
  if (HAS_PINGPONG != 0 && HAS_CHAIN == 0) begin : g_bad_pp
    $error("HAS_PINGPONG = 1 đòi hỏi HAS_CHAIN = 1");
  end

  // ===========================================================================
  // Reset
  // ===========================================================================
  logic rst_n_sync, soft_clr;
  gemm_reset_sync u_rst_sync (.clk, .rst_n, .rst_n_sync);

  // ===========================================================================
  // Dây nội bộ
  // ===========================================================================
  // RF <-> FSM
  logic        start_pulse, soft_req, soft_busy;
  logic [1:0]  start_kind;
  logic [31:0] cfg_dim, cfg_a_addr, cfg_b_addr, cfg_c_addr, cfg_post_ctrl;
  logic [31:0] cfg_bias_addr, cfg_qm0, cfg_qshift, cfg_desc_ptr;
  logic        done_pulse, err_pulse;
  logic [3:0]  err_code;
  logic        perf_load, perf_comp, perf_store;
  logic [31:0] err_desc_addr, desc_done_cnt;
  // FSM <-> DMA, kênh đọc
  logic        rd_start, rd_bank, rd_abort, rd_busy, rd_done, rd_error;
  logic [1:0]  rd_dst;
  logic [31:0] rd_base;
  logic [5:0]  rd_rows, rd_rwords;
  logic [15:0] rd_stride;
  logic        desc_valid;
  logic [3:0]  desc_idx;
  logic [31:0] desc_data;
  // FSM <-> DMA, kênh ghi
  logic        wr_start, wr_fmt, wr_bank, wr_abort, wr_busy, wr_done, wr_error;
  logic [31:0] wr_base;
  logic [5:0]  wr_rows, wr_rwords;
  logic [15:0] wr_stride;
  // DMA <-> SRAM
  logic        spm_wr_valid, spm_wr_bank, spm_wr_ready;
  logic [1:0]  spm_wr_buf;
  logic [9:0]  spm_wr_addr;
  logic [31:0] spm_wr_data;
  logic        spm_rd_valid, spm_rd_bank, spm_rd_ready, spm_rd_rvalid;
  logic [9:0]  spm_rd_addr;
  logic [31:0] spm_rd_rdata;
  // FSM -> Array / VPU / SRAM
  logic        pe_start, pe_done, pe_busy;
  logic [31:0] comp_dim, comp_qm0;
  logic        comp_post_en, comp_relu_en;
  logic [4:0]  comp_qshift;
  logic        comp_bank_a, comp_bank_b, comp_bank_bias, comp_bank_c, comp_active;
  // Array <-> SRAM
  logic            a_rd_en, b_rd_en;
  logic [4:0]      a_rd_row, a_rd_k, b_rd_k, b_rd_col;
  logic [8*P-1:0]  a_rd_data, b_rd_data;
  // Array -> VPU
  logic            row_valid;
  logic [4:0]      row_idx, row_col;
  logic [32*P-1:0] row_data;
  logic [P-1:0]    row_mask;
  // VPU <-> SRAM
  logic            bias_rd_en, c_wr_en, c_wr_fmt;
  logic [4:0]      bias_rd_col, c_wr_row, c_wr_col;
  logic [32*P-1:0] bias_rd_data, c_wr_data;
  logic [P-1:0]    c_wr_mask;

  // ===========================================================================
  // Register File
  // ===========================================================================
  gemm_register_file #(.P(P), .HAS_CHAIN(HAS_CHAIN), .HAS_PINGPONG(HAS_PINGPONG)) u_regfile (
    .clk, .rst_n(rst_n_sync), .i_soft_clr(soft_clr),
    .s_axi_awaddr, .s_axi_awvalid, .s_axi_awready, .s_axi_wdata, .s_axi_wstrb, .s_axi_wvalid,
    .s_axi_wready, .s_axi_bresp, .s_axi_bvalid, .s_axi_bready, .s_axi_araddr, .s_axi_arvalid,
    .s_axi_arready, .s_axi_rdata, .s_axi_rresp, .s_axi_rvalid, .s_axi_rready,
    .o_start_pulse(start_pulse), .o_start_kind(start_kind), .o_soft_req(soft_req),
    .o_cfg_dim(cfg_dim), .o_cfg_a_addr(cfg_a_addr), .o_cfg_b_addr(cfg_b_addr), .o_cfg_c_addr(cfg_c_addr),
    .o_cfg_post_ctrl(cfg_post_ctrl), .o_cfg_bias_addr(cfg_bias_addr), .o_cfg_qm0(cfg_qm0),
    .o_cfg_qshift(cfg_qshift), .o_cfg_desc_ptr(cfg_desc_ptr),
    .i_soft_busy(soft_busy), .i_done_pulse(done_pulse), .i_err_pulse(err_pulse), .i_err_code(err_code),
    .i_perf_load(perf_load), .i_perf_comp(perf_comp), .i_perf_store(perf_store),
    .i_err_desc_addr(err_desc_addr), .i_desc_done_cnt(desc_done_cnt)
  );

  // ===========================================================================
  // Main FSM
  // ===========================================================================
  gemm_main_fsm #(.P(P), .HAS_CHAIN(HAS_CHAIN), .HAS_PINGPONG(HAS_PINGPONG)) u_main_fsm (
    .clk, .rst_n(rst_n_sync), .o_soft_clr(soft_clr), .o_soft_busy(soft_busy),
    .i_start_pulse(start_pulse), .i_start_kind(start_kind), .i_soft_req(soft_req),
    .i_cfg_dim(cfg_dim), .i_cfg_a_addr(cfg_a_addr), .i_cfg_b_addr(cfg_b_addr), .i_cfg_c_addr(cfg_c_addr),
    .i_cfg_post_ctrl(cfg_post_ctrl), .i_cfg_bias_addr(cfg_bias_addr), .i_cfg_qm0(cfg_qm0),
    .i_cfg_qshift(cfg_qshift), .i_cfg_desc_ptr(cfg_desc_ptr),
    .o_done_pulse(done_pulse), .o_err_pulse(err_pulse), .o_err_code(err_code),
    .o_perf_load(perf_load), .o_perf_comp(perf_comp), .o_perf_store(perf_store),
    .o_err_desc_addr(err_desc_addr), .o_desc_done_cnt(desc_done_cnt),
    .o_rd_start(rd_start), .o_rd_dst(rd_dst), .o_rd_base(rd_base), .o_rd_rows(rd_rows),
    .o_rd_rwords(rd_rwords), .o_rd_stride(rd_stride), .o_rd_bank(rd_bank), .o_rd_abort(rd_abort),
    .i_rd_busy(rd_busy), .i_rd_done(rd_done), .i_rd_error(rd_error),
    .i_desc_valid(desc_valid), .i_desc_idx(desc_idx), .i_desc_data(desc_data),
    .o_wr_start(wr_start), .o_wr_fmt(wr_fmt), .o_wr_base(wr_base), .o_wr_rows(wr_rows),
    .o_wr_rwords(wr_rwords), .o_wr_stride(wr_stride), .o_wr_bank(wr_bank), .o_wr_abort(wr_abort),
    .i_wr_busy(wr_busy), .i_wr_done(wr_done), .i_wr_error(wr_error),
    .o_pe_start(pe_start), .i_pe_done(pe_done), .i_pe_busy(pe_busy),
    .o_comp_dim(comp_dim), .o_comp_post_en(comp_post_en), .o_comp_relu_en(comp_relu_en),
    .o_comp_qm0(comp_qm0), .o_comp_qshift(comp_qshift),
    .o_comp_bank_a(comp_bank_a), .o_comp_bank_b(comp_bank_b), .o_comp_bank_bias(comp_bank_bias),
    .o_comp_bank_c(comp_bank_c), .o_comp_active(comp_active)
  );

  // ===========================================================================
  // DMA
  // ===========================================================================
  gemm_dma_engine #(.MAX_BURST_BEATS(MAX_BURST_BEATS)) u_dma (
    .clk, .rst_n(rst_n_sync), .i_soft_clr(soft_clr),
    .i_rd_start(rd_start), .i_rd_dst(rd_dst), .i_rd_base(rd_base), .i_rd_rows(rd_rows),
    .i_rd_rwords(rd_rwords), .i_rd_stride(rd_stride), .i_rd_bank(rd_bank), .i_rd_abort(rd_abort),
    .o_rd_busy(rd_busy), .o_rd_done(rd_done), .o_rd_error(rd_error),
    .o_desc_valid(desc_valid), .o_desc_idx(desc_idx), .o_desc_data(desc_data),
    .i_wr_start(wr_start), .i_wr_fmt(wr_fmt), .i_wr_base(wr_base), .i_wr_rows(wr_rows),
    .i_wr_rwords(wr_rwords), .i_wr_stride(wr_stride), .i_wr_bank(wr_bank), .i_wr_abort(wr_abort),
    .o_wr_busy(wr_busy), .o_wr_done(wr_done), .o_wr_error(wr_error),
    .o_spm_wr_valid(spm_wr_valid), .o_spm_wr_buf(spm_wr_buf), .o_spm_wr_bank(spm_wr_bank),
    .o_spm_wr_addr(spm_wr_addr), .o_spm_wr_data(spm_wr_data), .i_spm_wr_ready(spm_wr_ready),
    .o_spm_rd_valid(spm_rd_valid), .o_spm_rd_bank(spm_rd_bank), .o_spm_rd_addr(spm_rd_addr),
    .i_spm_rd_ready(spm_rd_ready), .i_spm_rd_rvalid(spm_rd_rvalid), .i_spm_rd_rdata(spm_rd_rdata),
    .m_axi_araddr, .m_axi_arlen, .m_axi_arsize, .m_axi_arburst, .m_axi_arvalid, .m_axi_arready,
    .m_axi_rdata, .m_axi_rresp, .m_axi_rlast, .m_axi_rvalid, .m_axi_rready,
    .m_axi_awaddr, .m_axi_awlen, .m_axi_awsize, .m_axi_awburst, .m_axi_awvalid, .m_axi_awready,
    .m_axi_wdata, .m_axi_wstrb, .m_axi_wlast, .m_axi_wvalid, .m_axi_wready,
    .m_axi_bresp, .m_axi_bvalid, .m_axi_bready
  );

  // ===========================================================================
  // Scratchpad
  // ===========================================================================
  gemm_local_sram #(.P(P), .HAS_PINGPONG(HAS_PINGPONG)) u_sram (
    .clk, .rst_n(rst_n_sync), .i_soft_clr(soft_clr),
    .i_dw_valid(spm_wr_valid), .i_dw_buf(spm_wr_buf), .i_dw_bank(spm_wr_bank),
    .i_dw_addr(spm_wr_addr), .i_dw_data(spm_wr_data), .o_dw_ready(spm_wr_ready),
    .i_dr_valid(spm_rd_valid), .i_dr_bank(spm_rd_bank), .i_dr_addr(spm_rd_addr),
    .o_dr_ready(spm_rd_ready), .o_dr_rvalid(spm_rd_rvalid), .o_dr_rdata(spm_rd_rdata),
    .i_comp_bank_a(comp_bank_a), .i_comp_bank_b(comp_bank_b), .i_comp_bank_bias(comp_bank_bias),
    .i_comp_bank_c(comp_bank_c), .i_comp_active(comp_active),
    .i_a_rd_en(a_rd_en), .i_a_rd_row(a_rd_row), .i_a_rd_k(a_rd_k), .o_a_rd_data(a_rd_data),
    .i_b_rd_en(b_rd_en), .i_b_rd_k(b_rd_k), .i_b_rd_col(b_rd_col), .o_b_rd_data(b_rd_data),
    .i_bias_rd_en(bias_rd_en), .i_bias_rd_col(bias_rd_col), .o_bias_rd_data(bias_rd_data),
    .i_c_wr_en(c_wr_en), .i_c_wr_fmt(c_wr_fmt), .i_c_wr_row(c_wr_row), .i_c_wr_col(c_wr_col),
    .i_c_wr_data(c_wr_data), .i_c_wr_mask(c_wr_mask)
  );

  // ===========================================================================
  // Systolic array — L_VPU lấy từ gemm_pkg, không viết số trực tiếp (VPU-P02)
  // ===========================================================================
  gemm_systolic_array #(.P(P), .L_VPU(gemm_pkg::VPU_LATENCY)) u_array (
    .clk, .rst_n(rst_n_sync), .i_soft_clr(soft_clr),
    .i_pe_start(pe_start), .o_pe_done(pe_done), .o_busy(pe_busy), .i_matrix_dim(comp_dim),
    .o_a_rd_en(a_rd_en), .o_a_rd_row(a_rd_row), .o_a_rd_k(a_rd_k), .i_a_rd_data(a_rd_data),
    .o_b_rd_en(b_rd_en), .o_b_rd_k(b_rd_k), .o_b_rd_col(b_rd_col), .i_b_rd_data(b_rd_data),
    .o_row_valid(row_valid), .o_row_idx(row_idx), .o_row_col(row_col),
    .o_row_data(row_data), .o_row_mask(row_mask)
  );

  // ===========================================================================
  // VPU
  // ===========================================================================
  gemm_vpu #(.P(P), .MUL_STAGES(gemm_pkg::VPU_MUL_STAGES)) u_vpu (
    .clk, .rst_n(rst_n_sync), .i_soft_clr(soft_clr),
    .i_post_en(comp_post_en), .i_relu_en(comp_relu_en), .i_quant_m0(comp_qm0), .i_quant_shift(comp_qshift),
    .i_row_valid(row_valid), .i_row_idx(row_idx), .i_row_col(row_col),
    .i_row_data(row_data), .i_row_mask(row_mask),
    .o_bias_rd_en(bias_rd_en), .o_bias_rd_col(bias_rd_col), .i_bias_rd_data(bias_rd_data),
    .o_c_wr_en(c_wr_en), .o_c_wr_fmt(c_wr_fmt), .o_c_wr_row(c_wr_row), .o_c_wr_col(c_wr_col),
    .o_c_wr_data(c_wr_data), .o_c_wr_mask(c_wr_mask)
  );

endmodule
