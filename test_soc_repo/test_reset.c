// test_reset.c — Software validation test for reset controller
#include <stdint.h>
#include <stdbool.h>

#define RESET_CTRL_BASE 0x40000000
#define SW_RST_REQ_OFFSET 0x04

static volatile uint32_t *const SW_RST_REG = (uint32_t *)(RESET_CTRL_BASE + SW_RST_REQ_OFFSET);

bool trigger_software_reset(void) {
    // Assert software reset request
    *SW_RST_REG = 0x1;
    for (volatile int i = 0; i < 100; i++) {
        __asm__ volatile("nop");
    }
    return true;
}

int main(void) {
    return trigger_software_reset() ? 0 : 1;
}
