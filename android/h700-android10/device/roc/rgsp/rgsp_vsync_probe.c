#include <errno.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <linux/netlink.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

static int64_t monotonic_ns(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (int64_t)t.tv_sec * 1000000000 + t.tv_nsec;
}

int main(void) {
    setvbuf(stdout, NULL, _IOLBF, 0);
    int fb = open("/dev/graphics/fb0", O_RDWR | O_CLOEXEC);
    if (fb < 0) { perror("open fb0"); return 1; }
    uint32_t crtc = 0;
    int64_t start = monotonic_ns(), previous = start;
    for (int i = 0; i < 120; ++i) {
        errno = 0;
        int rc = ioctl(fb, FBIO_WAITFORVSYNC, &crtc);
        int error = errno;
        int64_t now = monotonic_ns();
        if (i < 8 || rc < 0 || i == 119)
            printf("fbwait i=%d rc=%d errno=%d delta_ns=%lld\n",
                   i, rc, error, (long long)(now - previous));
        if (rc < 0) break;
        previous = now;
    }
    printf("fbwait_elapsed_ns=%lld\n", (long long)(monotonic_ns() - start));
    close(fb);

    int sock = socket(AF_NETLINK, SOCK_DGRAM | SOCK_CLOEXEC, NETLINK_KOBJECT_UEVENT);
    struct sockaddr_nl addr = {.nl_family = AF_NETLINK, .nl_groups = 1};
    if (sock < 0 || bind(sock, (struct sockaddr *)&addr, sizeof(addr))) {
        perror("netlink"); return 1;
    }
    struct pollfd pfd = {.fd = sock, .events = POLLIN};
    int messages = 0, vsyncs = 0;
    start = monotonic_ns();
    while (monotonic_ns() - start < 3000000000LL) {
        if (poll(&pfd, 1, 100) <= 0) continue;
        char buf[4098] = {0};
        ssize_t len = recv(sock, buf, sizeof(buf) - 2, 0);
        if (len <= 0) continue;
        ++messages;
        for (char *p = buf; p < buf + len; p += strlen(p) + 1) {
            if (strncmp(p, "VSYNC", 5) == 0) {
                if (vsyncs < 8) puts(p);
                ++vsyncs;
            }
        }
    }
    printf("uevent_messages=%d vsync_messages=%d\n", messages, vsyncs);
    close(sock);
    return 0;
}
