// =============================================================================
// gemm_reset_sync.sv — bộ đồng bộ reset 2 flip-flop (RST-01 spec hệ thống)
// Bật bất đồng bộ, nhả đồng bộ với clk.
// =============================================================================
module gemm_reset_sync (
  input  logic clk,
  input  logic rst_n,        // reset ngoài, bất đồng bộ, tích cực thấp
  output logic rst_n_sync    // cấp cho mọi module bên trong
);
  logic ff1;
  always_ff @(posedge clk or negedge rst_n)
    if (!rst_n) {rst_n_sync, ff1} <= 2'b00;
    else        {rst_n_sync, ff1} <= {ff1, 1'b1};
endmodule
