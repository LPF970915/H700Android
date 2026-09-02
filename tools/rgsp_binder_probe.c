#include <errno.h>
#include <fcntl.h>
#include <linux/android/binder.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

static void report_ioctl(const char *name, int rc) {
    if (rc == 0) {
        printf("%s=ok\n", name);
    } else {
        printf("%s=error rc=%d errno=%d (%s)\n", name, rc, errno, strerror(errno));
    }
}

int main(int argc, char **argv) {
    const char *device = argc > 1 ? argv[1] : "/dev/binder";
    int fd = open(device, O_RDWR | O_CLOEXEC);
    if (fd < 0) {
        fprintf(stderr, "open(%s): %s\n", device, strerror(errno));
        return 2;
    }

    struct binder_version version = {0};
    int rc = ioctl(fd, BINDER_VERSION, &version);
    report_ioctl("BINDER_VERSION", rc);
    printf("driver_protocol=%d userspace_protocol=%d\n", version.protocol_version,
           BINDER_CURRENT_PROTOCOL_VERSION);

    unsigned int max_threads = 15;
    errno = 0;
    rc = ioctl(fd, BINDER_SET_MAX_THREADS, &max_threads);
    report_ioctl("BINDER_SET_MAX_THREADS", rc);

    struct flat_binder_object object = {0};
    object.flags = FLAT_BINDER_FLAG_TXN_SECURITY_CTX;
    errno = 0;
    rc = ioctl(fd, BINDER_SET_CONTEXT_MGR_EXT, &object);
    report_ioctl("BINDER_SET_CONTEXT_MGR_EXT", rc);

    if (rc != 0) {
        errno = 0;
        rc = ioctl(fd, BINDER_SET_CONTEXT_MGR, 0);
        report_ioctl("BINDER_SET_CONTEXT_MGR", rc);
    }

    close(fd);
    return 0;
}
