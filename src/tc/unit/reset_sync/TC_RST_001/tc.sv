// Vplan TC_RST_001: async assertion and release after exactly two rising edges.
// No module/initial here: this task is included in the harness scope.
task automatic run_tc();
  assert_reset();
  hold_reset(2);
  release_reset();
endtask
