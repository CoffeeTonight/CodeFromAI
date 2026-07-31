// Dual-group IRQ change detect + zero-cycle handler for verif_cpu_core (model only).
// Requires parameters NUM_IRQ0 / NUM_IRQ1 and ports irq0 / irq1.

reg [NUM_IRQ0-1:0] irq0_prev;
reg [NUM_IRQ1-1:0] irq1_prev;
reg                irq_ready;

// ISR hook — enter/exit with no #delay and no total_steps cost.
// group: 0 = irq0 port, 1 = irq1 port
task irq_handler;
  input integer group;
  input integer bit_idx;
  input         old_val;
  input         new_val;
  begin
    $display("SCPU%0d > [IRQ handler] grp=%0d bit=%0d old=%0b new=%0b (zero-cycle return)",
             CPU_ID, group, bit_idx, old_val, new_val);
  end
endtask

task irq_service_bit;
  input integer group;
  input integer bit_idx;
  input         old_val;
  input         new_val;
  begin
    $display("SCPU%0d > [IRQ] grp=%0d bit %0d: %0b -> %0b (now=%0b)",
             CPU_ID, group, bit_idx, old_val, new_val, new_val);
    irq_handler(group, bit_idx, old_val, new_val);
  end
endtask

task irq0_process_change;
  integer bi;
  begin
    for (bi = 0; bi < NUM_IRQ0; bi = bi + 1) begin
      if (irq0[bi] !== irq0_prev[bi])
        irq_service_bit(0, bi, irq0_prev[bi], irq0[bi]);
    end
    irq0_prev = irq0;
  end
endtask

task irq1_process_change;
  integer bi;
  begin
    for (bi = 0; bi < NUM_IRQ1; bi = bi + 1) begin
      if (irq1[bi] !== irq1_prev[bi])
        irq_service_bit(1, bi, irq1_prev[bi], irq1[bi]);
    end
    irq1_prev = irq1;
  end
endtask

initial begin : irq_init
  irq_ready  = 1'b0;
  irq0_prev  = {NUM_IRQ0{1'b0}};
  irq1_prev  = {NUM_IRQ1{1'b0}};
  // Defer first sample so X→0 at time 0 is not treated as a real IRQ edge.
  #0;
  irq0_prev = irq0;
  irq1_prev = irq1;
  irq_ready = 1'b1;
end

always @(irq0) begin : irq0_watch
  if (irq_ready)
    irq0_process_change();
  else
    irq0_prev = irq0;
end

always @(irq1) begin : irq1_watch
  if (irq_ready)
    irq1_process_change();
  else
    irq1_prev = irq1;
end
