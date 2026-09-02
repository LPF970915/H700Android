#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <fcntl.h>
#include <linux/ioctl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

#define DISP_GET_SCN_WIDTH 0x07
#define DISP_GET_SCN_HEIGHT 0x08
#define DISP_GET_OUTPUT_TYPE 0x09
#define DISP_GET_OUTPUT 0x10
#define DISP_DEVICE_GET_CONFIG 0x15

struct disp_output {
    uint32_t type;
    uint32_t mode;
};

struct disp_device_config {
    uint32_t type;
    uint32_t mode;
    uint32_t format;
    uint32_t bits;
    uint32_t eotf;
    uint32_t color_space;
    uint32_t dvi_hdmi;
    uint32_t range;
    uint32_t scan;
    uint32_t aspect_ratio;
    uint32_t reserved;
};

#define ION_IOC_MAGIC 'I'
#define ION_MAX_HEAP_NAME 32

typedef int ion_user_handle_t;

struct ion_allocation_data {
    size_t len;
    size_t align;
    uint32_t heap_id_mask;
    uint32_t flags;
    ion_user_handle_t handle;
};

struct ion_fd_data {
    ion_user_handle_t handle;
    int fd;
};

struct ion_handle_data {
    ion_user_handle_t handle;
};

struct ion_heap_data {
    char name[ION_MAX_HEAP_NAME];
    uint32_t type;
    uint32_t heap_id;
    uint32_t reserved[3];
};

struct ion_heap_query {
    uint32_t count;
    uint32_t reserved0;
    uint64_t heaps;
    uint32_t reserved1;
    uint32_t reserved2;
};

#define ION_IOC_ALLOC _IOWR(ION_IOC_MAGIC, 0, struct ion_allocation_data)
#define ION_IOC_FREE _IOWR(ION_IOC_MAGIC, 1, struct ion_handle_data)
#define ION_IOC_SHARE _IOWR(ION_IOC_MAGIC, 4, struct ion_fd_data)
#define ION_IOC_SYNC _IOWR(ION_IOC_MAGIC, 7, struct ion_fd_data)
#define ION_IOC_HEAP_QUERY _IOWR(ION_IOC_MAGIC, 8, struct ion_heap_query)

#define KBASE_IOCTL_TYPE 0x80

struct kbase_ioctl_version_check {
    uint16_t major;
    uint16_t minor;
};

struct kbase_ioctl_set_flags {
    uint32_t create_flags;
};

struct kbase_ioctl_get_gpuprops {
    uint64_t buffer;
    uint32_t size;
    uint32_t flags;
};

struct kbase_ioctl_get_ddk_version {
    uint64_t version_buffer;
    uint32_t size;
    uint32_t padding;
};

#define KBASE_IOCTL_VERSION_CHECK \
    _IOWR(KBASE_IOCTL_TYPE, 0, struct kbase_ioctl_version_check)
#define KBASE_IOCTL_SET_FLAGS \
    _IOW(KBASE_IOCTL_TYPE, 1, struct kbase_ioctl_set_flags)
#define KBASE_IOCTL_GET_GPUPROPS \
    _IOW(KBASE_IOCTL_TYPE, 3, struct kbase_ioctl_get_gpuprops)
#define KBASE_IOCTL_GET_DDK_VERSION \
    _IOW(KBASE_IOCTL_TYPE, 13, struct kbase_ioctl_get_ddk_version)

static int disp_ioctl(int fd, unsigned long request, unsigned long display,
                      unsigned long arg1, unsigned long arg2, unsigned long arg3) {
    unsigned long args[4] = {display, arg1, arg2, arg3};
    return ioctl(fd, request, args);
}

static int probe_disp(void) {
    int fd = open("/dev/disp", O_RDWR | O_CLOEXEC);

    if (fd < 0) {
        fprintf(stderr, "disp_open_error=%s\n", strerror(errno));
        return -1;
    }

    for (unsigned display = 0; display < 2; ++display) {
        struct disp_output output = {0};
        struct disp_device_config config = {0};
        int width = disp_ioctl(fd, DISP_GET_SCN_WIDTH, display, 0, 0, 0);
        int height = disp_ioctl(fd, DISP_GET_SCN_HEIGHT, display, 0, 0, 0);
        int type = disp_ioctl(fd, DISP_GET_OUTPUT_TYPE, display, 0, 0, 0);
        int output_rc = disp_ioctl(fd, DISP_GET_OUTPUT, display,
                                   (unsigned long)(uintptr_t)&output, 0, 0);
        int config_rc = disp_ioctl(fd, DISP_DEVICE_GET_CONFIG, display,
                                   (unsigned long)(uintptr_t)&config, 0, 0);

        printf("disp%u width=%d height=%d type=%d output_rc=%d output=%u:%u ",
               display, width, height, type, output_rc, output.type, output.mode);
        printf("config_rc=%d config=%u:%u:%u:%u:%u:%u:%u:%u:%u:%u\n",
               config_rc, config.type, config.mode, config.format, config.bits,
               config.eotf, config.color_space, config.dvi_hdmi, config.range,
               config.scan, config.aspect_ratio);
    }

    close(fd);
    return 0;
}

static int probe_ion(void) {
    struct ion_heap_query query = {0};
    struct ion_heap_data *heaps = NULL;
    int fd = open("/dev/ion", O_RDWR | O_CLOEXEC);
    int system_heap_id = -1;
    int rc = -1;

    if (fd < 0) {
        fprintf(stderr, "ion_open_error=%s\n", strerror(errno));
        return -1;
    }
    if (ioctl(fd, ION_IOC_HEAP_QUERY, &query) < 0) {
        fprintf(stderr, "ion_heap_count_error=%s ioctl=0x%lx\n",
                strerror(errno), (unsigned long)ION_IOC_HEAP_QUERY);
        goto out;
    }
    if (query.count == 0 || query.count > 64) {
        fprintf(stderr, "ion_heap_count_invalid=%u\n", query.count);
        goto out;
    }

    heaps = calloc(query.count, sizeof(*heaps));
    if (!heaps) {
        goto out;
    }
    query.heaps = (uint64_t)(uintptr_t)heaps;
    errno = 0;
    int heap_query_rc = ioctl(fd, ION_IOC_HEAP_QUERY, &query);
    if (heap_query_rc < 0 && errno != EINVAL) {
        fprintf(stderr, "ion_heap_query_error=%s\n", strerror(errno));
        goto out;
    }
    /* Allwinner's 4.9 ion_query_heaps() fills the array but leaves ret=-EINVAL. */
    printf("ion_heap_query_rc=%d errno=%d vendor_einval=%d\n",
           heap_query_rc, heap_query_rc < 0 ? errno : 0,
           heap_query_rc < 0 && errno == EINVAL);

    printf("ion_heap_count=%u\n", query.count);
    for (uint32_t i = 0; i < query.count; ++i) {
        printf("ion_heap[%u]=name:%.*s type:%u id:%u\n", i,
               ION_MAX_HEAP_NAME, heaps[i].name, heaps[i].type, heaps[i].heap_id);
        if (heaps[i].type == 0 && heaps[i].heap_id < 32 && system_heap_id < 0) {
            system_heap_id = (int)heaps[i].heap_id;
        }
    }

    if (system_heap_id >= 0) {
        struct ion_allocation_data allocation = {
            .len = 4096,
            .align = 4096,
            .heap_id_mask = UINT32_C(1) << system_heap_id,
            .flags = 0,
            .handle = 0,
        };
        struct ion_fd_data shared = {.handle = 0, .fd = -1};
        struct ion_handle_data release = {.handle = 0};
        void *map = MAP_FAILED;

        if (ioctl(fd, ION_IOC_ALLOC, &allocation) < 0) {
            fprintf(stderr, "ion_alloc_error=%s heap_id=%d ioctl=0x%lx\n",
                    strerror(errno), system_heap_id, (unsigned long)ION_IOC_ALLOC);
            goto out;
        }
        release.handle = allocation.handle;
        shared.handle = allocation.handle;
        if (ioctl(fd, ION_IOC_SHARE, &shared) < 0) {
            fprintf(stderr, "ion_share_error=%s\n", strerror(errno));
            ioctl(fd, ION_IOC_FREE, &release);
            goto out;
        }
        map = mmap(NULL, allocation.len, PROT_READ | PROT_WRITE, MAP_SHARED, shared.fd, 0);
        if (map == MAP_FAILED) {
            fprintf(stderr, "ion_mmap_error=%s\n", strerror(errno));
            close(shared.fd);
            ioctl(fd, ION_IOC_FREE, &release);
            goto out;
        }
        memset(map, 0xa5, allocation.len);
        if (((const uint8_t *)map)[0] != 0xa5 ||
            ((const uint8_t *)map)[allocation.len - 1] != 0xa5) {
            fprintf(stderr, "ion_memory_verify_error\n");
            munmap(map, allocation.len);
            close(shared.fd);
            ioctl(fd, ION_IOC_FREE, &release);
            goto out;
        }
        (void)ioctl(fd, ION_IOC_SYNC, &shared);
        printf("ion_alloc_ok heap_id=%d handle=%d dma_buf_fd=%d bytes=%zu\n",
               system_heap_id, allocation.handle, shared.fd, allocation.len);
        munmap(map, allocation.len);
        close(shared.fd);
        if (ioctl(fd, ION_IOC_FREE, &release) < 0) {
            fprintf(stderr, "ion_free_error=%s\n", strerror(errno));
            goto out;
        }
    }

    rc = 0;
out:
    free(heaps);
    close(fd);
    return rc;
}

static int probe_mali(void) {
    struct kbase_ioctl_version_check version = {.major = 11, .minor = 17};
    struct kbase_ioctl_set_flags flags = {.create_flags = 0};
    struct kbase_ioctl_get_gpuprops properties = {0};
    struct kbase_ioctl_get_ddk_version ddk = {0};
    char version_string[128] = {0};
    int fd = open("/dev/mali0", O_RDWR | O_CLOEXEC);
    int property_bytes;

    if (fd < 0) {
        fprintf(stderr, "mali_open_error=%s\n", strerror(errno));
        return -1;
    }
    if (ioctl(fd, KBASE_IOCTL_VERSION_CHECK, &version) < 0) {
        fprintf(stderr, "mali_version_error=%s ioctl=0x%lx\n",
                strerror(errno), (unsigned long)KBASE_IOCTL_VERSION_CHECK);
        close(fd);
        return -1;
    }
    printf("mali_uk_version=%u.%u\n", version.major, version.minor);

    if (ioctl(fd, KBASE_IOCTL_SET_FLAGS, &flags) < 0) {
        fprintf(stderr, "mali_set_flags_error=%s\n", strerror(errno));
        close(fd);
        return -1;
    }

    ddk.version_buffer = (uint64_t)(uintptr_t)version_string;
    ddk.size = sizeof(version_string);
    int ddk_bytes = ioctl(fd, KBASE_IOCTL_GET_DDK_VERSION, &ddk);
    if (ddk_bytes >= 0) {
        version_string[sizeof(version_string) - 1] = '\0';
        printf("mali_ddk_version_bytes=%d value=%s\n", ddk_bytes, version_string);
    } else {
        printf("mali_ddk_version_error=%s\n", strerror(errno));
    }

    property_bytes = ioctl(fd, KBASE_IOCTL_GET_GPUPROPS, &properties);
    if (property_bytes >= 0) {
        printf("mali_gpuprops_bytes=%d\n", property_bytes);
    } else {
        printf("mali_gpuprops_error=%s\n", strerror(errno));
    }

    close(fd);
    return 0;
}

int main(void) {
    int failures = 0;

    failures += probe_disp() != 0;
    failures += probe_ion() != 0;
    failures += probe_mali() != 0;
    printf("probe_failures=%d\n", failures);
    return failures ? 1 : 0;
}
