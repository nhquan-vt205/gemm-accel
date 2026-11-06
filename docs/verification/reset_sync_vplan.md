# Reset synchronizer example vplan

DUT is `gemm_reset_sync` (`rst_n_sync` output), not a module named `sync_rst_n`.
Requirement: system RST-01. Assertion is asynchronous; release takes two rising edges.
The example checks digital behavior; it does not simulate analog metastability.

| TC ID | Checklist | Pass condition |
|---|---|---|
| TC_RST_001 | Assert away from rising edge; hold reset; release | Output clears before next rising edge, remains 0 after first rising edge, becomes 1 after second, stays 1 |
| TC_RST_002 | Reassert during operation; pulse entirely between rising edges; repeat reset | Async clear still works, release again requires two rising edges |
| random_s101 / random_s102 | Python-generated hold durations and release offsets | Every pulse satisfies the same RST-01 checks in harness |

`pat.list` runs directed tests. `random.list` runs the checked-in generated examples.
Testcase calls harness tasks; harness owns checks, result line, watchdog and finish.
