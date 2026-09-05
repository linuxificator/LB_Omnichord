// Native Windows AMY wire service for LB Omnichord.
// AMY remains a separate process; this executable only owns AMY/audio and
// forwards complete LF-framed named-pipe records into the AMY C API.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include "amy.h"

#ifdef GAMMA9001
extern const int16_t gamma9001_pcm_data[];
#endif

#define SERVICE_MAX_LINE MAX_MESSAGE_LEN
#define SERVICE_PIPE_PATH 256

// AMY's example helpers reference this platform hook.  The native service
// supplies it here rather than linking the standalone amy-example program.
void delay_ms(uint32_t milliseconds) {
    Sleep((DWORD)milliseconds);
}

static volatile LONG g_running = 1;
static int g_offline_render = 0;
static uint64_t g_wire_records = 0;
static uint64_t g_nonzero_samples = 0;

static void configure_pcm_bank(void) {
#ifdef GAMMA9001
    amy_set_gamma9001_pcm(gamma9001_pcm_data);
#endif
}

static BOOL WINAPI console_handler(DWORD type) {
    if (type == CTRL_C_EVENT || type == CTRL_BREAK_EVENT ||
        type == CTRL_CLOSE_EVENT || type == CTRL_SHUTDOWN_EVENT) {
        InterlockedExchange(&g_running, 0);
        return TRUE;
    }
    return FALSE;
}

static void usage(void) {
    printf(
        "amy_service.exe --pipe-name NAME --ready-file PATH "
        "[--no-audio] [--once]\n"
    );
}

static uint64_t render_offline_block(void) {
    int16_t *block = amy_simple_fill_buffer();
    uint64_t nonzero = 0;
    for (size_t i = 0; i < (size_t)AMY_BLOCK_SIZE * AMY_NCHANS; ++i) {
        if (block[i] != 0) ++nonzero;
    }
    return nonzero;
}

static int publish_ready_file(const char *path, const char *pipe_name) {
    FILE *file = fopen(path, "w");
    if (file == NULL) {
        fprintf(stderr, "cannot publish AMY service pipe: %s\n", path);
        return -1;
    }
    fprintf(file, "%s\n", pipe_name);
    if (fclose(file) != 0) {
        fprintf(stderr, "cannot close AMY service ready file: %s\n", path);
        return -1;
    }
    return 0;
}

static int send_wire_line(char *line, size_t length) {
    while (length > 0 && (line[length - 1] == '\r' || line[length - 1] == '\n'))
        --length;
    if (length == 0) return 0;
    if (length >= MAX_MESSAGE_LEN || line[length - 1] != 'Z') return -1;
    line[length] = '\0';
    amy_add_message(line);
    ++g_wire_records;
    if (g_offline_render) {
        g_nonzero_samples += render_offline_block();
    }
    return 0;
}

static int serve_client(HANDLE pipe) {
    char input[4096];
    char line[SERVICE_MAX_LINE];
    size_t used = 0;
    while (InterlockedCompareExchange(&g_running, 1, 1)) {
        DWORD received = 0;
        if (!ReadFile(pipe, input, sizeof(input), &received, NULL)) {
            DWORD error = GetLastError();
            if (error == ERROR_BROKEN_PIPE) return used == 0 ? 0 : -1;
            if (error == ERROR_OPERATION_ABORTED &&
                !InterlockedCompareExchange(&g_running, 1, 1)) {
                return 0;
            }
            fprintf(
                stderr,
                "AMY named-pipe read failed: %lu\n",
                (unsigned long)error
            );
            return -1;
        }
        if (received == 0) continue;
        for (DWORD i = 0; i < received; ++i) {
            unsigned char byte = (unsigned char)input[i];
            if (byte == '\n') {
                if (send_wire_line(line, used) < 0) return -1;
                used = 0;
                continue;
            }
            if (used + 1 >= sizeof(line)) {
                fprintf(stderr, "AMY wire record exceeds maximum length\n");
                return -1;
            }
            line[used++] = (char)byte;
        }
    }
    return 0;
}

static int run_service(
    const char *pipe_name,
    const char *ready_file,
    int no_audio,
    int once
) {
    DeleteFileA(ready_file);
    char pipe_path[SERVICE_PIPE_PATH];
    HANDLE pipe = INVALID_HANDLE_VALUE;
    int result = 1;
    amy_config_t config = amy_default_config();
    config.audio = no_audio ? AMY_AUDIO_IS_NONE : AMY_AUDIO_IS_MINIAUDIO;
    config.features.default_synths = 0;
    config.max_buses = 11;
    config.max_oscs = 336;
    config.max_sequencer_tags = 1280;
    config.max_sequence_events = 64;
    config.max_sequence_executions = 40;
    g_offline_render = no_audio;
    g_wire_records = 0;
    g_nonzero_samples = 0;

    int pipe_path_length = snprintf(
            pipe_path,
            sizeof(pipe_path),
            "\\\\.\\pipe\\%s",
            pipe_name
        );
    if (pipe_name[0] == '\0' || pipe_path_length < 0 ||
        (size_t)pipe_path_length >= sizeof(pipe_path)) {
        fprintf(stderr, "invalid AMY named-pipe name\n");
        goto cleanup;
    }
    pipe = CreateNamedPipeA(
        pipe_path,
        PIPE_ACCESS_DUPLEX,
        PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT |
            PIPE_REJECT_REMOTE_CLIENTS,
        1,
        4096,
        4096,
        0,
        NULL
    );
    if (pipe == INVALID_HANDLE_VALUE) {
        fprintf(
            stderr,
            "cannot create AMY named pipe: %lu\n",
            (unsigned long)GetLastError()
        );
        goto cleanup;
    }
    if (!SetConsoleCtrlHandler(console_handler, TRUE)) goto cleanup;

    // Publish readiness only after both the local pipe and AMY exist.
    configure_pcm_bank();
    amy_start(config);
    if (publish_ready_file(ready_file, pipe_name) < 0) {
        amy_stop();
        SetConsoleCtrlHandler(console_handler, FALSE);
        goto cleanup;
    }
    printf("AMY service ready: named pipe %s\n", pipe_name);
    fflush(stdout);

    {
        BOOL connected = ConnectNamedPipe(pipe, NULL);
        if (!connected && GetLastError() != ERROR_PIPE_CONNECTED) {
            fprintf(
                stderr,
                "AMY named-pipe connect failed: %lu\n",
                (unsigned long)GetLastError()
            );
            goto service_cleanup;
        }
    }
    {
        int client_result = serve_client(pipe);
        if (client_result < 0) {
            fprintf(stderr, "AMY client sent an invalid wire record\n");
            result = 1;
        } else if (once) {
            printf(
                "AMY service session completed: %llu wire commands, "
                "%llu nonzero PCM samples\n",
                (unsigned long long)g_wire_records,
                (unsigned long long)g_nonzero_samples
            );
            fflush(stdout);
            result = 0;
        } else {
            result = 0;
        }
    }

service_cleanup:
    FlushFileBuffers(pipe);
    DisconnectNamedPipe(pipe);
    amy_stop();
    SetConsoleCtrlHandler(console_handler, FALSE);

cleanup:
    if (pipe != INVALID_HANDLE_VALUE) CloseHandle(pipe);
    DeleteFileA(ready_file);
    return result;
}

int main(int argc, char **argv) {
    const char *pipe_name = NULL;
    const char *ready_file = NULL;
    int no_audio = 0;
    int once = 0;
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--pipe-name") == 0 && i + 1 < argc)
            pipe_name = argv[++i];
        else if (strcmp(argv[i], "--ready-file") == 0 && i + 1 < argc)
            ready_file = argv[++i];
        else if (strcmp(argv[i], "--no-audio") == 0) no_audio = 1;
        else if (strcmp(argv[i], "--once") == 0) once = 1;
        else { usage(); return 2; }
    }
    if (pipe_name == NULL || ready_file == NULL) { usage(); return 2; }
    return run_service(pipe_name, ready_file, no_audio, once);
}
