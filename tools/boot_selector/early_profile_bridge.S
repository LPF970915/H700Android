/* Actual pinned U-Boot early-display deferral bridge. Local references are
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
    bne .Lsafe_default
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
    adr.w r6,.Lonce
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
    str r4,[sp,#52]
    movs r4,#0
.Lvalidate_property:
    mov r0,r7
    mov r1,r8
    ldr r2,[sp,#52]
    add r3,sp,#48
    movs r12,#0
    str r12,[r3]
    bl roc_fdt_getprop
    cmp r0,#0
    beq .Lfallback
    ldr r1,[sp,#48]
    cmp r1,#4
    bne .Lfallback
    str r0,[sp,r4,lsl #2]
    ldr r2,[sp,#52]
.Lnext_property_name:
    ldrb r1,[r2],#1
    cmp r1,#0
    bne .Lnext_property_name
    str r2,[sp,#52]
    adds r4,#1
    cmp r4,#12
    bne .Lvalidate_property
    adr.w r2,.Lvalues720
    cmp r5,#1
    it eq
    adreq.w r2,.Lvalues640
    movs r4,#0
.Lwrite_property:
    ldr r0,[sp,r4,lsl #2]
    ldr r1,[r2,r4,lsl #2]
    rev r1,r1
    str r1,[r0]
    adds r4,#1
    cmp r4,#12
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

/* Only concrete retained electrical profiles are accepted in this test.
 * Do not collapse other catalogue models into a geometry bucket. */
.thumb_func
.Llookup:
    cmp r0,#0
    beq .Lunknown_leaf
    push {r4,lr}
    mov r4,r0
    adr.w r1,.Lmodel720
    bl .Lequal
    cmp r0,#1
    beq .Lfound720
    mov r0,r4
    adr.w r1,.Lmodelrgsp
    bl .Lequal
    cmp r0,#1
    beq .Lfoundrgsp
    mov r0,r4
    adr.w r1,.Lmodel640
    bl .Lequal
    cmp r0,#1
    beq .Lfound640
    movs r0,#0
    pop {r4,pc}
.Lfound720:
    adr.w r0,.Lmodel720
    movs r1,#0
    pop {r4,pc}
.Lfoundrgsp:
    adr.w r0,.Lmodelrgsp
    movs r1,#0
    pop {r4,pc}
.Lfound640:
    adr.w r0,.Lmodel640
    movs r1,#1
    pop {r4,pc}
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
.Lvalues720:
    .word 0,720,480,26,46,820,2,20,536,5,1,3
.Lvalues640:
    .word 1,640,480,24,46,770,20,15,520,4,2,3
.Lproperties:
    .asciz "roc_panel_profile","lcd_x","lcd_y","lcd_dclk_freq","lcd_hbp","lcd_ht","lcd_hspw","lcd_vbp","lcd_vt","lcd_vspw","lcd_hv_clk_phase","lcd_hv_sync_polarity"
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
