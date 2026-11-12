// SPDX-License-Identifier: Apache-2.0
#define LOG_TAG "ROCPowerRelease"
#include <log/log.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static const char lock_name[] = "rgsp_android_bringup";
static int held(void) {
    char buf[8192];
    int fd = open("/sys/power/wake_lock", O_RDONLY | O_CLOEXEC);
    if (fd < 0) return -1;
    ssize_t n = read(fd, buf, sizeof(buf) - 1);
    int error = errno;
    close(fd);
    if (n < 0) { errno = error; return -1; }
    buf[n] = 0;
    char *save = NULL;
    for (char *p = strtok_r(buf, " \t\r\n", &save); p; p = strtok_r(NULL, " \t\r\n", &save)) {
        if (strcmp(p, lock_name) == 0) return 1;
    }
    return 0;
}

int main(int argc, char **argv) {
    // Only the exact init service is qualified. No arbitrary name, path or command.
    if (getuid() != 1000 || getppid() != 1 || argc != 2
            || strcmp(argv[1], "--qualified-rg34xxsp") != 0) return 2;
    int before = held();
    if (before < 0) { ALOGE("Cannot inspect fixed bringup lock: errno=%d", errno); return 3; }
    if (!before) { ALOGI("Fixed bringup lock already absent"); return 0; }
    int fd = open("/sys/power/wake_unlock", O_WRONLY | O_CLOEXEC);
    if (fd < 0) { ALOGE("Cannot open fixed unlock endpoint: errno=%d", errno); return 4; }
    ssize_t n;
    do { n = write(fd, lock_name, sizeof(lock_name) - 1); } while (n < 0 && errno == EINTR);
    int error = errno;
    close(fd);
    if (n != (ssize_t)(sizeof(lock_name) - 1)) {
        ALOGE("Fixed bringup unlock failed: errno=%d", error); return 5;
    }
    int after = held();
    if (after != 0) { ALOGE("Fixed bringup lock absence not verified: state=%d", after); return 6; }
    ALOGI("Fixed bringup lock released after completed boot; normal autosuspend available");
    return 0;
}
