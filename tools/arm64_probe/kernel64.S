/* Standalone AArch64 Linux syscall probe: no libc, Binder, GPU or storage writes. */
.section .text
.global _start
_start:
    mov x0, #0
    mov x1, #4096
    mov x2, #3
    mov x3, #0x22
    mov x4, #-1
    mov x5, #0
    mov x8, #222
    svc #0
    tbnz x0, #63, failed
    mov x19, x0
    mov x20, #0x1234
    movk x20, #0x5678, lsl #32
    str x20, [x19]
    ldr x21, [x19]
    cmp x20, x21
    b.ne failed
    mov x0, x19
    mov x1, #4096
    mov x8, #215
    svc #0
    cbnz x0, failed
    mov x0, #1
    adr x1, message
    adr x2, message_end
    sub x2, x2, x1
    mov x8, #64
    svc #0
    mov x0, #0
    mov x8, #93
    svc #0
failed:
    mov x0, #1
    mov x8, #93
    svc #0
.section .rodata
message:
    .ascii "ARM64_STATIC_OK pointer_bits=64 mmap_rw64=pass munmap=pass\n"
message_end:
