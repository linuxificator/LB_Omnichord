#pragma once

/*
 * UI-P4 -> AMY-P4 serial link.
 */
#define AMY_UART_BAUD              1000000
#define AMY_UART_RX_GPIO           15

/*
 * Shared LP-RAM message ring.
 *
 * 8 x 1024 bytes = 8192 bytes.
 *
 * AMY itself currently defines MAX_MESSAGE_LEN as 1024.
 */
#define AMY_UART_RING_SLOTS        8
#define AMY_UART_MSG_MAX           1024

/*
 * LP globals are uint32_t-visible from the HP side, so pack
 * four UART bytes into each shared uint32_t word.
 */
#define AMY_UART_WORDS_PER_SLOT    (AMY_UART_MSG_MAX / 4)
#define AMY_UART_TOTAL_WORDS       \
    (AMY_UART_RING_SLOTS * AMY_UART_WORDS_PER_SLOT)
