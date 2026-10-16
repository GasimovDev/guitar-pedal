# Build and run the DSP on your computer (Linux, macOS, or Windows with MSYS2/WSL).
#   make        -> build, run the tests, write demo WAVs into out/
#   make plots  -> also draw out/*.png (needs python3 + numpy + matplotlib)

CC     ?= gcc
CFLAGS  = -std=c99 -O2 -Wall -Wextra -Wno-unused-result -D_DEFAULT_SOURCE

all: run

sim: sim.c ../dsp/effects.c ../dsp/effects.h
	$(CC) $(CFLAGS) -o $@ sim.c ../dsp/effects.c -lm

run: sim
	mkdir -p out
	./sim

plots: run
	python3 plot_demos.py

clean:
	rm -rf sim out

.PHONY: all run plots clean
