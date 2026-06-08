// Parse-eval: generate / ifdef / param chain / include-only
// NOTE: include/hidden/include_only_mod.v is NOT listed (pulled via `include)
+incdir+../include/param
+incdir+../include/hidden
+define+PARSE_STRESS
+define+ORION_ENABLE_GEN_IF=1
../rtl/stress/stress_generate.v
../rtl/stress/stress_ifdef_nest.v
../rtl/stress/stress_inst_styles.v
../rtl/stress/include_gateway.v
../rtl/stress/parse_eval_wrap.v
../rtl/stress/param_stack_l5.v
../rtl/stress/param_stack_l4.v
../rtl/stress/param_stack_l3.v
../rtl/stress/param_stack_l2.v
../rtl/stress/param_stack_l1.v
// param_leaf.v pulled only through `include chain in param_stack_l1
