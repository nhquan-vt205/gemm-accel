// Harness template: DUT + reusable task API + checks + one included run_tc().
module tb_gemm_reset_sync;
  timeunit 1ns;
  timeprecision 1ps;
  parameter int CLK_HALF_NS = 5;
  logic clk = 0;
  logic rst_n = 1;
  logic rst_n_sync;
  string tc_dir;
  string tc_id;
  int seed;
  int checks = 0;
  int errors = 0;

  gemm_reset_sync dut (.clk(clk), .rst_n(rst_n), .rst_n_sync(rst_n_sync));
  always #(CLK_HALF_NS) clk = ~clk;

  task automatic check_reset(input bit expected, input string action);
    checks++;
    if (rst_n_sync !== expected) errors++;
    $display("[t = %8s] [%-24s] rst_n=%0b | rst_n_sync exp=%0b act=%0b | %s",
             $sformatf("%0t", $time), action, rst_n, expected, rst_n_sync,
             (rst_n_sync === expected) ? "PASS" : "FAIL");
  endtask

  // Drive away from posedge; #1 allows DUT nonblocking updates to settle.
  task automatic assert_reset();
    @(negedge clk);
    #1;
    rst_n = 0;
    #1;
    check_reset(0, "assert");
  endtask

  task automatic hold_reset(input int cycles);
    repeat (cycles) begin
      @(posedge clk);
      #1;
      check_reset(0, "hold");
    end
  endtask

  task automatic release_reset(input int delay_ns = 1);
    @(negedge clk);
    #(delay_ns);
    rst_n = 1;
    #1;
    check_reset(0, "release");
    @(posedge clk);
    #1;
    check_reset(0, "release: posedge 1");
    @(posedge clk);
    #1;
    check_reset(1, "release: posedge 2");
    @(posedge clk);
    #1;
    check_reset(1, "release: posedge 3");
  endtask

  `include "tc.sv"

  initial begin
    int id_start;
    $timeformat(-9, 0, " ns", 0);
    if (CLK_HALF_NS < 5) $fatal(1, "TEST FAILED: CLK_HALF_NS must be >= 5");
    if (!$value$plusargs("TC_DIR=%s", tc_dir)) $fatal(1, "TEST FAILED: missing TC_DIR");
    if (!$value$plusargs("SEED=%d", seed)) seed = 1;
    id_start = 0;
    for (int i = 0; i < tc_dir.len(); i++)
      if (tc_dir[i] == "/") id_start = i+1;
    tc_id = tc_dir.substr(id_start, tc_dir.len()-1);
    $display("[TC] %s", tc_id);
    run_tc();
    if (errors != 0 || checks == 0) begin
      $display("TEST FAILED: checks=%0d errors=%0d", checks, errors);
      $fatal(1, "checker failure");
    end
    $display("TEST PASSED (%s)", tc_id);
    $finish;
  end

  initial begin
    #100000;
    $display("TEST FAILED: TIMEOUT reset_sync watchdog");
    $fatal(1, "watchdog");
  end

  `ifdef WAVES
  initial begin
    $dumpfile("waves.fst");
    $dumpvars(0, tb_gemm_reset_sync);
  end
  `endif
endmodule
