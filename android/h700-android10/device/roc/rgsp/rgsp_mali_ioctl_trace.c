#define _GNU_SOURCE

#include <android/log.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/ioctl.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/syscall.h>
#include <unistd.h>

#define KBASE_IOCTL_TYPE 0x80
#define TRACE_PATH "/rgsp-persist/RGSP_ANDROID_MALI_IOCTL_TRACE_LAST.log"
#define TRACE_FALLBACK_PATH "/data/rgsp_mali_ioctl_trace.log"
#define TRACE_TAG "RGSP_MALI_TRACE"

static int trace_fd = -2;

static long trace_tid(void) {
    return syscall(__NR_gettid);
}

static void trace_open_if_needed(void) {
    int saved_errno;

    if (trace_fd != -2) {
        return;
    }
    saved_errno = errno;
    trace_fd = open(TRACE_PATH, O_WRONLY | O_APPEND | O_CLOEXEC);
    if (trace_fd < 0) {
        trace_fd = open(TRACE_FALLBACK_PATH, O_WRONLY | O_APPEND | O_CLOEXEC);
    }
    errno = saved_errno;
}

static void trace_line(int fd, unsigned long request, uintptr_t argument,
                       intptr_t result, int error) {
    char line[320];
    int count;

    trace_open_if_needed();
    count = snprintf(line, sizeof(line),
                     "pid=%d tid=%ld op=ioctl fd=%d req=0x%08lx type=0x%02lx "
                     "nr=%lu dir=%lu size=%lu arg=0x%lx result=0x%lx "
                     "errno=%d",
                     getpid(), trace_tid(), fd, request,
                     (request >> _IOC_TYPESHIFT) & _IOC_TYPEMASK,
                     (request >> _IOC_NRSHIFT) & _IOC_NRMASK,
                     (request >> _IOC_DIRSHIFT) & _IOC_DIRMASK,
                     (request >> _IOC_SIZESHIFT) & _IOC_SIZEMASK,
                     (unsigned long)argument, (unsigned long)result, error);
    if (count > 0) {
        size_t bytes = (size_t)count < sizeof(line) ? (size_t)count : sizeof(line) - 1;
        (void)__android_log_write(ANDROID_LOG_INFO, TRACE_TAG, line);
        if (trace_fd >= 0) {
            (void)write(trace_fd, line, bytes);
            (void)write(trace_fd, "\n", 1);
        }
    }
}

int ioctl(int fd, int request, ...) {
    va_list args;
    void *argument = NULL;
    long result;
    int saved_errno;

    if (_IOC_DIR((unsigned int)request) != _IOC_NONE ||
        _IOC_SIZE((unsigned int)request) != 0) {
        va_start(args, request);
        argument = va_arg(args, void *);
        va_end(args);
    }
    result = syscall(__NR_ioctl, fd, request, argument);
    saved_errno = errno;
    if (_IOC_TYPE((unsigned int)request) == KBASE_IOCTL_TYPE) {
        trace_line(fd, (unsigned int)request, (uintptr_t)argument,
                   result, result < 0 ? saved_errno : 0);
    }
    errno = saved_errno;
    return (int)result;
}
