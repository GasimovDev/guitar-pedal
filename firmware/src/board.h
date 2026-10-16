/*
 * board.h - which STM32 pin is wired to what on the pedal PCB.
 * Must match hardware/ (schematic net names in brackets).
 *
 *  Audio (I2S2, full duplex)
 *    PA3  I2S2_MCK   AF5  -> PCM1808 SCKI, PCM5102A SCK   [MCLK]  12.29 MHz
 *    PB13 I2S2_CK    AF5  -> both converters' BCK          [BCK]    3.07 MHz
 *    PB12 I2S2_WS    AF5  -> both converters' LRCK         [LRCK]  48 kHz
 *    PB15 I2S2_SD    AF5  -> PCM5102A DIN  (DAC data out)  [DAC_DIN]
 *    PB14 I2S2ext_SD AF6  <- PCM1808 DOUT  (ADC data in)   [ADC_DOUT]
 *    PB9  GPIO out        -> PCM5102A XSMT (low = mute)    [DAC_XSMT]
 *
 *  Knobs (ADC1, 0..3.3 V, ratiometric)
 *    PA1 IN1 DRIVE   PA2 IN2 TONE   PA4 IN4 RATE
 *    PA5 IN5 DEPTH   PA6 IN6 TIME   PA7 IN7 REPEATS
 *
 *  Footswitches (to GND when pressed, internal pull-up)
 *    PB6 OD   PB7 TREM   PB8 DELAY
 *
 *  LEDs (high = on)
 *    PB0 OD   PB1 TREM   PB10 DELAY       PC13 = Black Pill's own LED (low = on)
 *
 *  Debug UART (USART1, 115200 8N1)
 *    PA9 TX   PA10 RX
 */
#ifndef BOARD_H
#define BOARD_H

#include "stm32f4xx.h"

#define SYSCLK_HZ   96000000u
#define APB1_HZ     48000000u
#define APB2_HZ     96000000u

/* Exact rate the I2S clock tree gives: 86 MHz / (256 * 7) */
#define AUDIO_FS_HZ 47991.07f

/* Half of the DMA buffer is processed at a time: 32 frames = 0.67 ms. */
#define AUDIO_BLOCK 32

/* Small helpers for GPIO setup. mode: 0 in, 1 out, 2 alternate, 3 analog */
static inline void gpio_mode(GPIO_TypeDef *g, int pin, int mode)
{
    g->MODER = (g->MODER & ~(3u << (pin * 2))) | ((uint32_t)mode << (pin * 2));
}
static inline void gpio_af(GPIO_TypeDef *g, int pin, int af)
{
    volatile uint32_t *r = &g->AFR[pin >> 3];
    int s = (pin & 7) * 4;
    *r = (*r & ~(0xFu << s)) | ((uint32_t)af << s);
    gpio_mode(g, pin, 2);
}
static inline void gpio_speed_high(GPIO_TypeDef *g, int pin)
{
    g->OSPEEDR |= (3u << (pin * 2));
}
static inline void gpio_pullup(GPIO_TypeDef *g, int pin)
{
    g->PUPDR = (g->PUPDR & ~(3u << (pin * 2))) | (1u << (pin * 2));
}
static inline void gpio_write(GPIO_TypeDef *g, int pin, int on)
{
    g->BSRR = on ? (1u << pin) : (1u << (pin + 16));
}
static inline int gpio_read(GPIO_TypeDef *g, int pin)
{
    return (g->IDR >> pin) & 1u;
}

#endif
