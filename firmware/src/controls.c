/*
 * controls.c - knobs, footswitches and LEDs.
 *
 * Knobs: ADC1 converts the six pot wipers over and over by itself (scan +
 * continuous mode) and DMA2 keeps the latest six results in adc_raw[].
 * Nobody has to start a conversion; we just read the array.
 *
 * Footswitches: a mechanical switch "bounces" - it opens and closes many
 * times in the first few ms. We only accept a new state after it has been
 * stable for 20 ms (checked every 1 ms from SysTick).
 */
#include "board.h"
#include "controls.h"

static volatile uint16_t adc_raw[NUM_KNOBS];
static float knob_smooth[NUM_KNOBS];

/* ADC channel for each knob, in knob order K1..K6 */
static const uint8_t knob_channel[NUM_KNOBS] = { 1, 2, 4, 5, 6, 7 };
static const uint8_t knob_pin[NUM_KNOBS]     = { 1, 2, 4, 5, 6, 7 };   /* all on GPIOA */

static const uint8_t sw_pin[NUM_SWITCHES]  = { 6, 7, 8 };    /* GPIOB */
static const uint8_t led_pin[NUM_SWITCHES] = { 0, 1, 10 };   /* GPIOB */

static volatile uint8_t sw_state[NUM_SWITCHES];   /* toggled on each press */
static uint8_t sw_stable[NUM_SWITCHES], sw_count[NUM_SWITCHES];

void controls_init(void)
{
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN | RCC_AHB1ENR_GPIOBEN | RCC_AHB1ENR_GPIOCEN |
                    RCC_AHB1ENR_DMA2EN;
    RCC->APB2ENR |= RCC_APB2ENR_ADC1EN;
    (void)RCC->APB2ENR;

    for (int i = 0; i < NUM_KNOBS; i++) gpio_mode(GPIOA, knob_pin[i], 3);
    for (int i = 0; i < NUM_SWITCHES; i++) {
        gpio_mode(GPIOB, sw_pin[i], 0);
        gpio_pullup(GPIOB, sw_pin[i]);
        gpio_mode(GPIOB, led_pin[i], 1);
        sw_stable[i] = 1;   /* released = high (pull-up) */
    }
    gpio_mode(GPIOC, 13, 1);   /* Black Pill LED */

    /* ADC clock = 96 MHz / 4 = 24 MHz (max 36). */
    ADC1_COMMON->CCR = (1u << ADC_CCR_ADCPRE_Pos);
    ADC1->CR1 = ADC_CR1_SCAN;
    ADC1->CR2 = ADC_CR2_CONT | ADC_CR2_DMA | ADC_CR2_DDS;
    /* Longest sample time (480 cycles): pots are high impedance, give the
     * ADC's sampling capacitor plenty of time to charge. */
    ADC1->SMPR2 = 0x3FFFFFFFu;
    ADC1->SQR1  = (NUM_KNOBS - 1u) << ADC_SQR1_L_Pos;
    ADC1->SQR3  = 0;
    for (int i = 0; i < NUM_KNOBS; i++) ADC1->SQR3 |= (uint32_t)knob_channel[i] << (5 * i);

    /* DMA2 Stream0 channel 0 = ADC1, circular, 16-bit. */
    DMA2_Stream0->CR = 0;
    while (DMA2_Stream0->CR & DMA_SxCR_EN) { }
    DMA2_Stream0->PAR  = (uint32_t)&ADC1->DR;
    DMA2_Stream0->M0AR = (uint32_t)adc_raw;
    DMA2_Stream0->NDTR = NUM_KNOBS;
    DMA2_Stream0->CR = (0u << DMA_SxCR_CHSEL_Pos) | (1u << DMA_SxCR_MSIZE_Pos) |
                       (1u << DMA_SxCR_PSIZE_Pos) | DMA_SxCR_MINC | DMA_SxCR_CIRC;
    DMA2_Stream0->CR |= DMA_SxCR_EN;

    ADC1->CR2 |= ADC_CR2_ADON;
    for (volatile int i = 0; i < 1000; i++) { }    /* ADC power-up time */
    ADC1->CR2 |= ADC_CR2_SWSTART;

    for (int i = 0; i < NUM_KNOBS; i++) knob_smooth[i] = -1.0f;
}

/* Called every 1 ms from SysTick_Handler. */
void controls_tick_1ms(void)
{
    for (int i = 0; i < NUM_SWITCHES; i++) {
        uint8_t now = (uint8_t)gpio_read(GPIOB, sw_pin[i]);
        if (now != sw_stable[i]) {
            if (++sw_count[i] >= 20) {        /* 20 ms the same = real change */
                sw_stable[i] = now;
                sw_count[i] = 0;
                if (now == 0) sw_state[i] ^= 1u;   /* pressed (pulled to GND) */
            }
        } else {
            sw_count[i] = 0;
        }
    }
}

float controls_knob(int i)
{
    /* 12-bit ADC: 0..4095. Smooth to hide the last-bit flicker. */
    float v = (float)adc_raw[i] * (1.0f / 4095.0f);
    if (knob_smooth[i] < 0.0f) knob_smooth[i] = v;
    knob_smooth[i] += 0.2f * (v - knob_smooth[i]);
    return knob_smooth[i];
}

uint16_t controls_knob_raw(int i) { return adc_raw[i]; }

int controls_switch(int i) { return sw_state[i]; }

void controls_led(int i, int on) { gpio_write(GPIOB, led_pin[i], on); }

void controls_board_led(int on) { gpio_write(GPIOC, 13, !on); }   /* active low */
