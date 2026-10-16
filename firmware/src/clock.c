/*
 * clock.c - turn the 25 MHz crystal into the clocks we need.
 *
 *   25 MHz crystal (HSE) / M=25 = 1 MHz reference for both PLLs
 *
 *   Main PLL : 1 MHz * N=192 = 192 MHz, / P=2 = 96 MHz CPU clock
 *                                       / Q=4 = 48 MHz (USB, unused)
 *   I2S PLL  : 1 MHz * N=258 = 258 MHz, / R=3 = 86 MHz I2S clock
 *
 *   The I2S block divides 86 MHz by 256*7 = 47991 Hz sample rate and puts
 *   86 MHz / 7 = 12.29 MHz (= 256 x fs) on the MCLK pin for the converters.
 *   (Exactly 48000 is impossible from 25 MHz; 0.02 % off is inaudible.)
 */
#include "board.h"
#include "clock.h"

volatile uint32_t g_ms;   /* milliseconds since boot, counted by SysTick */

void clock_init(void)
{
    /* Power interface: allow the highest speed (voltage scale 1). */
    RCC->APB1ENR |= RCC_APB1ENR_PWREN;
    PWR->CR = (PWR->CR & ~PWR_CR_VOS_Msk) | (3u << PWR_CR_VOS_Pos);

    /* Flash is slower than the CPU: 3 wait states at 96 MHz / 3.3 V,
     * plus the prefetch and caches so it doesn't slow us down. */
    FLASH->ACR = FLASH_ACR_LATENCY_3WS | FLASH_ACR_PRFTEN | FLASH_ACR_ICEN | FLASH_ACR_DCEN;

    /* Start the crystal oscillator and wait until it is stable. */
    RCC->CR |= RCC_CR_HSEON;
    while (!(RCC->CR & RCC_CR_HSERDY)) { }

    RCC->PLLCFGR = (25u << RCC_PLLCFGR_PLLM_Pos) |
                   (192u << RCC_PLLCFGR_PLLN_Pos) |
                   (0u << RCC_PLLCFGR_PLLP_Pos) |      /* 0 means /2 */
                   (4u << RCC_PLLCFGR_PLLQ_Pos) |
                   RCC_PLLCFGR_PLLSRC_HSE;

    RCC->PLLI2SCFGR = (25u << RCC_PLLI2SCFGR_PLLI2SM_Pos) |
                      (258u << RCC_PLLI2SCFGR_PLLI2SN_Pos) |
                      (3u << RCC_PLLI2SCFGR_PLLI2SR_Pos);

    /* Bus dividers: AHB 96 MHz, APB1 48 MHz (its max is 50), APB2 96 MHz. */
    RCC->CFGR = RCC_CFGR_HPRE_DIV1 | RCC_CFGR_PPRE1_DIV2 | RCC_CFGR_PPRE2_DIV1;

    RCC->CR |= RCC_CR_PLLON | RCC_CR_PLLI2SON;
    while (!(RCC->CR & RCC_CR_PLLRDY)) { }
    while (!(RCC->CR & RCC_CR_PLLI2SRDY)) { }

    /* Switch the CPU over to the PLL. */
    RCC->CFGR = (RCC->CFGR & ~RCC_CFGR_SW) | RCC_CFGR_SW_PLL;
    while ((RCC->CFGR & RCC_CFGR_SWS) != RCC_CFGR_SWS_PLL) { }

    /* SysTick interrupt every 1 ms. */
    SysTick_Config(SYSCLK_HZ / 1000u);

    /* Cycle counter, used to measure how much CPU the audio code takes. */
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

void delay_ms(uint32_t ms)
{
    uint32_t start = g_ms;
    while ((g_ms - start) < ms) { }
}
