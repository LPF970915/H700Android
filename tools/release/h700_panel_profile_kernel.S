/* Ordinary candidate source only. This file has not been compiled or patched.
 * Actual kernel SHA-256:
 * 3328c2fab9f19f7ea6a80e34b0a76238cf594bc631f77e05fec32f8adabad042
 *
 * Keep original [3a29b0,3a2b50) prologue/reset/probe bytes unchanged.
 * Both original branch entries reach this bridge with w19 holding the original
 * physical old/boe flag. Only branch==1 selects boe in the frozen library.
 */

.section .bridge_boe,"ax",%progbits
.p2align 2
.global kernel_bridge_boe
.type kernel_bridge_boe,%function
kernel_bridge_boe:
    b kernel_profile_dispatch
.size kernel_bridge_boe,.-kernel_bridge_boe

.section .profile_dispatch,"ax",%progbits
.p2align 2
.global kernel_profile_dispatch
.type kernel_profile_dispatch,%function
kernel_profile_dispatch:
    /* The original outer frame already saves x19, x29 and caller LR.
     * Our 16-byte local frame saves the branch across the real getter call.
     * This bridge never returns: after unwinding it uses the original
     * epilogue, which restores the original caller frame and LR.
     */
    sub sp, sp, #16
    str wzr, [sp]
    str w19, [sp, #4]
    adr x0, kernel_profile_main
    adr x1, kernel_profile_sub
    mov x2, sp
    mov w3, #1
    bl kernel_profile_get_item
    /* A present u32 equal to 1 is the only opt-in profile. Missing property,
     * failed getter, zero and all unknown values choose retained720.
     */
    cmp w0, #1
    b.ne 1f
    ldr w0, [sp]
    cmp w0, #1
    cset w0, eq
    b 2f
1:
    mov w0, wzr
2:
    ldr w1, [sp, #4]
    add sp, sp, #16
    bl kernel_panel_apply_frozen
    /* All four frozen streams contain their entire command/wait tail.
     * Do not enter old join3a482c: that would repeat CMD29/WAIT100.
     */
    b kernel_original_epilogue
.size kernel_profile_dispatch,.-kernel_profile_dispatch

.type kernel_profile_main,%object
kernel_profile_main:
    .asciz "lcd0"
.size kernel_profile_main,.-kernel_profile_main
.type kernel_profile_sub,%object
kernel_profile_sub:
    .asciz "roc_panel_profile"
.size kernel_profile_sub,.-kernel_profile_sub
.p2align 2

.section .bridge_old,"ax",%progbits
.p2align 2
.global kernel_bridge_old
.type kernel_bridge_old,%function
kernel_bridge_old:
    b kernel_profile_dispatch
.size kernel_bridge_old,.-kernel_bridge_old

/* All external calls are PC-relative. Uniform kernel relocation/KASLR slides
 * therefore preserve targets without introducing a new relocation cell.
 */
.global kernel_profile_get_item
.type kernel_profile_get_item,%function
.set kernel_profile_get_item,0xffffff8008400298
.global kernel_panel_apply_frozen
.type kernel_panel_apply_frozen,%function
.set kernel_panel_apply_frozen,0xffffff8008423480
.global kernel_original_epilogue
.type kernel_original_epilogue,%function
.set kernel_original_epilogue,0xffffff8008424840

.section .note.GNU-stack,"",%progbits
