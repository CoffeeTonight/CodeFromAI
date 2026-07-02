// TB verdict policy — assert_fail semantics by tier
//
// CAMPAIGN (tb_full_campaign): strict — every active VCPU assert_fail==0 at phase
//   checkpoints; agent verify_fail==0 at campaign end.
//
// HARNESS (tb_verification_harness): recovery — troublemaker recovery_count>0;
//   troublemaker assert_fail==0 after recovery epoch; peer (main/worker) cross-CPU
//   assert_fail is transient injection (logged, not FAIL).
//
// RECOVERY EPOCH: cpu_reset / wdt_default_recovery clears assert_pass, assert_fail,
//   and cov_assert_* so post-recovery checks start from a clean slate.

`ifndef VERIF_VERDICT_POLICY_VH
`define VERIF_VERDICT_POLICY_VH

`define VERIF_HARNESS_MIN_RECOVERY 1

`endif