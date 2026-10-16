# Firmware build. Needs the free GNU Arm toolchain (arm-none-eabi-gcc).
#   make             -> build/pedal.elf, build/pedal.bin, build/pedal.hex
#   make flash-dfu   -> flash over USB with dfu-util (Black Pill in DFU mode)
#   make flash-stlink-> flash with an ST-Link and st-flash
#   make test        -> run the DSP tests on your PC (host/)

TARGET  = pedal
BUILD   = build
CC      = arm-none-eabi-gcc
OBJCOPY = arm-none-eabi-objcopy
SIZE    = arm-none-eabi-size

SRCS = src/startup.c src/clock.c src/audio_io.c src/controls.c src/uart.c src/main.c \
       dsp/effects.c

CPU    = -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard
CFLAGS = $(CPU) -std=c99 -O2 -g -Wall -Wextra -ffunction-sections -fdata-sections \
         -fsingle-precision-constant -DSTM32F411xE -Icmsis -Isrc
LDFLAGS = $(CPU) -T STM32F411CEUx.ld -nostartfiles --specs=nano.specs --specs=nosys.specs \
          -Wl,--gc-sections -Wl,-Map=$(BUILD)/$(TARGET).map -lm

OBJS = $(SRCS:%.c=$(BUILD)/%.o)

all: $(BUILD)/$(TARGET).bin $(BUILD)/$(TARGET).hex
	$(SIZE) $(BUILD)/$(TARGET).elf

$(BUILD)/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/$(TARGET).elf: $(OBJS) STM32F411CEUx.ld
	$(CC) $(OBJS) $(LDFLAGS) -o $@

$(BUILD)/$(TARGET).bin: $(BUILD)/$(TARGET).elf
	$(OBJCOPY) -O binary $< $@

$(BUILD)/$(TARGET).hex: $(BUILD)/$(TARGET).elf
	$(OBJCOPY) -O ihex $< $@

flash-dfu: $(BUILD)/$(TARGET).bin
	dfu-util -a 0 -s 0x08000000:leave -D $<

flash-stlink: $(BUILD)/$(TARGET).bin
	st-flash --reset write $< 0x08000000

test:
	$(MAKE) -C host

clean:
	rm -rf $(BUILD)

.PHONY: all flash-dfu flash-stlink test clean
