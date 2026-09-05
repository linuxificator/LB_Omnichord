#include <stdio.h>
#include <stdint.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "esp_err.h"

#include "ulp_lp_core.h"
#include "lp_core_uart.h"
#include "lp_core_mailbox.h"

#include "amy.h"

/*
 * Automatically generated from the LP-core binary.
 */
#include "lp_core_main.h"

#include "lp_core/amy_uart_shared.h"


/*
 * LP binary embedded by ulp_embed_binary().
 */
extern const uint8_t lp_core_main_bin_start[]
    asm("_binary_lp_core_main_bin_start");

extern const uint8_t lp_core_main_bin_end[]
    asm("_binary_lp_core_main_bin_end");


static lp_mailbox_t s_mailbox;

static TaskHandle_t s_amy_command_task = NULL;


/*
 * Use one priority below AMY's core-0 render task.
 *
 * AMY render:
 *     ESP_TASK_PRIO_MAX - 1
 *
 * UART command forwarder:
 *     ESP_TASK_PRIO_MAX - 2
 */
#define AMY_COMMAND_TASK_PRIORITY \
    (AMY_RENDER_TASK_PRIORITY - 1)

#define AMY_COMMAND_TASK_STACK ( 16 * 4096 )

#define AMY_COMMAND_TASK_CORE      0


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
 * Unpack one LP-ring slot into a normal HP char buffer.
 */
static uint32_t copy_lp_message(
    uint32_t slot,
    char *dest,
    uint32_t dest_size)
{
    if (slot >= AMY_UART_RING_SLOTS) {
        return 0;
    }

    shared_memory_barrier();

    uint32_t len =
        ulp_amy_rx_len[slot];

    if (len == 0 ||
        len >= dest_size ||
        len > AMY_UART_MSG_MAX) {

        return 0;
    }


    for (uint32_t i = 0; i < len; i++) {

        const uint32_t word_index =
            slot * AMY_UART_WORDS_PER_SLOT +
            (i >> 2);

        const uint32_t shift =
            (i & 3U) * 8U;

        uint32_t word =
            ulp_amy_rx_words[word_index];

        dest[i] =
            (char)((word >> shift) & 0xffU);
    }


    dest[len] = '\0';

    return len;
}


/*
 * This runs in HP mailbox ISR context.
 *
 * Do as little as possible here:
 * just wake the command forwarding task.
 *
 * The ESP-IDF mailbox driver has already acknowledged the
 * LP message before invoking this callback.
 */
static void lp_mailbox_callback(
    lp_message_t msg)
{
    (void)msg;

    BaseType_t task_woken = pdFALSE;

    vTaskNotifyGiveFromISR(
        s_amy_command_task,
        &task_woken
    );

    if (task_woken != pdFALSE) {
        portYIELD_FROM_ISR();
    }
}


/*
 * HP command forwarding task.
 *
 * Pinned to core 0, below AMY's core-0 render task.
 *
 * When AMY starts rendering, AMY preempts us.
 */
static void amy_command_task(void *arg)
{
    (void)arg;

    char command[
        AMY_UART_MSG_MAX + 1
    ];


    while (1) {

        /*
         * Sleep until LP mailbox interrupt says there is
         * at least one complete command.
         */
        ulTaskNotifyTake(
            pdTRUE,
            portMAX_DELAY
        );


        /*
         * One notification can represent several queued
         * messages, so drain the complete shared ring.
         */
        while (ulp_amy_rx_read_seq !=
               ulp_amy_rx_write_seq) {

            const uint32_t read_seq =
                ulp_amy_rx_read_seq;

            const uint32_t slot =
                read_seq %
                AMY_UART_RING_SLOTS;


            uint32_t len =
                copy_lp_message(
                    slot,
                    command,
                    sizeof(command)
                );


            /*
             * The command is now safely copied into HP
             * stack memory, so release the LP ring slot
             * immediately.
             */
            shared_memory_barrier();

            ulp_amy_rx_read_seq =
                read_seq + 1;

            shared_memory_barrier();


            if (len == 0) {
                continue;
            }


            /*
             * Native AMY wire command.
             *
             * Example:
             *
             *   v0w0f440Q0l0.2Z
             */
            amy_add_message(command);
        }
    }
}


/*
 * Initialize RX-only LP UART.
 */
static void init_lp_uart(void)
{
    lp_core_uart_cfg_t cfg =
        LP_CORE_UART_DEFAULT_CONFIG();


    /*
     * RX only.
     */
    cfg.uart_pin_cfg.tx_io_num = -1;
    cfg.uart_pin_cfg.rx_io_num =
        GPIO_NUM_15;


    cfg.uart_proto_cfg.baud_rate =
        AMY_UART_BAUD;


    /*
     * Use XTAL/2 rather than the default RC oscillator.
     *
     * ESP32-P4:
     *     XTAL     = 40 MHz
     *     XTAL_D2  = 20 MHz
     *
     * 1 Mbaud divides exactly from 20 MHz.
     */
    cfg.lp_uart_source_clk =
        LP_UART_SCLK_XTAL_D2;


    ESP_ERROR_CHECK(
        lp_core_uart_init(&cfg)
    );


    printf(
        "LP UART: RX GPIO15, %d baud, 8N1\n",
        AMY_UART_BAUD
    );
}


/*
 * Load and start the LP-core firmware.
 */
static void start_lp_core(void)
{
    ulp_lp_core_cfg_t cfg = {
        .wakeup_source =
            ULP_LP_CORE_WAKEUP_SOURCE_HP_CPU,
    };


    ESP_ERROR_CHECK(
        ulp_lp_core_load_binary(
            lp_core_main_bin_start,
            lp_core_main_bin_end -
            lp_core_main_bin_start
        )
    );


    ESP_ERROR_CHECK(
        ulp_lp_core_run(&cfg)
    );


    /*
     * Wait until the LP program has initialized its side
     * of the mailbox.
     *
     * This is startup-only, so the coarse RTOS tick is
     * irrelevant here.
     */
    for (int i = 0;
         i < 100 &&
         ulp_amy_rx_ready == 0;
         i++) {

        vTaskDelay(1);
    }


    if (ulp_amy_rx_ready == 0) {
        printf(
            "ERROR: LP core did not become ready\n"
        );

        abort();
    }


    printf("LP core UART receiver running\n");
}


void app_main(void)
{
    printf("\n");
    printf(
        "========================================\n"
    );
    printf(
        " AMY P4 - LP UART command receiver\n"
    );
    printf(
        "========================================\n"
    );

    printf(
        "AMY sample rate : %d Hz\n",
        AMY_SAMPLE_RATE
    );

    printf(
        "AMY block size  : %d samples\n",
        AMY_BLOCK_SIZE
    );


    /*
     * ----------------------------------------------------
     * Start AMY first.
     * ----------------------------------------------------
     *
     * This guarantees that no UART command can reach
     * amy_add_message() before the synth is initialized.
     */

    amy_config_t config =
        amy_default_config();

    config.platform.multicore = 1;
    config.platform.multithread = 1;

    config.audio =
        AMY_AUDIO_IS_I2S;

    config.midi =
        AMY_MIDI_IS_NONE;

    config.features.audio_in = 0;
    config.features.startup_bleep = 0;

    /*
     * Physical Strings uses AMY's Karplus-Strong oscillator.  Upstream AMY
     * defaults to a single KS delay buffer; reserve enough for all melodic
     * Omnichord roles (1 bass + 2 strum + 7 manual chord + 4 rhythm chord),
     * with two spare buffers for future voice-layout changes.
     */
    config.ks_oscs = 16;
    config.max_sequencer_tags = 1280;
    config.max_sequence_events = 64;
    config.max_sequence_executions = 40;


    /*
     * PCM5102A
     *
     * GPIO16 -> LRCK
     * GPIO17 -> DIN
     * GPIO18 -> BCK
     */
    config.i2s_lrc  = 16;
    config.i2s_dout = 17;
    config.i2s_bclk = 18;

    config.i2s_din  = -1;
    config.i2s_mclk = -1;


    printf("Starting AMY...\n");

    amy_start(config);

    printf("AMY running\n");


    /*
     * ----------------------------------------------------
     * Configure LP UART and start LP core.
     * ----------------------------------------------------
     */

    init_lp_uart();

    start_lp_core();


    /*
     * Initialize HP side of mailbox.
     *
     * ESP32-P4 has a hardware LP mailbox. ESP-IDF's
     * mailbox driver installs an HP interrupt for it.
     */
    ESP_ERROR_CHECK(
        lp_core_mailbox_init(
            &s_mailbox,
            NULL
        )
    );


    /*
     * Create the normal HP task that will actually call AMY.
     *
     * Pin it to core 0, one priority below AMY's render
     * task.
     */
    BaseType_t created =
        xTaskCreatePinnedToCore(
            amy_command_task,
            "amy_uart_cmd",
            AMY_COMMAND_TASK_STACK,
            NULL,
            AMY_COMMAND_TASK_PRIORITY,
            &s_amy_command_task,
            AMY_COMMAND_TASK_CORE
        );

    if (created != pdPASS) {
        printf(
            "ERROR: couldn't create AMY UART task\n"
        );

        abort();
    }


    /*
     * Receive effectively indefinitely.
     *
     * Callback runs in ISR context, acknowledges the LP
     * mailbox message, then wakes amy_command_task().
     */
    ESP_ERROR_CHECK(
        lp_core_mailbox_receive_async(
            s_mailbox,
            UINT32_MAX,
            lp_mailbox_callback
        )
    );


    printf("\n");
    printf(
        "Ready for AMY commands on GPIO15\n"
    );
    printf(
        "Format: native AMY command + LF\n"
    );
    printf(
        "Example: v0w0f440Q0l0.2Z\\n\n"
    );


    /*
     * app_main can return.
     *
     * AMY tasks, LP core and amy_command_task continue.
     */
}
