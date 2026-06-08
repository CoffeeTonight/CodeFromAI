// demo_data/elab_test_cases/step3_nested_param_passing.v
// C 단계 (다음단계): 중첩 generate-for + 상위 parameter 전달 + genvar 조합 표현식 + param override
// 목표: unroller가 nested scope의 모든 genvar + outer params를 합쳐서 .PARAM 값을 숫자로 정확히 계산하는지 검증

module leaf_core #(
    parameter int CLUSTER_ID = 0,
    parameter int CORE_ID = 0,
    parameter int TOTAL_CORES = 8
)();
endmodule

module step3_nested_param_passing #(
    parameter int NUM_CLUSTERS = 2,
    parameter int CORES_PER_CLUSTER = 2
)();

    generate
        for (genvar c = 0; c < NUM_CLUSTERS; c = c + 1) begin : u_cluster
            for (genvar i = 0; i < CORES_PER_CLUSTER; i = i + 1) begin : u_core
                // C 핵심: 중첩 genvar (c, i) + 외부 파라미터 조합 표현식 (localparam 없이 직접)
                leaf_core #(
                    .CLUSTER_ID(c),
                    .CORE_ID(c * CORES_PER_CLUSTER + i),
                    .TOTAL_CORES(NUM_CLUSTERS * CORES_PER_CLUSTER)
                ) u_leaf ();
            end
        end
    endgenerate

endmodule