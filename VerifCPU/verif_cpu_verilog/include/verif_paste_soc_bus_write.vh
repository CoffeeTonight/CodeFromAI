// Hand-maintained — soc_cpu_bus_paste.v (1-slave copy-paste template)
        case (CPU_ID)
          7'd1: soc_cpu_bus_paste.g_slv0.u_bus.u_bridge.bus_write(addr, data, size, resp);
          default: resp = 2'd2;
        endcase