#ifndef CONTROLS_H
#define CONTROLS_H
#include <stdint.h>

#define NUM_KNOBS    6
#define NUM_SWITCHES 3

enum { KNOB_DRIVE, KNOB_TONE, KNOB_RATE, KNOB_DEPTH, KNOB_TIME, KNOB_REPEATS };
enum { SW_OD, SW_TREM, SW_DELAY };

void     controls_init(void);
void     controls_tick_1ms(void);
float    controls_knob(int i);       /* 0.0 .. 1.0, smoothed */
uint16_t controls_knob_raw(int i);   /* 0 .. 4095 */
int      controls_switch(int i);     /* 1 = effect on */
void     controls_led(int i, int on);
void     controls_board_led(int on);

#endif
