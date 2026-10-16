#ifndef AUDIO_IO_H
#define AUDIO_IO_H
#include <stdint.h>

/* Called from the DMA interrupt with AUDIO_BLOCK mono samples in [-1, 1).
 * It must finish in less than one block time (0.67 ms) or audio glitches. */
typedef void (*audio_callback_t)(const float *in, float *out, int n);

extern volatile uint32_t g_audio_cycles;
extern volatile uint32_t g_audio_blocks;

void audio_init(audio_callback_t cb);
void audio_start(void);
void audio_unmute(int on);

#endif
