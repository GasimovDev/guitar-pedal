/*
 * sim.c - run the pedal DSP on your PC.
 *
 *   make -C firmware/host        (builds and runs everything)
 *
 * 1. Unit tests: each effect is checked with a signal whose correct answer
 *    we know in advance (an impulse, a steady sine, silence...).
 * 2. Demo renders: a synthetic guitar riff is played through each effect
 *    and written to WAV files you can listen to.
 *
 * Usage: sim [input.wav]    (16-bit mono/stereo WAV; default = synth riff)
 */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../dsp/effects.h"

#define FS 48000
#define PI_F 3.14159265358979f

static pedal_t pedal;   /* big (delay buffer), so not on the stack */
static int failures = 0;

#define CHECK(cond, ...) do { \
    if (cond) { printf("  PASS  "); } else { printf("  FAIL  "); failures++; } \
    printf(__VA_ARGS__); printf("\n"); } while (0)

/* ---------------- WAV I/O (16-bit PCM) ---------------- */

static void put_u32(FILE *f, uint32_t v) { fwrite(&v, 4, 1, f); }
static void put_u16(FILE *f, uint16_t v) { fwrite(&v, 2, 1, f); }

static void wav_write(const char *path, const float *x, int n)
{
    FILE *f = fopen(path, "wb");
    if (!f) { perror(path); return; }
    fwrite("RIFF", 1, 4, f); put_u32(f, 36 + n * 2);
    fwrite("WAVEfmt ", 1, 8, f); put_u32(f, 16);
    put_u16(f, 1); put_u16(f, 1); put_u32(f, FS); put_u32(f, FS * 2);
    put_u16(f, 2); put_u16(f, 16);
    fwrite("data", 1, 4, f); put_u32(f, n * 2);
    for (int i = 0; i < n; i++) {
        float v = x[i] < -1 ? -1 : (x[i] > 1 ? 1 : x[i]);
        int16_t s = (int16_t)lrintf(v * 32767.0f);
        fwrite(&s, 2, 1, f);
    }
    fclose(f);
}

/* Minimal reader: finds "fmt " and "data", 16-bit only, mixes to mono. */
static float *wav_read(const char *path, int *n_out)
{
    FILE *f = fopen(path, "rb");
    if (!f) { perror(path); return NULL; }
    char id[4]; uint32_t sz; uint16_t ch = 1, bits = 16; uint32_t rate = FS;
    fseek(f, 12, SEEK_SET);
    while (fread(id, 1, 4, f) == 4 && fread(&sz, 4, 1, f) == 1) {
        if (!memcmp(id, "fmt ", 4)) {
            uint16_t fmt; fread(&fmt, 2, 1, f); fread(&ch, 2, 1, f);
            fread(&rate, 4, 1, f); fseek(f, 6, SEEK_CUR); fread(&bits, 2, 1, f);
            fseek(f, sz - 16, SEEK_CUR);
        } else if (!memcmp(id, "data", 4)) {
            if (bits != 16) { fprintf(stderr, "only 16-bit WAV supported\n"); break; }
            int frames = sz / (2 * ch);
            float *x = malloc(sizeof(float) * frames);
            for (int i = 0; i < frames; i++) {
                float acc = 0;
                for (int c = 0; c < ch; c++) { int16_t s; fread(&s, 2, 1, f); acc += s; }
                x[i] = acc / (32768.0f * ch);
            }
            if (rate != FS) fprintf(stderr, "warning: file is %u Hz, pedal runs at %d Hz\n", rate, FS);
            fclose(f); *n_out = frames; return x;
        } else fseek(f, sz, SEEK_CUR);
    }
    fclose(f); return NULL;
}

/* ---------------- a fake guitar (Karplus-Strong) ---------------- */
/* A plucked string is a burst of noise going round a delay line whose
 * length is one period of the note, getting a little darker each trip. */
static void pluck(float *out, int n, int start, float freq, float amp)
{
    int L = (int)(FS / freq);
    float *line = calloc(L, sizeof(float));
    uint32_t seed = 12345u + (uint32_t)(freq * 10);
    for (int i = 0; i < L; i++) {
        seed = seed * 1664525u + 1013904223u;
        line[i] = ((seed >> 9) * (1.0f / 4194304.0f) - 1.0f) * amp;
    }
    float prev = 0; int idx = 0;
    for (int t = start; t < n; t++) {
        float v = line[idx];
        float nv = 0.996f * 0.5f * (v + prev);
        prev = v; line[idx] = nv;
        out[t] += v;
        if (++idx >= L) idx = 0;
    }
    free(line);
}

static float *make_riff(int *n_out)
{
    int n = FS * 8;
    float *x = calloc(n, sizeof(float));
    /* E5 power chord, single notes, then an open A chord. Amplitudes are a
     * typical guitar level into the ADC (~0.2 .. 0.4 of full scale). */
    const struct { float t, f, a; } notes[] = {
        {0.0f, 82.41f, 0.30f}, {0.0f, 123.47f, 0.25f}, {0.0f, 164.81f, 0.2f},
        {1.0f, 82.41f, 0.30f}, {1.0f, 123.47f, 0.25f}, {1.0f, 164.81f, 0.2f},
        {2.0f, 196.0f, 0.25f}, {2.25f, 220.0f, 0.25f}, {2.5f, 246.9f, 0.25f},
        {2.75f, 293.7f, 0.25f}, {3.0f, 329.6f, 0.30f},
        {4.5f, 110.0f, 0.25f}, {4.5f, 164.8f, 0.2f}, {4.5f, 220.0f, 0.2f},
        {4.5f, 277.2f, 0.18f}, {4.5f, 329.6f, 0.18f},
    };
    for (unsigned i = 0; i < sizeof notes / sizeof notes[0]; i++)
        pluck(x, n, (int)(notes[i].t * FS), notes[i].f, notes[i].a);
    *n_out = n;
    return x;
}

/* ---------------- helpers ---------------- */

static pedal_params_t knobs_default(void)
{
    pedal_params_t k = { 0.5f, 0.5f, 0.4f, 0.7f, 0.45f, 0.4f, false, false, false };
    return k;
}

/* Process in blocks of 32, exactly like the firmware's DMA callback does. */
static void run(const pedal_params_t *k, const float *in, float *out, int n)
{
    pedal_init(&pedal, FS);
    pedal_set_params(&pedal, k);
    for (int i = 0; i < n; i += 32) {
        int m = (n - i) < 32 ? (n - i) : 32;
        pedal_process(&pedal, in + i, out + i, m);
    }
}

static float rms(const float *x, int n)
{
    double s = 0; for (int i = 0; i < n; i++) s += (double)x[i] * x[i];
    return (float)sqrt(s / n);
}

/* Total harmonic distortion of a 1 kHz sine via a plain DFT at harmonics. */
static float thd_percent(const float *x, int n, float f0)
{
    double p[8] = {0};
    for (int h = 1; h < 8; h++) {
        double re = 0, im = 0, w = 2 * M_PI * f0 * h / FS;
        for (int i = 0; i < n; i++) { re += x[i] * cos(w * i); im += x[i] * sin(w * i); }
        p[h] = re * re + im * im;
    }
    double harm = 0; for (int h = 2; h < 8; h++) harm += p[h];
    return (float)(100.0 * sqrt(harm / p[1]));
}

/* ---------------- tests ---------------- */

static void test_bypass(void)
{
    printf("[bypass] all effects off must pass the signal unchanged\n");
    int n = FS / 2;
    float *in = malloc(n * sizeof(float)), *out = malloc(n * sizeof(float));
    for (int i = 0; i < n; i++) in[i] = 0.5f * sinf(2 * PI_F * 440 * i / FS);
    pedal_params_t k = knobs_default();
    run(&k, in, out, n);
    float err = 0;
    for (int i = 0; i < n; i++) { float e = fabsf(out[i] - in[i]); if (e > err) err = e; }
    CHECK(err < 1e-5f, "max difference = %.2e (want < 1e-5)", err);
    free(in); free(out);
}

static void test_delay_time(void)
{
    printf("[delay] an impulse must come back exactly 'time' ms later\n");
    int n = FS;
    float *in = calloc(n, sizeof(float)), *out = malloc(n * sizeof(float));
    pedal_params_t k = knobs_default();
    k.dly_on = true; k.time = 0.5f; k.repeats = 0.0f;
    pedal_init(&pedal, FS);
    pedal_set_params(&pedal, &k);
    pedal.dly_en = 1.0f;           /* skip the 10 ms switch-on ramp for this test */
    pedal.dly_samples = pedal.dly_samples_t;   /* and the delay-time glide */
    in[1000] = 0.8f;
    for (int i = 0; i < n; i += 32) pedal_process(&pedal, in + i, out + i, 32);
    int peak = 1001; float pv = 0;
    for (int i = 1001; i < n; i++) if (fabsf(out[i]) > pv) { pv = fabsf(out[i]); peak = i; }
    float ms = (peak - 1000) * 1000.0f / FS;
    float want = pedal_knob_to_delay_ms(0.5f);
    CHECK(fabsf(ms - want) < 0.05f, "echo at %.2f ms (want %.2f ms), echo level %.2f", ms, want, pv);
    free(in); free(out);
}

static void test_delay_stable(void)
{
    printf("[delay] max repeats must die away, never run away\n");
    int n = FS * 20;
    float *in = calloc(n, sizeof(float)), *out = malloc(n * sizeof(float));
    for (int i = 0; i < FS / 10; i++) in[i] = 0.9f * sinf(2 * PI_F * 300 * i / FS);
    pedal_params_t k = knobs_default();
    k.dly_on = true; k.repeats = 1.0f; k.time = 0.1f;
    run(&k, in, out, n);
    float early = rms(out, FS), late = rms(out + n - FS, FS);
    int bad = 0; for (int i = 0; i < n; i++) if (!isfinite(out[i])) bad++;
    CHECK(late < early * 0.05f && bad == 0,
          "rms first second %.3f, last second %.5f, non-finite samples %d", early, late, bad);
    free(in); free(out);
}

static void test_tremolo(void)
{
    printf("[tremolo] the volume must wobble at the RATE knob's frequency\n");
    int n = FS * 4;
    float *in = malloc(n * sizeof(float)), *out = malloc(n * sizeof(float));
    for (int i = 0; i < n; i++) in[i] = 0.5f * sinf(2 * PI_F * 1000 * i / FS);
    pedal_params_t k = knobs_default();
    k.trem_on = true; k.rate = 0.5f; k.depth = 1.0f;
    run(&k, in, out, n);
    /* envelope = rms over 1 ms windows; count its minima */
    int win = FS / 1000, nw = n / win, minima = 0;
    float *env = malloc(nw * sizeof(float));
    for (int w = 0; w < nw; w++) env[w] = rms(out + w * win, win);
    for (int w = 500 + 1; w < nw - 1; w++)   /* skip the first 0.5 s */
        if (env[w] < env[w - 1] && env[w] <= env[w + 1] && env[w] < 0.05f) minima++;
    float hz = minima / ((nw - 501) / 1000.0f);
    float want = pedal_knob_to_rate_hz(0.5f);
    float lo = 1, hi = 0; for (int w = 500; w < nw; w++) { if (env[w] < lo) lo = env[w]; if (env[w] > hi) hi = env[w]; }
    CHECK(fabsf(hz - want) < 0.4f, "measured %.2f Hz (want %.2f Hz)", hz, want);
    CHECK(lo < 0.02f && hi > 0.3f, "depth 100%%: envelope goes from %.3f to %.3f", lo, hi);
    free(in); free(out); free(env);
}

static void test_overdrive(void)
{
    printf("[overdrive] more DRIVE must mean more distortion, output stays bounded\n");
    int n = FS;
    float *in = malloc(n * sizeof(float)), *out = malloc(n * sizeof(float));
    for (int i = 0; i < n; i++) in[i] = 0.3f * sinf(2 * PI_F * 1000 * i / FS);
    float last = -1; int monotonic = 1;
    for (int d = 0; d <= 4; d++) {
        pedal_params_t k = knobs_default();
        k.od_on = true; k.drive = d / 4.0f; k.tone = 1.0f;
        run(&k, in, out, n);
        float thd = thd_percent(out + FS / 2, FS / 2, 1000);
        float peak = 0; for (int i = 0; i < n; i++) if (fabsf(out[i]) > peak) peak = fabsf(out[i]);
        printf("        drive %.2f -> THD %5.1f %%, peak %.2f\n", d / 4.0, thd, peak);
        if (thd < last) monotonic = 0;
        last = thd;
    }
    CHECK(monotonic && last > 10.0f, "THD rises with drive and is %.1f %% at full drive", last);
    free(in); free(out);
}

static float max_step(const float *x, int a, int b)
{
    float m = 0;
    for (int i = a + 1; i < b; i++) { float s = fabsf(x[i] - x[i - 1]); if (s > m) m = s; }
    return m;
}

static void test_no_clicks(void)
{
    printf("[switching] stomping a footswitch must not click\n");
    /* A click is a sudden jump. Overdrive itself has steep edges (that's
     * what clipping is), so compare against the effect running steadily:
     * switching must never make a bigger jump than the effects themselves. */
    int n = FS;
    float *in = malloc(n * sizeof(float)), *out = malloc(n * sizeof(float));
    for (int i = 0; i < n; i++) in[i] = 0.4f * sinf(2 * PI_F * 220 * i / FS);
    pedal_params_t k = knobs_default();
    k.drive = 0.8f; k.od_on = true; k.trem_on = true;
    run(&k, in, out, n);
    float steady = max_step(out, FS / 4, n);

    k.od_on = false; k.trem_on = false;
    pedal_init(&pedal, FS); pedal_set_params(&pedal, &k);
    for (int i = 0; i < n; i += 32) {
        if (i == FS / 4) { k.od_on = true;  k.trem_on = true;  pedal_set_params(&pedal, &k); }
        if (i == FS / 2) { k.od_on = false; k.trem_on = false; pedal_set_params(&pedal, &k); }
        pedal_process(&pedal, in + i, out + i, 32);
    }
    float sw = max_step(out, 0, n);
    CHECK(sw <= steady * 1.05f, "largest jump while switching %.4f, effect running steadily %.4f", sw, steady);
    free(in); free(out);
}

static void test_lfo_shape(void)
{
    printf("[helpers] fast sine and soft clipper match the real thing\n");
    float e = 0;
    for (int i = 0; i < 1000; i++) {
        float ph = i / 1000.0f, d = fabsf(dsp_sin2pi(ph) - sinf(2 * PI_F * ph));
        if (d > e) e = d;
    }
    CHECK(e < 0.002f, "fast sine max error %.4f", e);
    CHECK(fabsf(dsp_softclip(10.0f) - 1.0f) < 1e-6f && fabsf(dsp_softclip(0.01f) - 0.01f) < 1e-5f,
          "softclip(10)=%.4f, softclip(0.01)=%.5f", dsp_softclip(10.0f), dsp_softclip(0.01f));
}

/* ---------------- demo renders ---------------- */

static void render(const char *name, const float *in, int n, pedal_params_t k)
{
    float *out = malloc(n * sizeof(float));
    run(&k, in, out, n);
    char path[256];
    snprintf(path, sizeof path, "out/%s.wav", name);
    wav_write(path, out, n);
    printf("  wrote %s (rms %.3f)\n", path, rms(out, n));
    free(out);
}

int main(int argc, char **argv)
{
    printf("=== unit tests ===\n");
    test_lfo_shape();
    test_bypass();
    test_overdrive();
    test_tremolo();
    test_delay_time();
    test_delay_stable();
    test_no_clicks();

    printf("\n=== demo renders ===\n");
    int n = 0;
    float *riff = (argc > 1) ? wav_read(argv[1], &n) : make_riff(&n);
    if (!riff) return 1;
    wav_write("out/00_dry.wav", riff, n);
    printf("  wrote out/00_dry.wav (rms %.3f)\n", rms(riff, n));

    pedal_params_t k = knobs_default();
    k.od_on = true;  k.drive = 0.7f; k.tone = 0.45f;  render("01_overdrive", riff, n, k);
    k = knobs_default(); k.trem_on = true; k.rate = 0.45f; k.depth = 0.8f; render("02_tremolo", riff, n, k);
    k = knobs_default(); k.dly_on = true; k.time = 0.45f; k.repeats = 0.5f; render("03_delay", riff, n, k);
    k = knobs_default(); k.od_on = k.trem_on = k.dly_on = true; k.drive = 0.6f; render("04_all_three", riff, n, k);
    free(riff);

    printf("\n%s: %d failure(s)\n", failures ? "FAILED" : "ALL TESTS PASSED", failures);
    return failures ? 1 : 0;
}
