# Guitar effects pedal: overdrive, tremolo and delay on your own PCB

A digital guitar pedal. Guitar in, an STM32 microcontroller runs three effects
(overdrive, then tremolo, then delay), and the sound comes out to your amp.
It has six knobs, three footswitches and three LEDs.

```
guitar -> input buffer -> ADC (PCM1808) -> STM32F411 (DSP) -> DAC (PCM5102A) -> output stage -> amp
              op-amp          24-bit          C firmware          32-bit            op-amp
```

| Effect | Knobs | Footswitch / LED |
|---|---|---|
| Overdrive | DRIVE (gain 1x to 151x), TONE (800 Hz to 8 kHz) | OD, red LED |
| Tremolo | RATE (0.5 to 12 Hz), DEPTH (0 to 100 %) | TREM, yellow LED blinks at the rate |
| Delay | TIME (40 to 800 ms), REPEATS (0 to 90 % feedback) | DELAY, green LED |

**What you do next is in the [build guide](https://claude.ai/code/artifact/68aed441-7a6f-4b3e-b3b9-c396d0ad24f2).**
It covers only the jobs that need your hands: ordering, soldering, flashing,
measuring and drilling.

## Parts I picked, and why

| Choice | Why |
|---|---|
| **WeAct Black Pill, STM32F411CEU6** (plugs into sockets) | Cheap, very well documented, has a hardware floating-point unit and full-duplex I2S. On sockets, so you can unplug it to flash it and the factory never touches it. |
| **PCM1808 ADC + PCM5102A DAC** | The standard hobby I2S audio pair. Few support parts, cheap, and the DAC makes its own negative supply, so its output is centred on 0 V. |
| **OPA1678 op-amp, single 9 V supply** | Low noise, rail-to-rail output. Works from the pedal's 9 V with a 4.3 V "virtual ground" (VBIAS). |
| **9 V DC, centre-negative** | The normal guitar-pedal power supply. |
| **KiCad 7** | Free, and the factory accepts its files. |
| **Bare-metal C (CMSIS registers, no HAL)** | Small, and every line is readable. Builds with `arm-none-eabi-gcc` and `make`. |
| **JLCPCB assembly, bottom side only** | All 79 small surface-mount parts are soldered by the factory. You solder only big through-hole parts. |
| **Hammond 1590XX box (145 x 121 x 39 mm)** | Room for 6 knobs and 3 footswitches. |

## What is done, and how it was checked

| Part | Status | How it was checked |
|---|---|---|
| DSP effects (C) | Done | 9 automated tests on the PC, all pass: bypass is exact, overdrive THD goes from 0.6 % to 38 %, tremolo rate and depth, delay echo lands at 420.00 ms, maximum repeats die out, no clicks when switching. Run `make test` in `firmware/`. |
| Firmware for the STM32 | Done, builds | Compiles with no warnings: 8.8 KB flash, 81 KB RAM (most of it is the 0.83 s delay memory). **Not yet run on a real chip.** |
| Analog circuits | Done | ngspice simulation: input stage gain x1.45 with -3 dB points at 2.2 Hz and 59.6 kHz; output stage x0.308 with -3 dB at 1 Hz and 150 kHz. A hard strum (1 V peak) uses about 2.9 V of the ADC's 3 V range. See `sim/analog_sim.png` (also in `docs/img/`). |
| Schematic | Done | 9 sheets, 66 nets. A script checks every pin against the design list: 271 pins, 0 errors. |
| PCB | Done | 85 x 76 mm, 2 layers, ground pour on both sides. KiCad design-rule check: **0 errors, 0 unconnected**. 3 warnings remain: three through-hole ground pads have 1 thermal spoke instead of 2 (still connected; harmless). |
| Factory files | Done | Gerbers + drill, BOM and pick-and-place for JLCPCB, a list of the parts you buy yourself. |
| Enclosure | Done | 1:1 printable drilling template, hole positions taken from the PCB. |

### Things I could not check from here

1. **Nothing has been built or powered yet.** The firmware has not run on hardware, and the board has not been made.
2. **LCSC part numbers are blank in the BOM.** I can't reach the JLCPCB parts catalogue from here, so you pick each part in their BOM tool. The guide shows how.
3. **Black Pill pin order.** I took it from the stm32-base.org pin tables. Check it against your module before you order (the guide's first step).
4. **Box size.** The template is drawn for a 1590XX. Measure your own box.

## Files

```
guitar-pedal/
  README.md                     this file
  docs/design-notes.md          how every stage works, with the numbers
  docs/img/                     simulation plot, effect plots, PCB pictures
  firmware/
    build/pedal.bin, pedal.hex  ready to flash
    src/                        main.c, audio_io.c (I2S + DMA), controls.c (knobs, switches, LEDs), clock.c, uart.c, startup.c, board.h (pin map)
    dsp/effects.c               the three effects (plain C, also runs on a PC)
    host/                       PC test bench: `make test` runs the tests and writes demo WAVs to host/out/
    Makefile                    make / make flash-dfu / make flash-stlink / make test
  hardware/
    pedal.kicad_pro             open this in KiCad 7
    fab/pedal-gerbers.zip       upload to JLCPCB
    fab/bom_jlc.csv, cpl_jlc.csv   factory assembly files
    fab/hand_parts.csv          what you buy and solder yourself
    fab/schematic.pdf           the schematic, 9 pages
    fab/enclosure-drill-template.pdf   print at 100 %
    fab/pcb_top.png, pcb_bottom.png
    gen/                        Python scripts that generate the whole KiCad project
  sim/analog.cir, run_sim.py    ngspice simulation of the analog stages
```

### Rebuilding from the scripts (optional)

Everything in `hardware/` is generated by the scripts in `hardware/gen/`, run in
this order: `gen_libs.py`, `gen_sch.py`, `check_netlist.py`, `gen_pcb.py`,
`gen_pro.py`, `route.py`, `drc.py`, `export.py`, `enclosure.py`. They need KiCad 7's
Python module, and `route.py` also needs Java and `freerouting.jar` (Freerouting 2.5,
not included because it is 65 MB).
