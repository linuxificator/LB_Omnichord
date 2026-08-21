#include <stdint.h>
#include <stdbool.h>

#include "esp_err.h"

#include "ulp_lp_core_uart.h"
#include "ulp_lp_core_mailbox.h"

#include "amy_uart_shared.h"


#define LP_UART_PORT       LP_UART_NUM_0

/*
 * Short polling timeout.
 *
 * This is in LP-CPU cycles, not FreeRTOS ticks.
 * At 40 MHz, 1000 cycles = 25 us.
 */
#define UART_READ_TIMEOUT_CYCLES  1000


/*
 * --------------------------------------------------------------------
 * Shared LP -> HP ring
 * --------------------------------------------------------------------
 *
 * These MUST NOT be static.
 *
 * ESP-IDF generates HP-visible symbols:
 *
 *   amy_rx_words      -> ulp_amy_rx_words
 *   amy_rx_len        -> ulp_amy_rx_len
 *   amy_rx_write_seq  -> ulp_amy_rx_write_seq
 *   amy_rx_read_seq   -> ulp_amy_rx_read_seq
 *   ...
 */

volatile uint32_t amy_rx_words[AMY_UART_TOTAL_WORDS];
volatile uint32_t amy_rx_len[AMY_UART_RING_SLOTS];

volatile uint32_t amy_rx_write_seq = 0;
volatile uint32_t amy_rx_read_seq  = 0;

volatile uint32_t amy_rx_commands       = 0;
volatile uint32_t amy_rx_ring_overflow  = 0;
volatile uint32_t amy_rx_too_long       = 0;
volatile uint32_t amy_rx_bad_frame      = 0;
volatile uint32_t amy_rx_mailbox_errors = 0;

volatile uint32_t amy_rx_ready = 0;


static lp_mailbox_t mailbox;


/*
 * Both the HP and LP CPUs are RISC-V.
 *
 * Make sure all shared-memory writes have completed before
 * publishing the new write sequence / mailbox notification.
 */
static inline void shared_memory_barrier(void)
{
    __asm__ __volatile__(
        "fence rw, rw"
        :
        :
        : "memory"
    );
}


/*
 * Store one byte into the packed uint32_t LP-RAM ring.
 */
static inline void store_byte(
    uint32_t slot,
    uint32_t pos,
    uint8_t value)
{
    const uint32_t word_index =
        slot * AMY_UART_WORDS_PER_SLOT +
        (pos >> 2);

    const uint32_t shift =
        (pos & 3U) * 8U;

    const uint32_t mask =
        0xffU << shift;

    uint32_t word =
        amy_rx_words[word_index];

    word &= ~mask;
    word |= ((uint32_t)value << shift);

    amy_rx_words[word_index] = word;
}


/*
 * Publish one completed AMY command to the HP side.
 */
static void publish_message(
    uint32_t slot,
    uint32_t length)
{
    amy_rx_len[slot] = length;

    /*
     * Payload + length must be globally visible before
     * write_seq says the slot exists.
     */
    shared_memory_barrier();

    amy_rx_write_seq++;
    amy_rx_commands++;

    shared_memory_barrier();


    /*
     * Synchronous LP mailbox send:
     *
     * On the P4 the HP mailbox ISR acknowledges this.
     * The HP callback itself only wakes the command task;
     * parsing AMY is NOT done from interrupt context.
     */
    esp_err_t ret =
        lp_core_mailbox_send(
            mailbox,
            (lp_message_t)slot,
            -1
        );

    if (ret != ESP_OK) {
        amy_rx_mailbox_errors++;
    }
}


int main(void)
{
    /*
     * Initialize the LP-side mailbox first.
     */
    if (lp_core_mailbox_init(
            &mailbox,
            NULL) != ESP_OK) {

        /*
         * Fatal initialization error.
         */
        while (1) {
        }
    }


    /*
     * Tell the HP CPU that the LP program and mailbox
     * are ready.
     */
    shared_memory_barrier();
    amy_rx_ready = 1;
    shared_memory_barrier();


    uint8_t rx[16];

    uint32_t message_length = 0;
    uint32_t current_slot = 0;

    uint8_t last_byte = 0;

    bool dropping = false;


    while (1) {

        /*
         * Read whatever is currently available from the
         * LP UART FIFO.
         *
         * The API timeout is expressed in LP CPU cycles.
         */
        int received =
            lp_core_uart_read_bytes(
                LP_UART_PORT,
                rx,
                sizeof(rx),
                UART_READ_TIMEOUT_CYCLES
            );

        if (received <= 0) {
            continue;
        }


        for (int i = 0; i < received; i++) {

            const uint8_t c = rx[i];


            /*
             * Accept CRLF senders too.
             */
            if (c == '\r') {
                continue;
            }


            /*
             * LF is the transport frame boundary.
             *
             * The actual AMY payload must itself end in Z.
             */
            if (c == '\n') {

                if (!dropping &&
                    message_length > 0) {

                    if (last_byte == 'Z') {

                        publish_message(
                            current_slot,
                            message_length
                        );

                    } else {

                        /*
                         * A complete transport frame that
                         * isn't a complete AMY command.
                         */
                        amy_rx_bad_frame++;
                    }
                }


                /*
                 * Begin a fresh frame.
                 */
                message_length = 0;
                last_byte = 0;
                dropping = false;

                continue;
            }


            /*
             * First byte of a new message:
             * reserve the next ring slot.
             */
            if (message_length == 0 &&
                !dropping) {

                uint32_t used =
                    amy_rx_write_seq -
                    amy_rx_read_seq;

                if (used >=
                    AMY_UART_RING_SLOTS) {

                    /*
                     * HP side isn't consuming quickly enough.
                     *
                     * Continue reading UART data so the
                     * hardware FIFO doesn't overflow, but
                     * discard this entire frame.
                     */
                    amy_rx_ring_overflow++;
                    dropping = true;
                    continue;
                }

                current_slot =
                    amy_rx_write_seq %
                    AMY_UART_RING_SLOTS;
            }


            if (dropping) {
                continue;
            }


            /*
             * Reserve one byte for the maximum-length limit.
             *
             * No NUL is stored in LP RAM; HP adds it after
             * unpacking the command.
             */
            if (message_length >=
                AMY_UART_MSG_MAX) {

                amy_rx_too_long++;
                dropping = true;
                continue;
            }


            store_byte(
                current_slot,
                message_length,
                c
            );

            message_length++;
            last_byte = c;
        }
    }


    return 0;
}
