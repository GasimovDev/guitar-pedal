/*
 * effects.h - the sound of the pedal: overdrive -> tremolo -> delay.
 *
 * This file is plain C99 with no hardware code in it, so the exact same
 * code runs on the STM32 (firmware) and on your laptop (host/ simulator).
 * That is how you test DSP: prove it on the PC first, then flash it.
 *
 * Audio is mono float, nominally in [-1.0, +1.0]. 1.0 = ADC full scale.
 */
#ifndef EFFECTS_H
#define EFFECTS_H

#include <stdbool.h>
#include <stdint.h>

/* Longest delay we can store. 0.8 s at 48 kHz = 38400 samples.
 * Stored as int16 (2 bytes) => ~77 KB of the STM32F411's 128 KB RAM. */
#define DELAY_MAX_SAMPLES 40000

/* What the knobs and footswitches say. Knobs are 0.0 (fully CCW) .. 1.0 (CW). */
typedef struct {
    float drive;    /* K1 overdrive gain                         */
    float tone;     /* K2 overdrive brightness                   */
    float rate;     /* K3 tremolo speed  (0.5 .. 12 Hz)           */
    float depth;    /* K4 tremolo depth  (0 .. 100 %)             */
    float time;     /* K5 delay time     (40 .. 800 ms)           */
    float repeats;  /* K6 delay feedback (0 .. 90 %)              */
    bool  od_on;    /* footswitch 1 */
    bool  trem_on;  /* footswitch 2 */
    bool  dly_on;   /* footswitch 3 */
} pedal_params_t;

/* One-pole filter state: y[n] = y[n-1] + a * (x[n] - y[n-1]) */
typedef struct { float a, y; } onepole_t;

typedef struct {
    float fs;                 /* sample rate in Hz */

    /* --- targets computed from the knobs (set_params) --- */
    float od_gain_t, od_tone_a_t, od_level_t;
    float trem_inc_t, trem_depth_t;
    float dly_samples_t, dly_fb_t;
    float od_en_t, trem_en_t, dly_en_t;   /* 0 or 1 */

    /* --- smoothed values actually used per sample --- */
    float od_gain, od_tone_a, od_level;
    float trem_inc, trem_depth;
    float dly_samples, dly_fb;
    float od_en, trem_en, dly_en;         /* ramp 0..1 = click-free switching */
    float smooth_a;       /* knob smoothing coefficient (~20 Hz)  */
    float switch_a;       /* footswitch crossfade coefficient (~10 ms) */
    float dly_time_a;     /* delay-time glide coefficient (~0.15 s) */

    /* --- overdrive state --- */
    onepole_t od_pre_lp;  /* used to make a high-pass in front of the clipper */
    onepole_t od_tone;    /* tone low-pass after the clipper */
    float dc_x1, dc_y1;   /* DC blocker */

    /* --- tremolo state --- */
    float trem_phase;     /* 0..1 */

    /* --- delay state --- */
    int16_t  dly_buf[DELAY_MAX_SAMPLES];
    uint32_t dly_w;       /* write index */
    onepole_t dly_damp;   /* darkens each repeat like an analog delay */
} pedal_t;

void  pedal_init(pedal_t *p, float fs);
void  pedal_set_params(pedal_t *p, const pedal_params_t *k);
void  pedal_process(pedal_t *p, const float *in, float *out, int n);

/* Exposed so tests and the UART debug print can show real units. */
float pedal_knob_to_delay_ms(float k);
float pedal_knob_to_rate_hz(float k);
float pedal_knob_to_drive_gain(float k);
float pedal_knob_to_tone_hz(float k);

/* Helpers (also used by the tests). */
float dsp_softclip(float x);
float dsp_sin2pi(float phase01);

#endif
