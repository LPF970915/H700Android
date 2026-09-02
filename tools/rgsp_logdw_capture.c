#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

static int write_all(int fd, const void *data, size_t size) {
    const unsigned char *cursor = data;
    while (size > 0) {
        ssize_t written = write(fd, cursor, size);
        if (written < 0) {
            if (errno == EINTR) {
                continue;
            }
            return -1;
        }
        cursor += written;
        size -= (size_t)written;
    }
    return 0;
}

int main(int argc, char **argv) {
    const char *socket_value = getenv("ANDROID_SOCKET_logdw");
    const char *output_path = argc > 1
        ? argv[1]
        : "/rgsp-persist/RGSP_ANDROID_LOGDW_LAST.log";
    unsigned char packet[65536];
    char printable[65536];
    char prefix[96];
    int socket_fd;
    int output_fd;

    if (socket_value == NULL || *socket_value == '\0') {
        return 2;
    }
    socket_fd = atoi(socket_value);
    if (socket_fd < 0) {
        return 3;
    }

    output_fd = open(output_path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0666);
    if (output_fd < 0) {
        return 4;
    }
    static const char start_message[] = "[rgsp-logdw] capture started\n";

    write_all(output_fd, start_message, sizeof(start_message) - 1);
    fsync(output_fd);

    signal(SIGPIPE, SIG_IGN);
    for (;;) {
        struct timespec now;
        ssize_t size = recv(socket_fd, packet, sizeof(packet), 0);
        size_t output_size = 0;
        int prefix_size;

        if (size < 0) {
            if (errno == EINTR) {
                continue;
            }
            break;
        }

        clock_gettime(CLOCK_MONOTONIC, &now);
        prefix_size = snprintf(prefix, sizeof(prefix), "[%lld.%09ld] ",
            (long long)now.tv_sec, now.tv_nsec);
        if (prefix_size > 0) {
            write_all(output_fd, prefix, (size_t)prefix_size);
        }

        for (ssize_t i = 0; i < size && output_size + 1 < sizeof(printable); ++i) {
            unsigned char value = packet[i];
            if (value == '\0') {
                printable[output_size++] = '|';
            } else if (value == '\n' || value == '\r' || value == '\t' ||
                       (value >= 0x20 && value <= 0x7e)) {
                printable[output_size++] = (char)value;
            } else {
                printable[output_size++] = '.';
            }
        }
        printable[output_size++] = '\n';
        write_all(output_fd, printable, output_size);
        fsync(output_fd);
    }

    close(output_fd);
    return 5;
}
