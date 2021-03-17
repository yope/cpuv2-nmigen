
## cpuv2-nmigen

This is a rewrite of the [cpuv2](https://github.com/yope/cpuv2) in [nmigen](https://github.com/m-labs/nmigen).
This is a work in progress and right now there is only the CPU core. The rest will be added bit by bit later.
It can be simulated:

```bash
./cpu.py --sim
```

This will create gtkwave data- and config files that can be used to inspect up to a few 100 bus cycles
of execution.
