#include "reverb_pie_bench.h"

#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "esp_heap_caps.h"
#include "esp_timer.h"

#define MATRIX_SAMPLES 512
#define MATRIX_VECTORS 4
#define BENCH_REPEATS 2000

void amy_reverb_hadamard4x32_pie(int32_t *values, uint32_t groups);

__attribute__((noinline))
static void scalar_hadamard4x32(int32_t *values, uint32_t samples)
{
    int32_t *d1 = values;
    int32_t *d2 = d1 + samples;
    int32_t *d3 = d2 + samples;
    int32_t *d4 = d3 + samples;
    for (uint32_t i = 0; i < samples; ++i) {
        int32_t a = d1[i] + d2[i];
        int32_t b = d1[i] - d2[i];
        int32_t c = d3[i] + d4[i];
        int32_t d = d3[i] - d4[i];
        d1[i] = a + c;
        d2[i] = b + d;
        d3[i] = a - c;
        d4[i] = b - d;
    }
}

static uint32_t checksum32(const int32_t *values, size_t count)
{
    uint32_t sum = 0;
    for (size_t i = 0; i < count; ++i) sum = sum * 33u + (uint32_t)values[i];
    return sum;
}

void reverb_pie_bench_run(void)
{
    const size_t words = MATRIX_SAMPLES * MATRIX_VECTORS;
    const size_t bytes = words * sizeof(int32_t);
    int32_t *input = heap_caps_aligned_alloc(
        16, bytes, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    int32_t *scalar = heap_caps_aligned_alloc(
        16, bytes, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    int32_t *pie = heap_caps_aligned_alloc(
        16, bytes, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    if (!input || !scalar || !pie) {
        printf("PIE reverb benchmark: allocation failed\n");
        goto done;
    }

    for (size_t i = 0; i < words; ++i)
        input[i] = (int32_t)((i * 7919u) % 200001u) - 100000;
    memcpy(scalar, input, bytes);
    memcpy(pie, input, bytes);
    scalar_hadamard4x32(scalar, MATRIX_SAMPLES);
    amy_reverb_hadamard4x32_pie(pie, MATRIX_SAMPLES / 4);
    bool exact = memcmp(scalar, pie, bytes) == 0;

    int64_t start = esp_timer_get_time();
    for (int repeat = 0; repeat < BENCH_REPEATS; ++repeat) {
        memcpy(scalar, input, bytes);
        scalar_hadamard4x32(scalar, MATRIX_SAMPLES);
    }
    int64_t scalar_us = esp_timer_get_time() - start;
    start = esp_timer_get_time();
    for (int repeat = 0; repeat < BENCH_REPEATS; ++repeat) {
        memcpy(pie, input, bytes);
        amy_reverb_hadamard4x32_pie(pie, MATRIX_SAMPLES / 4);
    }
    int64_t pie_us = esp_timer_get_time() - start;

    printf("PIE Q8.23 reverb matrix (%d repeats):\n", BENCH_REPEATS);
    printf("  scalar=%" PRId64 " us PIE=%" PRId64
           " us speedup=%.2fx exact=%s checksum=%08" PRIx32 "\n",
           scalar_us, pie_us, (double)scalar_us / (double)pie_us,
           exact ? "yes" : "NO", checksum32(pie, words));

done:
    free(input);
    free(scalar);
    free(pie);
}
