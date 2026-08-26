// Native Windows AMY wire service for LB Omnichord.
// AMY remains a separate process; this executable only owns AMY/audio and
// forwards complete LF-framed wire records into the AMY C API.

#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <afunix.h>
#include <windows.h>

#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include <string.h>
#include <stdint.h>

#include "amy.h"

#define SERVICE_MAX_LINE (MAX_MESSAGE_LEN * 2)

// AMY's example helpers reference this platform hook.  The native service
// supplies it here rather than linking the standalone amy-example program.
void delay_ms(uint32_t milliseconds) {
    Sleep((DWORD)milliseconds);
}

static volatile LONG g_running = 1;
static int g_offline_render = 0;
static uint64_t g_wire_records = 0;
static uint64_t g_nonzero_samples = 0;

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
        "amy_service.exe --socket PATH [--no-audio] [--once] | --self-test\n"
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

static int run_self_test(void) {
    amy_config_t config = amy_default_config();
    config.audio = AMY_AUDIO_IS_NONE;
    config.features.default_synths = 0;
    config.max_buses = 11;
    config.max_oscs = 336;

    amy_start(config);
    amy_add_message("v0w0f440a1n69l1Z");

    uint64_t nonzero = 0;
    for (int i = 0; i < 12; ++i) nonzero += render_offline_block();

    amy_add_message("v0l0Z");
    for (int i = 0; i < 4; ++i) render_offline_block();
    amy_stop();

    if (nonzero == 0) {
        fprintf(stderr, "AMY offline render self-test produced silent PCM\n");
        return 1;
    }
    printf(
        "AMY offline render self-test passed: %llu nonzero PCM samples\n",
        (unsigned long long)nonzero
    );
    return 0;
}

static int remove_socket_if_safe(const char *path) {
    DWORD attrs = GetFileAttributesA(path);
    if (attrs == INVALID_FILE_ATTRIBUTES) return 0;
    if (attrs & FILE_ATTRIBUTE_DIRECTORY) {
        fprintf(stderr, "refusing to remove directory socket path: %s\n", path);
        return -1;
    }
    // Windows AF_UNIX creates a filesystem reparse point. DeleteFile is the
    // documented cleanup operation for that node; never overwrite a regular
    // file accidentally.
    if (!(attrs & FILE_ATTRIBUTE_REPARSE_POINT)) {
        fprintf(stderr, "refusing to remove non-socket path: %s\n", path);
        return -1;
    }
    return DeleteFileA(path) ? 0 : -1;
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

static int serve_client(SOCKET client) {
    char input[4096];
    char line[SERVICE_MAX_LINE];
    size_t used = 0;
    while (InterlockedCompareExchange(&g_running, 1, 1)) {
        int received = recv(client, input, (int)sizeof(input), 0);
        if (received == 0) return 0;
        if (received == SOCKET_ERROR) {
            int error = WSAGetLastError();
            if (error == WSAEINTR || error == WSAETIMEDOUT) continue;
            return -1;
        }
        for (int i = 0; i < received; ++i) {
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

static int run_service(const char *path, int no_audio, int once) {
    if (strlen(path) >= sizeof(((struct sockaddr_un *)0)->sun_path)) {
        fprintf(stderr, "socket path is too long for Windows AF_UNIX\n");
        return 2;
    }
    if (remove_socket_if_safe(path) < 0) return 2;

    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) return 2;
    SOCKET server = INVALID_SOCKET;
    SOCKET client = INVALID_SOCKET;
    int result = 1;
    amy_config_t config = amy_default_config();
    config.audio = no_audio ? AMY_AUDIO_IS_NONE : AMY_AUDIO_IS_MINIAUDIO;
    config.features.default_synths = 0;
    config.max_buses = 11;
    config.max_oscs = 336;
    g_offline_render = no_audio;
    g_wire_records = 0;
    g_nonzero_samples = 0;

    server = socket(AF_UNIX, SOCK_STREAM, 0);
    if (server == INVALID_SOCKET) goto cleanup;
    struct sockaddr_un address;
    memset(&address, 0, sizeof(address));
    address.sun_family = AF_UNIX;
    strcpy(address.sun_path, path);
    int address_length = (int)(offsetof(struct sockaddr_un, sun_path) +
                               strlen(path) + 1);
    if (bind(server, (const struct sockaddr *)&address, address_length) == SOCKET_ERROR)
        goto cleanup;
    if (listen(server, 1) == SOCKET_ERROR) goto cleanup;
    {
        u_long nonblocking = 1;
        if (ioctlsocket(server, FIONBIO, &nonblocking) == SOCKET_ERROR)
            goto cleanup;
    }
    if (!SetConsoleCtrlHandler(console_handler, TRUE)) goto cleanup;

    // Starting audio before publishing the socket makes connect() the
    // readiness boundary for the frontend.
    amy_start(config);
    printf("AMY service ready: %s\n", path);
    fflush(stdout);

    while (InterlockedCompareExchange(&g_running, 1, 1)) {
        client = accept(server, NULL, NULL);
        if (client == INVALID_SOCKET) {
            if (!InterlockedCompareExchange(&g_running, 1, 1)) break;
            if (WSAGetLastError() == WSAEWOULDBLOCK) {
                Sleep(50);
            }
            continue;
        }
        {
            DWORD timeout_ms = 250;
            setsockopt(client, SOL_SOCKET, SO_RCVTIMEO,
                       (const char *)&timeout_ms, sizeof(timeout_ms));
        }
        int client_result = serve_client(client);
        closesocket(client);
        client = INVALID_SOCKET;
        if (once) {
            if (client_result < 0) {
                fprintf(stderr, "AMY smoke client sent an invalid wire record\n");
                result = 1;
            } else if (g_wire_records == 0) {
                fprintf(stderr, "AMY smoke client sent no wire records\n");
                result = 1;
            } else if (no_audio && g_nonzero_samples == 0) {
                fprintf(stderr, "AMY smoke client produced silent PCM\n");
                result = 1;
            } else {
                printf(
                    "AMY service smoke passed: %llu wire commands, "
                    "%llu nonzero PCM samples\n",
                    (unsigned long long)g_wire_records,
                    (unsigned long long)g_nonzero_samples
                );
                fflush(stdout);
                result = 0;
            }
            break;
        }
    }
    if (!once) result = 0;
    amy_stop();
    SetConsoleCtrlHandler(console_handler, FALSE);

cleanup:
    if (client != INVALID_SOCKET) closesocket(client);
    if (server != INVALID_SOCKET) closesocket(server);
    remove_socket_if_safe(path);
    WSACleanup();
    return result;
}

int main(int argc, char **argv) {
    const char *path = NULL;
    int self_test = 0;
    int no_audio = 0;
    int once = 0;
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--socket") == 0 && i + 1 < argc) path = argv[++i];
        else if (strcmp(argv[i], "--self-test") == 0) self_test = 1;
        else if (strcmp(argv[i], "--no-audio") == 0) no_audio = 1;
        else if (strcmp(argv[i], "--once") == 0) once = 1;
        else { usage(); return 2; }
    }
    if (self_test) return run_self_test();
    if (path == NULL) { usage(); return 2; }
    return run_service(path, no_audio, once);
}
