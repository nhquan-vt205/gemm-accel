// Data-driven variant: each row is "hold_cycles release_delay_ns" (decimal).
task automatic run_tc();
  int fd, rc, hold_cycles, release_delay_ns, rows;
  string path, line, extra;
  path = {tc_dir, "/stim.txt"};
  fd = $fopen(path, "r");
  if (fd == 0) $fatal(1, "TEST FAILED: cannot open %s", path);
  rows = 0;
  while ($fgets(line, fd) != 0) begin
    // Read one line at a time: EOF handling is portable across both simulators.
    rc = $sscanf(line, "%d %d %s", hold_cycles, release_delay_ns, extra);
    if (rc != 2 || hold_cycles < 1 || hold_cycles > 10 ||
        release_delay_ns < 1 || release_delay_ns > 3)
      $fatal(1, "TEST FAILED: malformed stimulus row %0d", rows+1);
    rows++;
    assert_reset();
    hold_reset(hold_cycles);
    release_reset(release_delay_ns);
  end
  $fclose(fd);
  // The harness rejects zero checks, including an empty input file.
endtask
