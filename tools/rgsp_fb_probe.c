#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t interrupted;

static void on_signal(int signo) {
    (void)signo;
    interrupted = 1;
}

static uint64_t fnv1a64(const void *data, size_t size) {
    const uint8_t *bytes = data;
    uint64_t hash = UINT64_C(14695981039346656037);

    for (size_t i = 0; i < size; ++i) {
        hash ^= bytes[i];
        hash *= UINT64_C(1099511628211);
    }
    return hash;
}

static uint32_t scale_channel(uint8_t value, uint32_t bits) {
    if (bits == 0) {
        return 0;
    }
    if (bits >= 8) {
        return (uint32_t)value << (bits - 8);
    }
    return ((uint32_t)value * ((UINT32_C(1) << bits) - 1) + 127) / 255;
}

static uint32_t pack_pixel(const struct fb_var_screeninfo *var,
                           uint8_t r, uint8_t g, uint8_t b, uint8_t a) {
    return (scale_channel(r, var->red.length) << var->red.offset) |
           (scale_channel(g, var->green.length) << var->green.offset) |
           (scale_channel(b, var->blue.length) << var->blue.offset) |
           (scale_channel(a, var->transp.length) << var->transp.offset);
}

static uint8_t unpack_channel(uint32_t pixel, struct fb_bitfield field) {
    uint32_t mask;
    uint32_t value;

    if (field.length == 0) {
        return 0;
    }
    mask = field.length >= 32 ? UINT32_MAX : ((UINT32_C(1) << field.length) - 1);
    value = (pixel >> field.offset) & mask;
    return (uint8_t)((value * 255 + mask / 2) / mask);
}

static int dump_ppm(const char *path, const uint8_t *map,
                    const struct fb_fix_screeninfo *fix,
                    const struct fb_var_screeninfo *var) {
    FILE *out = fopen(path, "wb");
    unsigned bytes_per_pixel = var->bits_per_pixel / 8;

    if (!out) {
        fprintf(stderr, "open %s: %s\n", path, strerror(errno));
        return -1;
    }
    if (fprintf(out, "P6\n%u %u\n255\n", var->xres, var->yres) < 0) {
        fclose(out);
        return -1;
    }

    for (uint32_t y = 0; y < var->yres; ++y) {
        const uint8_t *row = map + (size_t)(var->yoffset + y) * fix->line_length +
                             (size_t)var->xoffset * bytes_per_pixel;
        for (uint32_t x = 0; x < var->xres; ++x) {
            uint32_t pixel = 0;
            uint8_t rgb[3];

            memcpy(&pixel, row + (size_t)x * bytes_per_pixel, bytes_per_pixel);
            rgb[0] = unpack_channel(pixel, var->red);
            rgb[1] = unpack_channel(pixel, var->green);
            rgb[2] = unpack_channel(pixel, var->blue);
            if (fwrite(rgb, sizeof(rgb), 1, out) != 1) {
                fclose(out);
                return -1;
            }
        }
    }

    if (fclose(out) != 0) {
        return -1;
    }
    return 0;
}

static void draw_pattern(uint8_t *map, const struct fb_fix_screeninfo *fix,
                         const struct fb_var_screeninfo *var) {
    static const uint8_t bars[][3] = {
        {255, 255, 255}, {255, 255, 0}, {0, 255, 255}, {0, 255, 0},
        {255, 0, 255}, {255, 0, 0}, {0, 0, 255}, {0, 0, 0},
    };
    unsigned bytes_per_pixel = var->bits_per_pixel / 8;

    for (uint32_t y = 0; y < var->yres; ++y) {
        uint8_t *row = map + (size_t)(var->yoffset + y) * fix->line_length +
                       (size_t)var->xoffset * bytes_per_pixel;
        for (uint32_t x = 0; x < var->xres; ++x) {
            size_t bar = ((size_t)x * (sizeof(bars) / sizeof(bars[0]))) / var->xres;
            uint8_t r = bars[bar][0];
            uint8_t g = bars[bar][1];
            uint8_t b = bars[bar][2];
            uint32_t pixel;

            if (((x / 24) + (y / 24)) % 2 == 0 && y > var->yres * 3 / 4) {
                r /= 2;
                g /= 2;
                b /= 2;
            }
            pixel = pack_pixel(var, r, g, b, 255);
            memcpy(row + (size_t)x * bytes_per_pixel, &pixel, bytes_per_pixel);
        }
    }
}

static void print_bitfield(const char *name, struct fb_bitfield field) {
    printf("%s=%u:%u:%u\n", name, field.offset, field.length, field.msb_right);
}

int main(int argc, char **argv) {
    const char *fb_path = "/dev/fb0";
    const char *dump_path = NULL;
    unsigned pattern_seconds = 0;
    struct fb_fix_screeninfo fix;
    struct fb_var_screeninfo var;
    uint8_t *map = MAP_FAILED;
    uint8_t *backup = NULL;
    int fd = -1;
    int rc = 1;

    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--device") == 0 && i + 1 < argc) {
            fb_path = argv[++i];
        } else if (strcmp(argv[i], "--dump") == 0 && i + 1 < argc) {
            dump_path = argv[++i];
        } else if (strcmp(argv[i], "--pattern") == 0 && i + 1 < argc) {
            char *end = NULL;
            unsigned long value = strtoul(argv[++i], &end, 10);
            if (!end || *end != '\0' || value > 60) {
                fprintf(stderr, "invalid pattern duration\n");
                return 2;
            }
            pattern_seconds = (unsigned)value;
        } else {
            fprintf(stderr, "usage: %s [--device PATH] [--dump PPM] [--pattern 0..60]\n", argv[0]);
            return 2;
        }
    }

    fd = open(fb_path, pattern_seconds ? O_RDWR : O_RDONLY);
    if (fd < 0) {
        fprintf(stderr, "open %s: %s\n", fb_path, strerror(errno));
        goto out;
    }
    if (ioctl(fd, FBIOGET_FSCREENINFO, &fix) < 0 ||
        ioctl(fd, FBIOGET_VSCREENINFO, &var) < 0) {
        fprintf(stderr, "framebuffer ioctl: %s\n", strerror(errno));
        goto out;
    }
    if (var.bits_per_pixel == 0 || var.bits_per_pixel > 32 ||
        var.bits_per_pixel % 8 != 0 || fix.line_length == 0 || fix.smem_len == 0) {
        fprintf(stderr, "unsupported framebuffer layout\n");
        goto out;
    }

    printf("id=%.16s\n", fix.id);
    printf("visible=%ux%u virtual=%ux%u offset=%u,%u\n",
           var.xres, var.yres, var.xres_virtual, var.yres_virtual,
           var.xoffset, var.yoffset);
    printf("bpp=%u stride=%u smem_len=%u type=%u visual=%u\n",
           var.bits_per_pixel, fix.line_length, fix.smem_len, fix.type, fix.visual);
    print_bitfield("red", var.red);
    print_bitfield("green", var.green);
    print_bitfield("blue", var.blue);
    print_bitfield("transp", var.transp);

    map = mmap(NULL, fix.smem_len, pattern_seconds ? (PROT_READ | PROT_WRITE) : PROT_READ,
               MAP_SHARED, fd, 0);
    if (map == MAP_FAILED) {
        fprintf(stderr, "mmap: %s\n", strerror(errno));
        goto out;
    }
    printf("framebuffer_fnv1a64=%016llx\n",
           (unsigned long long)fnv1a64(map, fix.smem_len));

    if (dump_path && dump_ppm(dump_path, map, &fix, &var) != 0) {
        fprintf(stderr, "failed to dump %s\n", dump_path);
        goto out;
    }

    if (pattern_seconds) {
        struct sigaction action;

        backup = malloc(fix.smem_len);
        if (!backup) {
            fprintf(stderr, "malloc %u: %s\n", fix.smem_len, strerror(errno));
            goto out;
        }
        memcpy(backup, map, fix.smem_len);
        memset(&action, 0, sizeof(action));
        action.sa_handler = on_signal;
        sigemptyset(&action.sa_mask);
        sigaction(SIGINT, &action, NULL);
        sigaction(SIGTERM, &action, NULL);

        draw_pattern(map, &fix, &var);
        printf("pattern_fnv1a64=%016llx\n",
               (unsigned long long)fnv1a64(map, fix.smem_len));
        fflush(stdout);
        for (unsigned i = 0; i < pattern_seconds && !interrupted; ++i) {
            struct timespec delay = {.tv_sec = 1, .tv_nsec = 0};
            while (nanosleep(&delay, &delay) < 0 && errno == EINTR && !interrupted) {
            }
        }
        memcpy(map, backup, fix.smem_len);
        printf("restored_fnv1a64=%016llx\n",
               (unsigned long long)fnv1a64(map, fix.smem_len));
    }

    rc = 0;
out:
    free(backup);
    if (map != MAP_FAILED) {
        munmap(map, fix.smem_len);
    }
    if (fd >= 0) {
        close(fd);
    }
    return rc;
}
