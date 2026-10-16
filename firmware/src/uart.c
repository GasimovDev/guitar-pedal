/*
 * uart.c - text output on PA9 for debugging (115200 baud, 8N1).
 * Connect a USB-serial adapter: its RX to PA9 (UART header pin TX), GND to GND.
 */
#include "board.h"
#include "uart.h"

void uart_init(void)
{
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN;
    RCC->APB2ENR |= RCC_APB2ENR_USART1EN;
    (void)RCC->APB2ENR;
    gpio_af(GPIOA, 9, 7);
    gpio_af(GPIOA, 10, 7);
    gpio_pullup(GPIOA, 10);
    /* Baud divider = 96 MHz / 115200 = 833.3 -> 833 (0.04 % error). */
    USART1->BRR = (APB2_HZ + 115200u / 2u) / 115200u;
    USART1->CR1 = USART_CR1_TE | USART_CR1_RE | USART_CR1_UE;
}

void uart_putc(char c)
{
    while (!(USART1->SR & USART_SR_TXE)) { }
    USART1->DR = (uint8_t)c;
}

void uart_puts(const char *s)
{
    while (*s) {
        if (*s == '\n') uart_putc('\r');
        uart_putc(*s++);
    }
}

void uart_putu(uint32_t v)
{
    char b[11]; int i = 10; b[i] = 0;
    do { b[--i] = (char)('0' + v % 10u); v /= 10u; } while (v && i);
    uart_puts(&b[i]);
}
