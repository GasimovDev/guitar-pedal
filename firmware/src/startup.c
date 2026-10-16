/*
 * startup.c - what runs before main().
 *
 * After reset the Cortex-M4 reads two words from address 0x08000000:
 *   [0] the initial stack pointer, [1] the address of Reset_Handler.
 * The rest of that table (the "vector table") holds one function address per
 * interrupt. Reset_Handler then has to set up C itself: copy initialised
 * globals (.data) from flash to RAM, zero the others (.bss), turn on the FPU.
 */
#include <stdint.h>
#include "stm32f4xx.h"

extern uint32_t _estack, _sidata, _sdata, _edata, _sbss, _ebss;
extern int main(void);

void Reset_Handler(void);
void Default_Handler(void);

/* Handlers we actually use (defined in other files). The weak alias makes
 * any we forgot fall back to Default_Handler instead of a link error. */
void NMI_Handler(void)            __attribute__((weak, alias("Default_Handler")));
void HardFault_Handler(void)      __attribute__((weak, alias("Default_Handler")));
void SysTick_Handler(void)        __attribute__((weak, alias("Default_Handler")));
void DMA1_Stream3_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));

#define NUM_IRQ 86   /* STM32F411 has interrupt numbers 0..85 */

__attribute__((section(".isr_vector"), used))
void (*const vector_table[16 + NUM_IRQ])(void) = {
    [0]  = (void (*)(void))&_estack,
    [1]  = Reset_Handler,
    [2]  = NMI_Handler,
    [3]  = HardFault_Handler,
    [4]  = Default_Handler,     /* MemManage  */
    [5]  = Default_Handler,     /* BusFault   */
    [6]  = Default_Handler,     /* UsageFault */
    [11] = Default_Handler,     /* SVCall     */
    [14] = Default_Handler,     /* PendSV     */
    [15] = SysTick_Handler,
    [16 + DMA1_Stream3_IRQn] = DMA1_Stream3_IRQHandler,
};

void Reset_Handler(void)
{
    uint32_t *src = &_sidata, *dst = &_sdata;
    while (dst < &_edata) *dst++ = *src++;
    for (dst = &_sbss; dst < &_ebss; ) *dst++ = 0;

    /* Enable the floating point unit (coprocessors CP10 and CP11). Without
     * this, the first float instruction crashes into HardFault. */
    SCB->CPACR |= (0xFu << 20);
    __DSB(); __ISB();

    main();
    for (;;) { }
}

/* Any unexpected interrupt or crash ends here. Blink the Black Pill LED fast
 * so you can SEE that the firmware crashed (PC13, active low). */
void Default_Handler(void)
{
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOCEN;
    GPIOC->MODER = (GPIOC->MODER & ~(3u << 26)) | (1u << 26);
    for (;;) {
        GPIOC->ODR ^= (1u << 13);
        for (volatile uint32_t i = 0; i < 300000; i++) { }
    }
}
