// Vplan TC_RST_002: reassert while running and a pulse without a clock edge.
task automatic run_tc();
  assert_reset();
  hold_reset(1);
  release_reset();
  // Assert AND deassert between rising edges: asynchronous assertion must work.
  @(negedge clk);
  #1;
  rst_n = 0;
  #1;
  check_reset(0, "pulse-assert");
  rst_n = 1;
  #1;
  check_reset(0, "pulse-release");
  @(posedge clk);
  #1;
  check_reset(0, "pulse-release: posedge 1");
  @(posedge clk);
  #1;
  check_reset(1, "pulse-release: posedge 2");
  assert_reset();
  hold_reset(3);
  release_reset(2);
endtask
