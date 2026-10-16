#ifndef CLOCK_H
#define CLOCK_H
#include <stdint.h>

/* 'volatile' because SysTick_Handler (an interrupt) changes it behind main's
 * back. Without volatile the compiler may read it once and loop forever. */
extern volatile uint32_t g_ms;

void clock_init(void);
void delay_ms(uint32_t ms);

#endif
