/* Host-verified H700 command-table library: no automatic identity selection.
 * profile0/unknown -> retained720 sequence, profile1 -> pinned35H640 sequence.
 * The old/boe branch only selects a vendor table inside the chosen profile.
 * No MMIO, framebuffer, image patch, reset, GPIO or power-flow code is here.
 */
struct panel_event { unsigned char kind, value; };
struct panel_program { unsigned short count; struct panel_event events[]; };
extern const struct panel_program *panel_table(unsigned profile, unsigned branch);
extern void panel_cmd(int value);
extern void panel_data(int value);
extern void panel_wait(unsigned milliseconds);

static int panel_byte(unsigned value)
{
#ifdef PANEL_SIGNED_BYTE
    return (signed char)value;
#else
    return (unsigned char)value;
#endif
}

__attribute__((noinline, used))
void panel_apply(unsigned profile, unsigned branch)
{
    const struct panel_program *program = panel_table(profile, branch);
    unsigned count = program->count;
    /* Reject malformed lengths before the finite, explicitly counted loop. */
    if (count > 636)
        return;
    for (unsigned i = 0; i < count; ++i) {
        unsigned kind = program->events[i].kind;
        unsigned value = program->events[i].value;
        if (kind == 1)
            panel_cmd(panel_byte(value));
        else if (kind == 2)
            panel_data(panel_byte(value));
        else if (kind == 3)
            panel_wait(value);
        else
            return;
    }
}
