/* Independent manual-panel recovery candidate; original bridge stays frozen.
 * Actual pinned U-Boot early-display deferral bridge. Local references are
 * PC-relative and external branches resolve at link time. No saved env write.
 * Resolve the model/profile before applying the selector-only volume hotkey.
 * First use defaults to the complete 35H640 profile; malformed stored requests
 * retain the original720 error fallback. No automatic profile probing. */
.syntax unified
.thumb
.section .early_bridge,"ax",%progbits
.p2align 2
.global roc_early_after_environment
.type roc_early_after_environment,%function
.thumb_func
roc_early_after_environment:
    push {r4-r8,r10,lr}
    sub sp,#60
    bl roc_initr_env
    cmp r0,#0
    bne .Lreturn
    adr.w r4,.Lmodel640
    movs r5,#1
    adr.w r6,.Lselector
    adr.w r0,.Lnextstart
    bl roc_env_get
    cmp r0,#0
    beq .Lread_saved
    ldrb r1,[r0]
    cmp r1,#49
    beq .Lnext_once
    cmp r1,#50
    bne .Lsafe_default
    /* Strict next_start=2 retains selector: trial never starts Android. */
    b .Lvalidate_next
.Lnext_once:
    adr.w r6,.Lonce
.Lvalidate_next:
    ldrb r1,[r0,#1]
    cmp r1,#0
    bne .Lsafe_default
    adr.w r0,.Lnextmodel
    bl roc_env_get
    bl .Llookup
    cmp r0,#0
    beq .Lsafe_default
    mov r4,r0
    mov r5,r1
    b .Lresolve_hotkey
.Lread_saved:
    adr.w r0,.Lsavedmodel
    bl roc_env_get
    cmp r0,#0
    beq .Lresolve_hotkey
    ldrb r1,[r0]
    cmp r1,#0
    beq .Lresolve_hotkey
    bl .Llookup
    cmp r0,#0
    beq .Lsafe_default
    mov r4,r0
    mov r5,r1
    adr.w r6,.Lsaved
    b .Lresolve_hotkey
.Lsafe_default:
    /* A present malformed record is not a first-use request. */
    adr.w r4,.Lmodel720
    movs r5,#0
    adr.w r6,.Lselector
.Lresolve_hotkey:
    bl roc_volume_down_held
    cmp r0,#1
    bne .Lapply
    /* Reopen the menu without replacing the resolved physical panel. */
    adr.w r6,.Lselector
.Lapply:
    mov r10,r4
    adr.w r0,.Lworking_fdt_delta
    ldr r1,[r0]
    add r0,r0,r1
    ldr r7,[r0]
    cmp r7,#0
    beq .Lfallback
    mov r0,r7
    adr.w r1,.Lpanelpath
    bl roc_fdt_path_offset
    cmp r0,#0
    blt .Lfallback
    mov r8,r0
    adr.w r4,.Lproperties
    /* Preserve canonical model while r4 walks property names. */
    str r4,[sp,#56]
    movs r4,#0
.Lvalidate_property:
    mov r0,r7
    mov r1,r8
    ldr r2,[sp,#56]
    add r3,sp,#52
    movs r12,#0
    str r12,[r3]
    bl roc_fdt_getprop
    cmp r0,#0
    beq .Lfallback
    ldr r1,[sp,#52]
    cmp r1,#4
    bne .Lfallback
    str r0,[sp,r4,lsl #2]
    ldr r2,[sp,#56]
.Lnext_property_name:
    ldrb r1,[r2],#1
    cmp r1,#0
    bne .Lnext_property_name
    str r2,[sp,#56]
    adds r4,#1
    cmp r4,#13
    bne .Lvalidate_property
    adr.w r2,.Lvalues
    movs r0,#52
    mla r2,r5,r0,r2
    movs r4,#0
.Lwrite_property:
    ldr r0,[sp,r4,lsl #2]
    ldr r1,[r2,r4,lsl #2]
    rev r1,r1
    str r1,[r0]
    adds r4,#1
    cmp r4,#13
    bne .Lwrite_property
    b .Lset_active
.Lfallback:
    adr.w r10,.Lmodel720
    movs r5,#0
    adr.w r6,.Lselector
.Lset_active:
    adr.w r0,.Lactive
    mov r1,r10
    bl roc_env_set
    cmp r0,#0
    bne .Lreturn
    adr.w r0,.Lroute
    mov r1,r6
    bl roc_env_set
    cmp r0,#0
    bne .Lreturn
    bl roc_original_workmode_display
    movs r0,#0
.Lreturn:
    add sp,#60
    pop {r4-r8,r10,pc}
.size roc_early_after_environment,.-roc_early_after_environment

/* Canonical twelve-model lookup.  A model remains distinct even where an
 * electrical candidate is shared.  No RAM or geometry inference is used. */
.thumb_func
.Llookup:
    cmp r0,#0
    beq .Lunknown_leaf
    push {r4-r6,lr}
    mov r4,r0
    adr.w r5,.Lmodels
.Llookup_next:
    ldrb r0,[r5]
    cmp r0,#0
    beq .Llookup_missing
    mov r0,r4
    mov r1,r5
    bl .Lequal
    mov r6,r5
.Llookup_advance:
    ldrb r1,[r6],#1
    cmp r1,#0
    bne .Llookup_advance
    ldrb r1,[r6],#1
    cmp r0,#1
    beq .Llookup_found
    mov r5,r6
    b .Llookup_next
.Llookup_found:
    mov r0,r5
    pop {r4-r6,pc}
.Llookup_missing:
    movs r0,#0
    pop {r4-r6,pc}
.Lunknown_leaf:
    movs r0,#0
    bx lr
.thumb_func
.Lequal:
    ldrb r2,[r0],#1
    ldrb r3,[r1],#1
    cmp r2,r3
    bne .Lunknown_leaf
    cmp r2,#0
    bne .Lequal
    movs r0,#1
    bx lr

.global roc_volume_down_held
.type roc_volume_down_held,%function
.thumb_func
roc_volume_down_held:
    push {r4-r6,lr}
    sub sp,#56
    movs r0,#0
    movs r1,#0
.Lclear_gpio:
    str r0,[sp,r1]
    adds r1,#4
    cmp r1,#56
    bne .Lclear_gpio
    adr.w r0,.Lvolpath
    adr.w r1,.Lgpios
    mov r2,sp
    bl roc_fdt_get_one_gpio
    cmp r0,#0
    bne .Lnotheld
    ldr r0,[sp,#32]
    cmp r0,#5
    bne .Lnotheld
    ldr r0,[sp,#36]
    cmp r0,#2
    bne .Lnotheld
    movs r0,#0
    str r0,[sp,#40]
    movs r0,#1
    str r0,[sp,#44]
    mov r0,sp
    movs r1,#1
    bl roc_gpio_request
    cmp r0,#0
    beq .Lnotheld
    mov r4,r0
    movs r5,#5
.Lvolume_sample:
    mov r0,r4
    movs r1,#0
    bl roc_gpio_read_one
    cmp r0,#0
    bne .Lnotheld
    movw r0,#1000
    bl roc_udelay
    subs r5,#1
    bne .Lvolume_sample
    movs r0,#1
    b .Lvolume_return
.Lnotheld:
    movs r0,#0
.Lvolume_return:
    add sp,#56
    pop {r4-r6,pc}
.size roc_volume_down_held,.-roc_volume_down_held

.p2align 2
.Lworking_fdt_delta:
    .word 0x4a09d874 - .Lworking_fdt_delta
/* Generated from twelve_model/models.py; profile indexes are electrical. */
.p2align 2
.Lvalues:
    .word 0,720,480,26,46,820,2,20,536,5,1,3,1
    .word 1,640,480,24,46,770,20,15,520,4,2,3,1
    .word 2,720,480,26,46,820,2,20,536,5,1,3,1
    .word 3,720,720,48,46,1060,2,20,755,5,0,0,1
    .word 4,640,480,24,46,770,20,15,520,4,2,3,1
    .word 5,480,640,24,56,586,6,26,686,6,0,0,0
    .word 6,640,480,24,46,770,20,15,522,4,2,3,1
    .word 7,640,480,24,46,770,20,15,522,4,2,3,1
    .word 8,640,480,48,48,1414,8,48,566,4,2,3,1
    .word 9,640,480,24,46,770,20,14,528,4,2,3,1
.Lmodels:
    .asciz "rg34xx"
    .byte 2
    .asciz "rg34xxsp"
    .byte 0
    .asciz "rgsp"
    .byte 0
    .asciz "rgcubexx"
    .byte 3
    .asciz "rg35xxplus"
    .byte 4
    .asciz "rg35xx_2025"
    .byte 4
    .asciz "rg28xx"
    .byte 5
    .asciz "rg35xxh"
    .byte 1
    .asciz "rg40xxh"
    .byte 6
    .asciz "rg40xxv"
    .byte 7
    .asciz "rg35xxsp"
    .byte 8
    .asciz "rg35xxpro"
    .byte 9
    .byte 0
.Lproperties:
    .asciz "roc_panel_profile","lcd_x","lcd_y","lcd_dclk_freq","lcd_hbp","lcd_ht","lcd_hspw","lcd_vbp","lcd_vt","lcd_vspw","lcd_hv_clk_phase","lcd_hv_sync_polarity","lcd_frm"
.Lpanelpath: .asciz "/soc@03000000/lcd0@01c0c000"
.Lvolpath: .asciz "/soc@03000000/gpio_keys/keyvol-"
.Lgpios: .asciz "gpios"
.Lmodel720: .asciz "rg34xxsp"
.Lmodelrgsp: .asciz "rgsp"
.Lmodel640: .asciz "rg35xxh"
.Lnextstart: .asciz "roc_next_start"
.Lnextmodel: .asciz "roc_next_model"
.Lsavedmodel: .asciz "roc_saved_model"
.Lactive: .asciz "roc_active_model"
.Lroute: .asciz "roc_boot_route"
.Lselector: .asciz "selector"
.Lonce: .asciz "start_once"
.Lsaved: .asciz "start_saved"
