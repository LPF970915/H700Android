/* SPDX-License-Identifier: MIT
 * H700 RG34XXSP input bring-up. Register layout: retained Allwinner H616 BSP;
 * mux pins: ROCKNIX H700 DTS, PI0 enable, PI1/PI2 select, PE8/PE9 stick clicks.
 * No arbitrary MMIO address or write command is accepted.
 */
#include <errno.h>
#include <fcntl.h>
#include <linux/gpio.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/file.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

static volatile uint32_t *ccu, *pio, *adc;
static uint32_t original_cfg, original_data, original_clock, saved_adc[7];
static const unsigned int adc_registers[] = {0, 4, 8, 0xc, 0x20, 0x24, 0x28};
static int mux_fd = -1, initialized;
static volatile sig_atomic_t running = 1;

static volatile uint32_t *map_page(int fd, off_t address, int writeable) {
    void *page = mmap(NULL, 4096, PROT_READ | (writeable ? PROT_WRITE : 0), MAP_SHARED, fd, address);
    if (page == MAP_FAILED) { perror("mmap input register page"); exit(1); }
    return page;
}

static void stop(int signal_number) { (void)signal_number; running = 0; }

static void cleanup(void) {
    if (initialized) {
        adc[1] &= ~(1u << 16);
        for (unsigned int i = 0; i < 7; ++i) adc[adc_registers[i] / 4] = saved_adc[i];
        ccu[0x9ec / 4] = (ccu[0x9ec / 4] & ~0x10001u) | (original_clock & 0x10001u);
    }
    if (mux_fd >= 0) {
        struct gpiohandle_data values = {0};
        for (unsigned int i = 0; i < 3; ++i) values.values[i] = (original_data >> i) & 1;
        ioctl(mux_fd, GPIOHANDLE_SET_LINE_VALUES_IOCTL, &values);
        close(mux_fd);
        pio[0x120 / 4] = (pio[0x120 / 4] & ~0xfffu) | (original_cfg & 0xfffu);
        mux_fd = -1;
    }
    if (ccu) munmap((void *)ccu, 4096);
    if (pio) munmap((void *)pio, 4096);
    if (adc) munmap((void *)adc, 4096);
}

static int initialize_adc(void) {
    int chip = -1;
    struct gpiochip_info info = {0};
    for (unsigned int index = 0; index < 8; ++index) {
        char name[40]; snprintf(name, sizeof(name), "/dev/gpiochip%u", index);
        int candidate = open(name, O_RDWR | O_CLOEXEC);
        if (candidate < 0) continue;
        if (!ioctl(candidate, GPIO_GET_CHIPINFO_IOCTL, &info) && info.lines > 258
                && (!strcmp(info.label, "pio") || strstr(info.label, "0300b000"))) {
            chip = candidate; break;
        }
        close(candidate);
    }
    if (chip < 0) { fputs("H700 main PIO GPIO chip not found\n", stderr); return -1; }
    original_cfg = pio[0x120 / 4]; original_data = pio[0x130 / 4];
    struct gpiohandle_request request = {0};
    request.lines = 3; request.flags = GPIOHANDLE_REQUEST_OUTPUT;
    request.lineoffsets[0] = 256; request.lineoffsets[1] = 257; request.lineoffsets[2] = 258;
    strcpy(request.consumer_label, "h700-rg34xxsp-mux");
    if (ioctl(chip, GPIO_GET_LINEHANDLE_IOCTL, &request)) {
        perror("request exclusive PI0/PI1/PI2 GPIO ownership"); close(chip); return -1;
    }
    close(chip); mux_fd = request.fd;
    original_clock = ccu[0x9ec / 4];
    ccu[0x9ec / 4] |= 0x10001;
    for (unsigned int i = 0; i < 7; ++i) saved_adc[i] = adc[adc_registers[i] / 4];
    initialized = 1;
    adc[1] = saved_adc[1] & ~(1u << 16);
    adc[0] = (saved_adc[0] & 0xffffu) | (479u << 16); /* 24MHz / 480 = 50kHz */
    adc[2] = 1;
    adc[3] = 0; adc[0x20 / 4] = 0; adc[0x24 / 4] = 0; adc[0x28 / 4] = 0;
    adc[1] = (saved_adc[1] & ~0x300u) | 0x10200u; /* continuous, enabled */
    usleep(10000);
    return 0;
}

static int read_channels(int values[4]) {
    for (unsigned int channel = 0; channel < 4; ++channel) {
        struct gpiohandle_data data = {0};
        data.values[1] = channel & 1;
        data.values[2] = (channel >> 1) & 1;
        if (ioctl(mux_fd, GPIOHANDLE_SET_LINE_VALUES_IOCTL, &data)) return -1;
        usleep(200);
        values[channel] = adc[0x80 / 4] & 0xfff;
    }
    return 0;
}

int main(int argc, char **argv) {
    int sample = argc == 4 && !strcmp(argv[1], "--sample") && !strcmp(argv[2], "rg34xxsp");
    if (!sample && (argc != 2 || strcmp(argv[1], "--probe"))) {
        fputs("usage: h700-sticks --probe | --sample rg34xxsp COUNT\n", stderr);
        return 2;
    }
    int count = sample ? atoi(argv[3]) : 0;
    if (sample && (count < 1 || count > 6000)) return 2;
    int lock = open("/data/local/tmp/h700-sticks.lock", O_CREAT | O_RDWR | O_NOFOLLOW, 0600);
    if (lock < 0 || flock(lock, LOCK_EX | LOCK_NB)) { perror("exclusive sampler lock"); return 1; }
    int fd = open("/dev/mem", (sample ? O_RDWR : O_RDONLY) | O_SYNC);
    if (fd < 0) { perror("open /dev/mem"); return 1; }
    atexit(cleanup);
    ccu = map_page(fd, 0x03001000, sample);
    pio = map_page(fd, 0x0300b000, sample);
    adc = map_page(fd, 0x05070000, sample);
    printf("GPADC_BGR=%08x PI_CFG0=%08x PI_DATA=%08x PE_CFG1=%08x PE_DATA=%08x\n",
           ccu[0x9ec / 4], pio[0x120 / 4], pio[0x130 / 4], pio[0x94 / 4], pio[0xa0 / 4]);
    printf("ADC_SR=%08x CTRL=%08x SELECT=%08x DATA0=%08x DATA1=%08x\n",
           adc[0], adc[1], adc[2], adc[0x80 / 4], adc[0x84 / 4]);
    if (sample) {
        signal(SIGINT, stop); signal(SIGTERM, stop);
        signal(SIGHUP, stop); signal(SIGPIPE, stop);
        if (initialize_adc()) return 1;
        for (int index = 0; index < count && running; ++index) {
            int values[4];
            if (read_channels(values)) { perror("read mux channels"); return 1; }
            printf("sample=%d channels=%d,%d,%d,%d\n", index, values[0], values[1], values[2], values[3]);
            fflush(stdout);
            usleep(50000);
        }
    }
    close(fd);
    /* Keep flock until after atexit restores MMIO/GPIO ownership. */
    return 0;
}
