/*
 * effects.c - overdrive, tremolo and delay.
 *
 * Signal chain (mono):
 *
 *   in -> [OVERDRIVE] -> [TREMOLO] -> [DELAY] -> out
 *
 * Every effect is mixed in with a ramp (0..1) instead of being switched on
 * instantly. Switching instantly makes a click, because the output jumps from
 * one value to another between two samples. A ~10 ms ramp is inaudible as a
 * fade but removes the click.
 */
#include "effects.h"
#include <math.h>

#define PI_F 3.14159265358979f

/* ---------- small building blocks ---------- */

/* Coefficient for a one-pole low-pass with cutoff fc (Hz). */
static float onepole_coef(float fc, float fs)
{
    return 1.0f - expf(-2.0f * PI_F * fc / fs);
}

static inline float onepole_run(onepole_t *f, float x)
{
    f->y += f->a * (x - f->y);
    return f->y;
}

static inline float clampf(float x, float lo, float hi)
{
    return x < lo ? lo : (x > hi ? hi : x);
}

/* Soft clipper: smooth like tanh(x) but much cheaper (no exp).
 * Rational approximation x(27+x^2)/(27+9x^2): equals 1.0 at x=3 with zero
 * slope there, so clamping to +-3 first gives a smooth curve into +-1. */
float dsp_softclip(float x)
{
    x = clampf(x, -3.0f, 3.0f);
    float x2 = x * x;
    return x * (27.0f + x2) / (27.0f + 9.0f * x2);
}

/* sin(2*pi*phase) for phase in [0,1). Parabolic approximation with one
 * correction step, max error about 0.001 - plenty for an LFO. */
float dsp_sin2pi(float phase01)
{
    float x = phase01 - (float)(int)phase01;   /* wrap to [0,1) */
    x = x * 2.0f - 1.0f;                       /* [-1,1) = [-pi, pi) */
    float y = 4.0f * x * (1.0f - fabsf(x));    /* parabola, this is -sin */
    y = 0.225f * (y * fabsf(y) - y) + y;       /* sharpen the parabola  */
    return -y;
}

/* ---------- knob -> real units ---------- */

float pedal_knob_to_delay_ms(float k)  { return 40.0f + 760.0f * clampf(k, 0, 1); }
float pedal_knob_to_rate_hz(float k)   { return 0.5f * powf(24.0f, clampf(k, 0, 1)); }
float pedal_knob_to_tone_hz(float k)   { return 800.0f * powf(10.0f, clampf(k, 0, 1)); }
float pedal_knob_to_drive_gain(float k)
{
    k = clampf(k, 0, 1);
    return 1.0f + 150.0f * k * k;   /* about 0 dB .. +44 dB, more resolution at low gain */
}

/* ---------- public API ---------- */

void pedal_init(pedal_t *p, float fs)
{
    /* Zero everything first (no memset so this builds without libc headers). */
    char *b = (char *)p;
    for (unsigned i = 0; i < sizeof(*p); i++) b[i] = 0;

    p->fs         = fs;
    p->smooth_a   = onepole_coef(20.0f, fs);
    p->switch_a   = onepole_coef(1.0f / (2.0f * PI_F * 0.010f), fs); /* tau = 10 ms  */
    p->dly_time_a = onepole_coef(1.0f / (2.0f * PI_F * 0.150f), fs); /* tau = 150 ms */
    p->od_pre_lp.a = onepole_coef(300.0f, fs);
    p->dly_damp.a  = onepole_coef(4000.0f, fs);

    pedal_params_t def = { 0.3f, 0.5f, 0.3f, 0.5f, 0.4f, 0.3f, false, false, false };
    pedal_set_params(p, &def);

    /* Start the smoothed values at their targets so nothing glides at boot. */
    p->od_gain = p->od_gain_t;     p->od_tone_a = p->od_tone_a_t;
    p->od_level = p->od_level_t;   p->trem_inc = p->trem_inc_t;
    p->trem_depth = p->trem_depth_t;
    p->dly_samples = p->dly_samples_t;  p->dly_fb = p->dly_fb_t;
    p->od_tone.a = p->od_tone_a;
}

void pedal_set_params(pedal_t *p, const pedal_params_t *k)
{
    p->od_gain_t   = pedal_knob_to_drive_gain(k->drive);
    p->od_tone_a_t = onepole_coef(pedal_knob_to_tone_hz(k->tone), p->fs);
    /* The clipper output is always near +-1, however quiet the guitar is,
     * so more gain = much louder. Turn the level down as the gain goes up.
     * Result: overdrive is ~+6..+9 dB louder than the dry guitar (a normal
     * "boost" feel) instead of +17 dB. */
    p->od_level_t  = 0.7f / (1.0f + 0.03f * p->od_gain_t);

    p->trem_inc_t   = pedal_knob_to_rate_hz(k->rate) / p->fs;
    p->trem_depth_t = clampf(k->depth, 0, 1);

    float d = pedal_knob_to_delay_ms(k->time) * 0.001f * p->fs;
    p->dly_samples_t = clampf(d, 1.0f, (float)(DELAY_MAX_SAMPLES - 2));
    p->dly_fb_t      = 0.9f * clampf(k->repeats, 0, 1);   /* < 1 => always dies out */

    p->od_en_t   = k->od_on   ? 1.0f : 0.0f;
    p->trem_en_t = k->trem_on ? 1.0f : 0.0f;
    p->dly_en_t  = k->dly_on  ? 1.0f : 0.0f;
}

void pedal_process(pedal_t *p, const float *in, float *out, int n)
{
    const float sa = p->smooth_a, wa = p->switch_a, ta = p->dly_time_a;

    for (int i = 0; i < n; i++) {
        /* --- smooth every control so knob turns never click or zipper --- */
        p->od_gain    += sa * (p->od_gain_t    - p->od_gain);
        p->od_tone_a  += sa * (p->od_tone_a_t  - p->od_tone_a);
        p->od_level   += sa * (p->od_level_t   - p->od_level);
        p->trem_inc   += sa * (p->trem_inc_t   - p->trem_inc);
        p->trem_depth += sa * (p->trem_depth_t - p->trem_depth);
        p->dly_fb     += sa * (p->dly_fb_t     - p->dly_fb);
        p->dly_samples += ta * (p->dly_samples_t - p->dly_samples);
        p->od_en      += wa * (p->od_en_t      - p->od_en);
        p->trem_en    += wa * (p->trem_en_t    - p->trem_en);
        p->dly_en     += wa * (p->dly_en_t     - p->dly_en);

        float x = in[i];

        /* ================= 1. OVERDRIVE ================= */
        /* Cut some bass before clipping (like a Tube Screamer): bass clips
         * first and sounds muddy, so we clip mostly mids and highs. */
        float low = onepole_run(&p->od_pre_lp, x);
        float pre = x - 0.75f * low;
        float clipped = dsp_softclip(p->od_gain * pre);
        p->od_tone.a = p->od_tone_a;
        float od = onepole_run(&p->od_tone, clipped) * p->od_level;
        /* DC blocker: y = x - x1 + 0.995*y1 (high-pass around 38 Hz) */
        float dc = od - p->dc_x1 + 0.995f * p->dc_y1;
        p->dc_x1 = od;  p->dc_y1 = dc;
        x = x + p->od_en * (dc - x);

        /* ================= 2. TREMOLO ================= */
        /* An LFO (low frequency oscillator) moves the volume up and down. */
        p->trem_phase += p->trem_inc;
        if (p->trem_phase >= 1.0f) p->trem_phase -= 1.0f;
        float lfo  = dsp_sin2pi(p->trem_phase);              /* -1..1 */
        float gain = 1.0f - p->trem_depth * 0.5f * (1.0f - lfo); /* 1-depth .. 1 */
        x = x * (1.0f + p->trem_en * (gain - 1.0f));

        /* ================= 3. DELAY ================= */
        /* Read the past: position = now - delay. The delay is fractional
         * (e.g. 12345.67 samples), so mix the two neighbours (linear
         * interpolation). That also makes knob turns glide in pitch like
         * a tape delay instead of clicking. */
        float rpos = (float)p->dly_w - p->dly_samples;
        if (rpos < 0.0f) rpos += (float)DELAY_MAX_SAMPLES;
        uint32_t i0 = (uint32_t)rpos;
        float frac  = rpos - (float)i0;
        uint32_t i1 = i0 + 1;
        if (i1 >= DELAY_MAX_SAMPLES) i1 = 0;
        float wet = ((float)p->dly_buf[i0] * (1.0f - frac) +
                     (float)p->dly_buf[i1] * frac) * (1.0f / 32767.0f);

        /* Write the present: input (only while the delay is ON) plus the
         * darkened, softly limited echo. When you switch the delay off the
         * input stops, but old echoes keep fading out ("trails"). */
        float fbk = onepole_run(&p->dly_damp, wet) * p->dly_fb;
        float wr  = dsp_softclip(p->dly_en * x + fbk);
        p->dly_buf[p->dly_w] = (int16_t)(clampf(wr, -1.0f, 1.0f) * 32767.0f);
        if (++p->dly_w >= DELAY_MAX_SAMPLES) p->dly_w = 0;

        x = x + 0.7f * wet;

        out[i] = clampf(x, -1.0f, 1.0f);
    }
}
