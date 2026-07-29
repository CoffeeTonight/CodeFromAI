// IRQ change detect + empty zero-cycle handler for verif_cpu_core (model only).
// Included inside the module body. Requires parameter NUM_IRQ and port irq[NUM_IRQ-1:0].

reg [NUM_IRQ-1:0] irq_prev;
reg               irq_ready;

// ISR hook — enter/exit with no #delay and no total_steps cost.
// Placeholder body: $display only (extend later with real model actions).
task irq_handler;
  input integer bit_idx;
  input         old_val;
  input         new_val;
  begin
    $display("SCPU%0d > [IRQ handler] entered bit=%0d old=%0b new=%0b (zero-cycle return)",
             CPU_ID, bit_idx, old_val, new_val);
  end
endtask

// CPU action for one changed bit: log level + call empty handler (zero model time).
task irq_service_bit;
  input integer bit_idx;
  input         old_val;
  input         new_val;
  begin
    $display("SCPU%0d > [IRQ] bit %0d: %0b -> %0b (now=%0b)",
             CPU_ID, bit_idx, old_val, new_val, new_val);
    // "jump" to empty handler without consuming a cpu_step / clock
    irq_handler(bit_idx, old_val, new_val);
  end
endtask

task irq_process_change;
  integer bi;
  begin
    for (bi = 0; bi < NUM_IRQ; bi = bi + 1) begin
      if (irq[bi] !== irq_prev[bi])
        irq_service_bit(bi, irq_prev[bi], irq[bi]);
    end
    irq_prev = irq;
  end
endtask

initial begin : irq_init
  irq_ready = 1'b0;
  irq_prev  = {NUM_IRQ{1'b0}};
  // Defer first sample so X→0 at time 0 is not treated as a real IRQ edge.
  #0;
  irq_prev  = irq;
  irq_ready = 1'b1;
end

// Any change on the irq vector (level edge per bit) while simulation runs.
always @(irq) begin : irq_watch
  if (irq_ready)
    irq_process_change();
  else
    irq_prev = irq;
end
