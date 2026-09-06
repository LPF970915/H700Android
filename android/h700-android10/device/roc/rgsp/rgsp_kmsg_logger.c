#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t stopping;

static void stop_logger(int signal_number) {
    (void)signal_number;
    stopping = 1;
}

static int open_log(const char *path, size_t *size) {
    int fd = open(path, O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC | O_NOFOLLOW, 0600);
    struct stat st;
    if (fd < 0) return -1;
    if (fstat(fd, &st) || !S_ISREG(st.st_mode)) {
        close(fd);
        errno = EINVAL;
        return -1;
    }
    *size = (size_t)st.st_size;
    return fd;
}

static int rotate_log(const char *path, int fd, size_t *size) {
    char from[PATH_MAX], to[PATH_MAX];
    int error = fsync(fd);
    if (close(fd)) error = -1;
    if (error) return -1;
    for (int index = 3; index > 0; --index) {
        if (index == 1) snprintf(from, sizeof(from), "%s", path);
        else snprintf(from, sizeof(from), "%s.%d", path, index - 1);
        snprintf(to, sizeof(to), "%s.%d", path, index);
        if (rename(from, to) && errno != ENOENT) return -1;
    }
    return open_log(path, size);
}

int main(int argc, char **argv) {
    if (argc < 2 || argc > 4 || strlen(argv[1]) > PATH_MAX - 16) {
        fprintf(stderr, "usage: rgsp_kmsg_logger LOG [BYTES [--stdin]]\n");
        return 2;
    }
    char *end = NULL;
    unsigned long limit = 1048576;
    if (argc >= 3) {
        errno = 0;
        limit = strtoul(argv[2], &end, 10);
        if (errno || end == argv[2] || *end || limit < 16 || limit > 16777216)
            return 2;
    }
    if (argc == 4 && strcmp(argv[3], "--stdin")) return 2;
    char lock_path[PATH_MAX];
    snprintf(lock_path, sizeof(lock_path), "%s.lock", argv[1]);
    int lock_fd = open(lock_path, O_WRONLY | O_CREAT | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (lock_fd < 0 || flock(lock_fd, LOCK_EX | LOCK_NB)) {
        perror("logger lock");
        return 1;
    }
    int input = argc == 4 ? STDIN_FILENO : open("/dev/kmsg", O_RDONLY | O_CLOEXEC);
    if (input < 0) { perror("kmsg open"); return 1; }
    size_t size = 0;
    int output = open_log(argv[1], &size);
    if (output < 0) { perror("log open"); return 1; }
    struct sigaction action = {.sa_handler = stop_logger};
    sigemptyset(&action.sa_mask);
    sigaction(SIGTERM, &action, NULL);
    sigaction(SIGINT, &action, NULL);
    char buffer[65536];
    struct pollfd ready = {.fd = input, .events = POLLIN};
    struct timespec last_sync;
    clock_gettime(CLOCK_MONOTONIC, &last_sync);
    int result = 0;
    while (!stopping) {
        int event = poll(&ready, 1, 1000);
        if (event < 0 && errno != EINTR) { result = 1; break; }
        if (event > 0) {
            if (ready.revents & POLLNVAL) { result = 1; break; }
            ssize_t received = read(input, buffer, sizeof(buffer));
            if (received < 0) {
                // /dev/kmsg reports overwritten records with EPIPE, then resumes.
                if (errno == EINTR || errno == EPIPE || errno == EAGAIN) continue;
                perror("kmsg read");
                result = 1;
                break;
            }
            if (!received) break;
            size_t offset = 0;
            while (offset < (size_t)received) {
                if (size >= limit) {
                    output = rotate_log(argv[1], output, &size);
                    if (output < 0) { perror("log rotate"); return 1; }
                }
                size_t count = (size_t)received - offset;
                if (count > limit - size) count = limit - size;
                ssize_t written = write(output, buffer + offset, count);
                if (written < 0 && errno == EINTR) continue;
                if (written <= 0) { perror("log write"); result = 1; goto done; }
                offset += (size_t)written;
                size += (size_t)written;
            }
        }
        struct timespec now;
        clock_gettime(CLOCK_MONOTONIC, &now);
        if (now.tv_sec - last_sync.tv_sec >= 5) {
            if (fsync(output)) { perror("log sync"); result = 1; break; }
            last_sync = now;
        }
    }
done:
    if (fsync(output)) result = 1;
    if (close(output)) result = 1;
    close(lock_fd);
    if (input != STDIN_FILENO) close(input);
    return result;
}
