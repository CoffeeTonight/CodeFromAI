module level7 #(
    parameter int PIN = 64,
    parameter int FINAL_OVERRIDE = 0   // will be overridden by defparam from top
)();
    level6 #(
        .PIN( ((((PIN * 3) + 11) / (PIN % 4 + 1)) - 2) * (PIN % 2 + 3) )
    ) u_l6 ();
endmodule
