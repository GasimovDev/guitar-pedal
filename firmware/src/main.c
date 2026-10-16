/*
 * main.c - guitar pedal firmware for the STM32F411 "Black Pill".
 *
 * Boot modes (hold a footswitch while plugging in power):
 *   none held  : normal pedal (overdrive -> tremolo -> delay)
 *   OD held    : TEST TONE  - a 440 Hz beep on the output, ignores the input.
 *                Proves MCU -> DAC -> output stage work.
 *   DELAY held : PASSTHROUGH - input copied to output, no effects.
 *                Proves input stage -> ADC -> MCU -> DAC -> output work.
 *
 * Every 0.5 s the UART prints knob values, switch states and CPU load.
 */
#include "board.h"
#include "clock.h"
#include "audio_io.h"
#include "controls.h"
#include "uart.h"
#include "../dsp/effects.h"

enum { MODE_PEDAL, MODE_TONE, MODE_THRU };

static pedal_t pedal;        /* ~80 KB, mostly the delay memory */
static volatile int mode = MODE_PEDAL;
static float tone_phase;

/* Runs inside the DMA interrupt every 0.67 ms. */
static void audio_cb(const float *in, float *out, int n)
{
    if (mode == MODE_PEDAL) {
        pedal_process(&pedal, in, out, n);
    } else if (mode == MODE_TONE) {
        for (int i = 0; i < n; i++) {
            tone_phase += 440.0f / AUDIO_FS_HZ;
            if (tone_phase >= 1.0f) tone_phase -= 1.0f;
            out[i] = 0.5f * dsp_sin2pi(tone_phase);
        }
    } else {
        for (int i = 0; i < n; i++) out[i] = in[i];
    }
}

void SysTick_Handler(void)
{
    g_ms++;
    controls_tick_1ms();
}

static void print_status(void)
{
    static const char *names[NUM_KNOBS] = { "DRV", "TONE", "RATE", "DEPTH", "TIME", "RPT" };
    for (int i = 0; i < NUM_KNOBS; i++) {
        uart_puts(names[i]); uart_putc('=');
        uart_putu((uint32_t)(controls_knob(i) * 100.0f + 0.5f));
        uart_puts("% ");
    }
    uart_puts(" OD="); uart_putu(controls_switch(SW_OD));
    uart_puts(" TREM="); uart_putu(controls_switch(SW_TREM));
    uart_puts(" DLY="); uart_putu(controls_switch(SW_DELAY));
    /* CPU load = cycles used per block / cycles available per block */
    uint32_t avail = (uint32_t)((float)SYSCLK_HZ * AUDIO_BLOCK / AUDIO_FS_HZ);
    uart_puts("  CPU="); uart_putu(g_audio_cycles * 100u / avail);
    uart_puts("%  blocks="); uart_putu(g_audio_blocks);
    uart_puts("\n");
}

int main(void)
{
    clock_init();
    uart_init();
    controls_init();
    uart_puts("\n\nGuitar pedal firmware - STM32F411 + PCM1808 + PCM5102A\n");

    /* Boot mode: switches read low (0) while held down. */
    delay_ms(50);
    if (!gpio_read(GPIOB, 6))      { mode = MODE_TONE; uart_puts("MODE: test tone 440 Hz\n"); }
    else if (!gpio_read(GPIOB, 8)) { mode = MODE_THRU; uart_puts("MODE: passthrough\n"); }
    else                             uart_puts("MODE: pedal\n");

    pedal_init(&pedal, AUDIO_FS_HZ);
    audio_init(audio_cb);
    audio_start();
    delay_ms(200);           /* let the converters lock to the clocks */
    audio_unmute(1);

    uint32_t last_ctl = 0, last_print = 0;
    for (;;) {
        uint32_t now = g_ms;

        if (now - last_ctl >= 5) {          /* read controls 200 times a second */
            last_ctl = now;
            pedal_params_t k;
            k.drive   = controls_knob(KNOB_DRIVE);
            k.tone    = controls_knob(KNOB_TONE);
            k.rate    = controls_knob(KNOB_RATE);
            k.depth   = controls_knob(KNOB_DEPTH);
            k.time    = controls_knob(KNOB_TIME);
            k.repeats = controls_knob(KNOB_REPEATS);
            k.od_on   = controls_switch(SW_OD);
            k.trem_on = controls_switch(SW_TREM);
            k.dly_on  = controls_switch(SW_DELAY);
            pedal_set_params(&pedal, &k);

            controls_led(SW_OD, k.od_on);
            /* Tremolo LED pulses in time with the tremolo. */
            controls_led(SW_TREM, k.trem_on && pedal.trem_phase < 0.5f);
            controls_led(SW_DELAY, k.dly_on);
        }

        if (now - last_print >= 500) {
            last_print = now;
            controls_board_led((now / 500) & 1);   /* heartbeat: "I'm alive" */
            print_status();
        }
    }
}
