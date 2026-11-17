/* Bounded LCD event lookup. No heap, MMIO, writable global or large buffer. */
typedef unsigned char u8;
extern const u8 *panel_blob(unsigned program);
extern unsigned panel_select(unsigned profile, unsigned branch);
extern void panel_cmd(int value);
extern void panel_data(int value);
extern void panel_wait(unsigned milliseconds);

static unsigned u16(const u8 *p) { return p[0] | (unsigned)p[1] << 8; }

/* Copy tokens always point backwards in the frozen program graph. Lookup is
 * iterative, so a malformed token cannot exhaust the kernel/bootloader stack. */
__attribute__((noinline))
static unsigned event_at(unsigned program, unsigned index)
{
    for (unsigned depth = 0; depth < 17; ++depth) {
        const u8 *header = panel_blob(program);
        if (!header || index >= u16(header) || u16(header) > 640) return 0;
        const u8 *p = header + 4, *end = p + u16(header + 2);
        unsigned cursor = 0;
        while (p < end) {
            unsigned token = *p++, size = 1, value;
            if (token & 128) {
                if (end - p < 2) return 0;
                unsigned word = (token & 127) << 16 | p[0] << 8 | p[1];
                p += 2;
                unsigned source = word >> 19, offset = word >> 9 & 1023;
                size = (word & 511) + 3;
                if (source > program || (source == program && offset + size > cursor))
                    return 0;
                if (index < cursor + size) {
                    program = source;
                    index = offset + index - cursor;
                    goto next_program;
                }
            } else {
                if (p == end || token == 0 || token == 127) return 0;
                value = *p++;
                if (token < 4) {
                    if (cursor == index)
                        return ((token == 1 ? 3 : token == 2 ? 1 : 2) << 8) | value;
                } else {
                    size = token - 2;
                    if ((unsigned)(end - p) < size - 1) return 0;
                    if (index < cursor + size)
                        return index == cursor ? 256 | value : 512 | p[index - cursor - 1];
                    p += size - 1;
                }
            }
            cursor += size;
        }
        return 0;
next_program:;
    }
    return 0;
}

__attribute__((noinline, used))
void panel_apply(unsigned profile, unsigned branch)
{
    if (profile >= 10) profile = 0;
    unsigned program = panel_select(profile, branch);
    const u8 *header = panel_blob(program);
    if (!header || u16(header) > 640) return;
    unsigned count = u16(header);
    for (unsigned i = 0; i < count; ++i) {
        unsigned event = event_at(program, i), value = event & 255;
#ifdef PANEL_SIGNED_BYTE
        int byte = (signed char)value;
#else
        int byte = value;
#endif
        if ((event >> 8) == 1) panel_cmd(byte);
        else if ((event >> 8) == 2) panel_data(byte);
        else if ((event >> 8) == 3) panel_wait(value);
        else return;
    }
#ifdef PANEL_KERNEL_LEGACY_WAIT
    if (profile == 0 && branch != 1) panel_wait(100);
#endif
}
