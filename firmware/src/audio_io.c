/*
 * audio_io.c - stream audio in and out with I2S + DMA.
 *
 * I2S2 is the master: it makes MCLK, BCK and LRCK and sends DAC data.
 * I2S2ext is its twin that shares those clocks and only receives (ADC data).
 *
 * DMA (Direct Memory Access) copies every sample between the I2S data
 * register and RAM by itself, so the CPU never waits for a sample.
 * Each buffer is circular and split in two halves ("ping-pong"):
 *
 *   rx_buf: [ half A | half B ]  <- DMA fills from the ADC, forever
 *   tx_buf: [ half A | half B ]  -> DMA empties into the DAC, forever
 *
 * When the RX DMA has filled half A it interrupts us ("half transfer").
 * We process half A of rx into half A of tx while DMA works on half B.
 * Then the "transfer complete" interrupt does the same for half B.
 * Latency = one half buffer in + one out = about 1.3 ms.
 *
 * Format: Philips I2S, 16-bit data in a 32-bit slot per channel. The
 * converters send/accept 24 bits, the STM32 just keeps the top 16 (96 dB
 * of range; a guitar's own noise is far above that). One halfword per
 * channel, two per stereo frame: [L, R, L, R, ...].
 */
#include "board.h"
#include "audio_io.h"

#define HALF_WORDS (AUDIO_BLOCK * 2)          /* L+R per frame */
#define BUF_WORDS  (HALF_WORDS * 2)           /* two halves    */

static volatile int16_t rx_buf[BUF_WORDS];
static volatile int16_t tx_buf[BUF_WORDS];
static audio_callback_t user_cb;

volatile uint32_t g_audio_cycles;     /* CPU cycles used by the last block */
volatile uint32_t g_audio_blocks;     /* blocks processed since start      */

void audio_init(audio_callback_t cb)
{
    user_cb = cb;

    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN | RCC_AHB1ENR_GPIOBEN | RCC_AHB1ENR_DMA1EN;
    RCC->APB1ENR |= RCC_APB1ENR_SPI2EN;
    (void)RCC->APB1ENR;   /* read back = small delay so the clock is on */

    /* Pins: alternate function 5 = I2S2, except PB14 which is AF6 = I2S2ext. */
    gpio_af(GPIOA, 3, 5);   gpio_speed_high(GPIOA, 3);    /* MCK */
    gpio_af(GPIOB, 12, 5);  gpio_speed_high(GPIOB, 12);   /* WS  */
    gpio_af(GPIOB, 13, 5);  gpio_speed_high(GPIOB, 13);   /* CK  */
    gpio_af(GPIOB, 15, 5);  gpio_speed_high(GPIOB, 15);   /* SD  */
    gpio_af(GPIOB, 14, 6);                                /* ext SD */

    /* DAC soft-mute pin: start muted (low) so power-up doesn't pop. */
    gpio_mode(GPIOB, 9, 1);
    gpio_write(GPIOB, 9, 0);

    /* I2S2: I2S mode, master transmit, Philips, 16-bit data, 32-bit channel. */
    SPI2->I2SCFGR = SPI_I2SCFGR_I2SMOD | (2u << SPI_I2SCFGR_I2SCFG_Pos) |
                    (0u << SPI_I2SCFGR_I2SSTD_Pos) | (0u << SPI_I2SCFGR_DATLEN_Pos) |
                    SPI_I2SCFGR_CHLEN;
    /* Prescaler: MCLK out on, divider = 2*3 + 1 = 7  (86 MHz/7/256 = 47991 Hz) */
    SPI2->I2SPR = SPI_I2SPR_MCKOE | SPI_I2SPR_ODD | (3u << SPI_I2SPR_I2SDIV_Pos);

    /* I2S2ext: same format, slave receive (clocks come from I2S2 inside the chip). */
    I2S2ext->I2SCFGR = SPI_I2SCFGR_I2SMOD | (1u << SPI_I2SCFGR_I2SCFG_Pos) |
                       (0u << SPI_I2SCFGR_I2SSTD_Pos) | (0u << SPI_I2SCFGR_DATLEN_Pos) |
                       SPI_I2SCFGR_CHLEN;

    SPI2->CR2    = SPI_CR2_TXDMAEN;
    I2S2ext->CR2 = SPI_CR2_RXDMAEN;

    /* DMA1 Stream4 channel 0 = SPI2_TX: memory -> peripheral, circular. */
    DMA1_Stream4->CR = 0;
    while (DMA1_Stream4->CR & DMA_SxCR_EN) { }
    DMA1_Stream4->PAR  = (uint32_t)&SPI2->DR;
    DMA1_Stream4->M0AR = (uint32_t)tx_buf;
    DMA1_Stream4->NDTR = BUF_WORDS;
    DMA1_Stream4->CR = (0u << DMA_SxCR_CHSEL_Pos) | (2u << DMA_SxCR_PL_Pos) |
                       (1u << DMA_SxCR_MSIZE_Pos) | (1u << DMA_SxCR_PSIZE_Pos) |
                       DMA_SxCR_MINC | DMA_SxCR_CIRC | (1u << DMA_SxCR_DIR_Pos);

    /* DMA1 Stream3 channel 3 = I2S2_EXT_RX: peripheral -> memory, circular,
     * interrupts at half and full. */
    DMA1_Stream3->CR = 0;
    while (DMA1_Stream3->CR & DMA_SxCR_EN) { }
    DMA1_Stream3->PAR  = (uint32_t)&I2S2ext->DR;
    DMA1_Stream3->M0AR = (uint32_t)rx_buf;
    DMA1_Stream3->NDTR = BUF_WORDS;
    DMA1_Stream3->CR = (3u << DMA_SxCR_CHSEL_Pos) | (3u << DMA_SxCR_PL_Pos) |
                       (1u << DMA_SxCR_MSIZE_Pos) | (1u << DMA_SxCR_PSIZE_Pos) |
                       DMA_SxCR_MINC | DMA_SxCR_CIRC | (0u << DMA_SxCR_DIR_Pos) |
                       DMA_SxCR_HTIE | DMA_SxCR_TCIE;

    NVIC_SetPriority(DMA1_Stream3_IRQn, 1);
    NVIC_EnableIRQ(DMA1_Stream3_IRQn);
}

void audio_start(void)
{
    DMA1->LIFCR = 0x0F7D0F7Du;   /* clear old flags of streams 0..3 */
    DMA1->HIFCR = 0x0F7D0F7Du;   /* and 4..7 */
    DMA1_Stream3->CR |= DMA_SxCR_EN;
    DMA1_Stream4->CR |= DMA_SxCR_EN;
    /* The slave must be enabled before the master starts the clocks. */
    I2S2ext->I2SCFGR |= SPI_I2SCFGR_I2SE;
    SPI2->I2SCFGR    |= SPI_I2SCFGR_I2SE;
}

void audio_unmute(int on)
{
    gpio_write(GPIOB, 9, on);
}

static void process_half(int half)
{
    static float in[AUDIO_BLOCK], out[AUDIO_BLOCK];
    uint32_t t0 = DWT->CYCCNT;
    const volatile int16_t *rx = rx_buf + half * HALF_WORDS;
    volatile int16_t *tx = tx_buf + half * HALF_WORDS;

    /* Mono input = L + R. The board only feeds the left ADC input (right is
     * grounded), so this is just L - but it also works if the channels ever
     * come out swapped. */
    for (int i = 0; i < AUDIO_BLOCK; i++)
        in[i] = ((float)rx[2 * i] + (float)rx[2 * i + 1]) * (1.0f / 32768.0f);

    user_cb(in, out, AUDIO_BLOCK);

    for (int i = 0; i < AUDIO_BLOCK; i++) {
        float v = out[i] * 32767.0f;
        int16_t s = (int16_t)(v > 32767.0f ? 32767.0f : (v < -32768.0f ? -32768.0f : v));
        tx[2 * i] = s;       /* left  */
        tx[2 * i + 1] = s;   /* right (same) */
    }
    g_audio_cycles = DWT->CYCCNT - t0;
    g_audio_blocks++;
}

void DMA1_Stream3_IRQHandler(void)
{
    uint32_t flags = DMA1->LISR;
    if (flags & DMA_LISR_HTIF3) {        /* first half is full */
        DMA1->LIFCR = DMA_LIFCR_CHTIF3;
        process_half(0);
    }
    if (flags & DMA_LISR_TCIF3) {        /* second half is full */
        DMA1->LIFCR = DMA_LIFCR_CTCIF3;
        process_half(1);
    }
    if (flags & (DMA_LISR_TEIF3 | DMA_LISR_DMEIF3 | DMA_LISR_FEIF3))
        DMA1->LIFCR = DMA_LIFCR_CTEIF3 | DMA_LIFCR_CDMEIF3 | DMA_LIFCR_CFEIF3;
}
