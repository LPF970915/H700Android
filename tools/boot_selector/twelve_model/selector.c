/* Standalone initramfs fbdev/evdev model picker. No panel or block writer.
 * The caller must initialize the physical LCD before invoking this program.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <glob.h>
#include <limits.h>
#include <linux/fb.h>
#include <linux/input.h>
#include <poll.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#include "assets.h"

#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
#define MAX_INPUTS 16
#define MAX_FB_BYTES (128u*1024u*1024u)
#define LONG_HOLD_MS 10000u
#define FIRST_REPEAT_MS 450u
#define REPEAT_MS 140u

struct surface {
    uint8_t *memory;
    size_t length;
    unsigned width, height, xoffset, yoffset, virtual_width, virtual_height, stride, bpp, rotation;
    struct fb_bitfield red, green, blue, alpha;
};
struct state { unsigned model, focus; bool save, confirmed, unavailable_notice; };
static uint32_t available_mask=(1u<<MODEL_COUNT)-1;
enum action { LEFT, RIGHT, UP, DOWN, CONFIRM, ACTION_COUNT };
struct button { bool down, blocked; uint64_t pressed, next; };
struct input_source {
    int fd;
    struct button buttons[ACTION_COUNT];
    int hat_x, hat_y;
    bool dropped;
};

static void fail(const char *message) { fprintf(stderr, "roc-boot-selector: %s: %s\n", message, strerror(errno)); exit(2); }
static uint64_t now_ms(void) {
    struct timespec value;
    if (clock_gettime(CLOCK_MONOTONIC, &value)) fail("clock_gettime");
    return (uint64_t)value.tv_sec * 1000 + value.tv_nsec / 1000000;
}
static unsigned find_model(const char *id) {
    for (unsigned i = 0; i < MODEL_COUNT; ++i) if (!strcmp(models[i].id, id)) return i;
    fprintf(stderr, "Unknown model_id: %s\n", id); exit(2);
}
static void action(struct state *state, enum action event) {
    if (state->confirmed) return;
    if (event == UP) state->focus = (state->focus + 2) % 3;
    else if (event == DOWN) state->focus = (state->focus + 1) % 3;
    else if ((event == LEFT || event == RIGHT) && state->focus == 0) {
        state->model = (state->model + MODEL_COUNT + (event == LEFT ? -1 : 1)) % MODEL_COUNT;
        state->unavailable_notice=false;
    }
    else if ((event == LEFT || event == RIGHT) && state->focus == 1) state->save = !state->save;
    else if (event == CONFIRM) {
        if (state->focus == 0) state->focus = 1;
        else if (state->focus == 1) state->save = !state->save;
        else if(!(available_mask&(1u<<state->model))){state->unavailable_notice=true;state->focus=0;}
        else state->confirmed = true;
    }
}
static bool bitfield_ok(struct fb_bitfield field, unsigned bpp) {
    return !field.msb_right && field.length <= 8 && field.offset <= bpp && field.length <= bpp - field.offset;
}
static uint64_t mask(struct fb_bitfield field) { return field.length ? ((1ull << field.length) - 1) << field.offset : 0; }
static unsigned canvas_width(const struct surface *s) { return s->rotation==90?s->height:s->width; }
static unsigned canvas_height(const struct surface *s) { return s->rotation==90?s->width:s->height; }
static bool surface_valid(const struct surface *s) {
    if (!s->memory || (s->rotation!=0&&s->rotation!=90) || canvas_width(s)<640 || canvas_height(s)<480 || s->width > 4096 || s->height > 4096 ||
        (s->bpp != 16 && s->bpp != 24 && s->bpp != 32) || !s->length || s->length > MAX_FB_BYTES ||
        s->virtual_width < s->width || s->virtual_height < s->height ||
        s->xoffset > s->virtual_width - s->width || s->yoffset > s->virtual_height - s->height ||
        (uint64_t)s->virtual_width * (s->bpp / 8) > s->stride ||
        (uint64_t)s->stride * s->virtual_height > s->length ||
        !bitfield_ok(s->red,s->bpp) || !bitfield_ok(s->green,s->bpp) || !bitfield_ok(s->blue,s->bpp) || !bitfield_ok(s->alpha,s->bpp) ||
        !s->red.length || !s->green.length || !s->blue.length) return false;
    uint64_t r=mask(s->red),g=mask(s->green),b=mask(s->blue),a=mask(s->alpha);
    return !(r&g) && !(r&b) && !(g&b) && !(a&(r|g|b));
}
static uint32_t packed(const struct surface *s, bool white) {
    return (uint32_t)(mask(s->alpha) | (white ? mask(s->red)|mask(s->green)|mask(s->blue) : 0));
}
static void pixel(struct surface *s, int x, int y, bool white) {
    if (x < 0 || y < 0 || (unsigned)x >= canvas_width(s) || (unsigned)y >= canvas_height(s)) return;
    unsigned px=(unsigned)x,py=(unsigned)y;
    if(s->rotation==90){px=s->width-1-(unsigned)y;py=(unsigned)x;}
    size_t offset = ((size_t)py+s->yoffset)*s->stride + ((size_t)px+s->xoffset)*(s->bpp/8);
    uint32_t value = packed(s,white);
    for (unsigned b=0; b<s->bpp/8; ++b) s->memory[offset+b] = (uint8_t)(value>>(8*b));
}
static void rect(struct surface *s,int x,int y,int w,int h,bool white) {
    for(int row=0;row<h;++row) for(int col=0;col<w;++col) pixel(s,x+col,y+row,white);
}
static void frame(struct surface *s,int x,int y,int w,int h) {
    rect(s,x,y,w,2,true);rect(s,x,y+h-2,w,2,true);rect(s,x,y,2,h,true);rect(s,x+w-2,y,2,h,true);
}
static unsigned utf8(const char **cursor) {
    const unsigned char *p=(const unsigned char *)*cursor;
    unsigned result=*p++, remaining=0;
    if(result>=0xf0){result&=7;remaining=3;}else if(result>=0xe0){result&=15;remaining=2;}else if(result>=0xc0){result&=31;remaining=1;}
    while(remaining--){if((*p&0xc0)!=0x80)return '?';result=(result<<6)|(*p++&63);}
    *cursor=(const char *)p;return result;
}
static const struct glyph *glyph(unsigned codepoint) {
    for(unsigned i=0;i<ARRAY_COUNT(glyphs);++i)if(glyphs[i].codepoint==codepoint)return &glyphs[i];
    for(unsigned i=0;i<ARRAY_COUNT(glyphs);++i)if(glyphs[i].codepoint=='?')return &glyphs[i];
    abort();
}
static unsigned text_width(const char *text) {
    unsigned width=0;while(*text)width+=glyph(utf8(&text))->advance;return width;
}
static void text(struct surface *s,int x,int y,const char *value,bool white) {
    while(*value){const struct glyph *g=glyph(utf8(&value));for(unsigned row=0;row<40;++row)for(unsigned col=0;col<32;++col)
        if(g->rows[row]&(1u<<col))pixel(s,x+(int)col,y+(int)row,white);x+=(int)g->advance;}
}
static void render(struct surface *s,const struct state *state) {
    int ox=((int)canvas_width(s)-640)/2,oy=((int)canvas_height(s)-480)/2;
    const struct model *model=&models[state->model];
    rect(s,0,0,(int)canvas_width(s),(int)canvas_height(s),false);
    text(s,ox+40,oy+20,"选择你的机型",true);
    if(state->focus==0)frame(s,ox+32,oy+70,576,52);
    text(s,ox+48,oy+76,"←",true);text(s,ox+558,oy+76,"→",true);
    text(s,ox+(640-(int)text_width(model->label))/2,oy+76,model->label,true);
    text(s,ox+40,oy+138,"分辨率",true);text(s,ox+224,oy+138,model->geometry,true);
    text(s,ox+40,oy+182,"翻盖机型",true);text(s,ox+224,oy+182,model->lid?"是":"否",true);
    text(s,ox+40,oy+226,"摇杆",true);text(s,ox+224,oy+226,model->sticks==2?"双摇杆":model->sticks==1?"单摇杆":"无摇杆",true);
    if(state->focus==1)frame(s,ox+32,oy+286,576,48);
    frame(s,ox+44,oy+300,24,24);if(state->save)rect(s,ox+50,oy+306,12,12,true);
    text(s,ox+82,oy+290,"保存为启动默认，下次跳过此页",true);
    if(state->focus==2){rect(s,ox+40,oy+354,180,52,true);text(s,ox+54,oy+358,"启动系统",false);}
    else{frame(s,ox+40,oy+354,180,52);text(s,ox+54,oy+358,"启动系统",true);}
    text(s,ox+40,oy+420,state->unavailable_notice?"该机型尚未接入，请重新选择":"← → 切换机型   A 确认",true);
}
static struct surface open_fb(const char *path,int *fd,unsigned rotation) {
    struct fb_fix_screeninfo fixed;struct fb_var_screeninfo variable;
    *fd=open(path,O_RDWR|O_CLOEXEC|O_NOFOLLOW);if(*fd<0)fail("open framebuffer");
    if(ioctl(*fd,FBIOGET_FSCREENINFO,&fixed)||ioctl(*fd,FBIOGET_VSCREENINFO,&variable))fail("framebuffer info");
    if(fixed.type!=FB_TYPE_PACKED_PIXELS||fixed.visual!=FB_VISUAL_TRUECOLOR||variable.grayscale){errno=ENOTSUP;fail("unsupported framebuffer type");}
    struct surface s={.length=fixed.smem_len,.width=variable.xres,.height=variable.yres,
        .xoffset=variable.xoffset,.yoffset=variable.yoffset,.virtual_width=variable.xres_virtual,
        .virtual_height=variable.yres_virtual,.stride=fixed.line_length,.bpp=variable.bits_per_pixel,
        .red=variable.red,.green=variable.green,.blue=variable.blue,.alpha=variable.transp,.rotation=rotation};
    s.memory=(uint8_t *)1;if(!surface_valid(&s)){errno=EINVAL;fail("invalid framebuffer bounds/format");}
    s.memory=mmap(NULL,s.length,PROT_READ|PROT_WRITE,MAP_SHARED,*fd,0);if(s.memory==MAP_FAILED)fail("map framebuffer");
    return s;
}
static void save_result(const char *path,const struct state *state) {
    int fd=open(path,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600);if(fd<0)fail("create result");
    struct stat st;if(fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_nlink!=1){errno=EINVAL;fail("result is not a new regular file");}
    char buffer[256];int count=snprintf(buffer,sizeof(buffer),"{\"schema\":2,\"model_id\":\"%s\",\"save_default\":%s}\n",models[state->model].id,state->save?"true":"false");
    if(count<0||(size_t)count>=sizeof(buffer)){errno=EOVERFLOW;fail("result overflow");}
    size_t offset=0;while(offset<(size_t)count){ssize_t written=write(fd,buffer+offset,(size_t)count-offset);if(written<0&&errno==EINTR)continue;if(written<=0)fail("write result");offset+=(size_t)written;}
    if(fsync(fd)||close(fd))fail("finish result");
}
static bool press(struct input_source *source,enum action event,bool down,uint64_t time,struct state *state) {
    struct button *button=&source->buttons[event];
    if(!down){button->down=false;button->blocked=false;return false;}
    if(button->down)return false;
    button->down=true;button->pressed=time;button->next=time+FIRST_REPEAT_MS;
    if(button->blocked)return false;
    action(state,event);return true;
}
static void block_source(struct input_source *source) {
    for(unsigned i=0;i<ACTION_COUNT;++i){source->buttons[i].down=false;source->buttons[i].blocked=true;}
    source->hat_x=source->hat_y=0;
}
static int key_action(unsigned code) {
    if(code==KEY_LEFT||code==BTN_DPAD_LEFT)return LEFT;if(code==KEY_RIGHT||code==BTN_DPAD_RIGHT)return RIGHT;
    if(code==KEY_UP||code==BTN_DPAD_UP)return UP;if(code==KEY_DOWN||code==BTN_DPAD_DOWN)return DOWN;
    if(code==BTN_SOUTH||code==KEY_ENTER||code==KEY_A)return CONFIRM;return -1;
}
static bool repeat_input(struct input_source *source,uint64_t time,struct state *state) {
    bool changed=false;
    for(unsigned e=0;e<ACTION_COUNT;++e){struct button *b=&source->buttons[e];if(!b->down||b->blocked||e==CONFIRM)continue;
        if(time-b->pressed>=LONG_HOLD_MS){b->blocked=true;continue;}
        if(time>=b->next){action(state,(enum action)e);b->next=time+REPEAT_MS;changed=true;}}
    return changed;
}
static bool event_input(struct input_source *source,const struct input_event *event,uint64_t time,struct state *state) {
    if(event->type==EV_SYN&&event->code==SYN_DROPPED){block_source(source);source->dropped=true;return false;}
    if(source->dropped){if(event->type==EV_SYN&&event->code==SYN_REPORT)source->dropped=false;return false;}
    if(event->type==EV_KEY){int which=key_action(event->code);if(which>=0&&event->value!=2)return press(source,(enum action)which,event->value==1,time,state);}
    if(event->type==EV_ABS&&(event->code==ABS_HAT0X||event->code==ABS_HAT0Y)) {
        int value=event->value<0?-1:event->value>0?1:0;
        bool changed=false;int *axis=event->code==ABS_HAT0X?&source->hat_x:&source->hat_y;
        enum action negative=event->code==ABS_HAT0X?LEFT:UP,positive=event->code==ABS_HAT0X?RIGHT:DOWN;
        if(value!=*axis){changed|=press(source,negative,value<0,time,state);changed|=press(source,positive,value>0,time,state);*axis=value;}
        else if(!value){press(source,negative,false,time,state);press(source,positive,false,time,state);}
        return changed;
    }
    return false;
}
/* Only a fresh press accepted by the existing input guards ends idle waiting.
 * Releases, kernel repeats, startup-held controls and dropped frames do not.
 */
static bool wait_input(struct input_source *source,const struct input_event *event,uint64_t time,struct state *state,bool *interacted) {
    bool accepted=event_input(source,event,time,state);
    if(accepted)*interacted=true;
    return accepted;
}
static bool idle_timeout(bool interacted,uint64_t start,uint64_t time,unsigned timeout) {
    return !interacted && time-start>=(uint64_t)timeout*1000;
}
static void initialize_source(struct input_source *source) {
    unsigned long keys[(KEY_MAX+8*sizeof(unsigned long))/(8*sizeof(unsigned long))];
    memset(keys,0,sizeof(keys));
    if(ioctl(source->fd,EVIOCGKEY(sizeof(keys)),keys)>=0)for(unsigned code=0;code<=KEY_MAX;++code){int which=key_action(code);if(which>=0&&(keys[code/(8*sizeof(unsigned long))]&(1ul<<(code%(8*sizeof(unsigned long)))))){source->buttons[which].down=true;source->buttons[which].blocked=true;}}
    for(unsigned i=0;i<2;++i){struct input_absinfo info;if(ioctl(source->fd,EVIOCGABS(i?ABS_HAT0Y:ABS_HAT0X),&info)>=0){int value=info.value<0?-1:info.value>0?1:0;int which=value<0?(i?UP:LEFT):(i?DOWN:RIGHT);if(i)source->hat_y=value;else source->hat_x=value;if(value){source->buttons[which].down=true;source->buttons[which].blocked=true;}}}
}
static int runtime(const char *fb_path,const char *input_pattern,const char *result,const char *initial,unsigned timeout,unsigned rotation) {
    int fb_fd;struct surface surface=open_fb(fb_path,&fb_fd,rotation);
    struct state state={.model=find_model(initial)};
    glob_t paths;memset(&paths,0,sizeof(paths));if(glob(input_pattern,GLOB_NOSORT,NULL,&paths)){errno=ENOENT;fail("no input devices");}
    struct pollfd pollfds[MAX_INPUTS];struct input_source sources[MAX_INPUTS];unsigned count=0;
    memset(sources,0,sizeof(sources));
    for(size_t i=0;i<paths.gl_pathc&&count<MAX_INPUTS;++i){int fd=open(paths.gl_pathv[i],O_RDONLY|O_NONBLOCK|O_CLOEXEC|O_NOFOLLOW);if(fd<0)continue;sources[count].fd=fd;initialize_source(&sources[count]);pollfds[count]=(struct pollfd){.fd=fd,.events=POLLIN};++count;}
    globfree(&paths);if(!count){errno=ENOENT;fail("open input devices");}
    uint64_t start=now_ms();bool interacted=false;render(&surface,&state);
    while(!state.confirmed){bool redraw=false;
        int rc=poll(pollfds,count,40);if(rc<0&&errno!=EINTR)fail("poll input");
        uint64_t time=now_ms();
        for(unsigned i=0;i<count;++i){if(pollfds[i].revents&(POLLERR|POLLHUP|POLLNVAL)){block_source(&sources[i]);pollfds[i].fd=-1;continue;}
            if(pollfds[i].revents&POLLIN){struct input_event events[32];ssize_t bytes;while((bytes=read(sources[i].fd,events,sizeof(events)))>0){if(bytes%(ssize_t)sizeof(events[0])){errno=EPROTO;fail("partial evdev event");}for(size_t j=0;j<(size_t)bytes/sizeof(events[0]);++j)redraw|=wait_input(&sources[i],&events[j],time,&state,&interacted);}}
            redraw|=repeat_input(&sources[i],time,&state);
        }
        /* A ready press wins over the idle deadline in this poll iteration. */
        if(idle_timeout(interacted,start,now_ms(),timeout)){fprintf(stderr,"roc-boot-selector: no accepted input before timeout\n");for(unsigned i=0;i<count;++i)close(sources[i].fd);munmap(surface.memory,surface.length);close(fb_fd);return 3;}
        if(redraw)render(&surface,&state);
    }
    save_result(result,&state);for(unsigned i=0;i<count;++i)close(sources[i].fd);munmap(surface.memory,surface.length);close(fb_fd);return 0;
}
static struct surface simulation_surface(unsigned width,unsigned height,unsigned bpp,unsigned xoffset,unsigned yoffset) {
    unsigned bytes=bpp/8,stride=(width+xoffset+3)*bytes+12;
    struct surface s={.width=width,.height=height,.bpp=bpp,.xoffset=xoffset,.yoffset=yoffset,.virtual_width=width+xoffset+3,.virtual_height=height*2+yoffset,.stride=stride,.rotation=(width==480&&height==640)?90:0};
    s.length=(size_t)stride*s.virtual_height;s.memory=malloc(s.length);if(!s.memory)fail("malloc simulation");memset(s.memory,0xa5,s.length);
    if(bpp==16){s.red=(struct fb_bitfield){11,5,0};s.green=(struct fb_bitfield){5,6,0};s.blue=(struct fb_bitfield){0,5,0};}
    else{s.red=(struct fb_bitfield){16,8,0};s.green=(struct fb_bitfield){8,8,0};s.blue=(struct fb_bitfield){0,8,0};if(bpp==32)s.alpha=(struct fb_bitfield){24,8,0};}
    if(!surface_valid(&s)){errno=EINVAL;fail("simulation surface");}return s;
}
static void ppm(const char *path,const struct surface *s) {
    FILE *out=fopen(path,"wbx");if(!out)fail("create simulation PPM");fprintf(out,"P6\n%u %u\n255\n",s->width,s->height);
    for(unsigned y=0;y<s->height;++y)for(unsigned x=0;x<s->width;++x){size_t offset=(size_t)(y+s->yoffset)*s->stride+(size_t)(x+s->xoffset)*(s->bpp/8);uint32_t raw=0;for(unsigned b=0;b<s->bpp/8;++b)raw|=(uint32_t)s->memory[offset+b]<<(8*b);struct fb_bitfield fields[]={s->red,s->green,s->blue};for(unsigned c=0;c<3;++c){unsigned value=(raw>>fields[c].offset)&((1u<<fields[c].length)-1);fputc((int)(value*255/((1u<<fields[c].length)-1)),out);}}
    if(fclose(out))fail("finish PPM");
}
static bool padding_untouched(const struct surface *s) {
    for(unsigned y=0;y<s->virtual_height;++y)for(unsigned x=0;x<s->stride;++x){bool visible=y>=s->yoffset&&y<s->yoffset+s->height&&x>=s->xoffset*(s->bpp/8)&&x<(s->xoffset+s->width)*(s->bpp/8);if(!visible&&s->memory[(size_t)y*s->stride+x]!=0xa5)return false;}return true;
}
static int selftest(void) {
    unsigned checks=0;struct state state={.model=find_model(DEFAULT_MODEL_ID)};
#define CHECK(value) do{++checks;if(!(value)){fprintf(stderr,"selftest failure line %u\n",__LINE__);return 1;}}while(0)
    state.model=0;action(&state,LEFT);CHECK(state.model==MODEL_COUNT-1);action(&state,RIGHT);CHECK(state.model==0);
    for(unsigned i=0;i<MODEL_COUNT;++i){CHECK(models[i].lid==(i==1||i==2||i==10));CHECK(text_width(models[i].label)<=460);}
    action(&state,DOWN);CHECK(state.focus==1);action(&state,CONFIRM);CHECK(state.save);action(&state,DOWN);action(&state,CONFIRM);CHECK(state.confirmed);
    for(unsigned geometry=0;geometry<3;++geometry)for(unsigned bpp=16;bpp<=32;bpp+=8){unsigned width=geometry?720:640,height=geometry==2?720:480;struct surface s=simulation_surface(width,height,bpp,7,9);state=(struct state){.model=1};render(&s,&state);CHECK(padding_untouched(&s));CHECK(surface_valid(&s));s.red.offset=s.bpp;CHECK(!surface_valid(&s));free(s.memory);}
    /* Native portrait 28XX output: asymmetric logical marks, physical stride,
     * offsets, clipping and untouched padding are checked independently. */
    for(unsigned bpp=16;bpp<=32;bpp+=8){
        struct surface s=simulation_surface(480,640,bpp,7,9);
        CHECK(canvas_width(&s)==640&&canvas_height(&s)==480);CHECK(surface_valid(&s));
        rect(&s,0,0,640,480,false);
        const unsigned marks[][2]={{13,27},{511,77},{620,450}};
        for(unsigned mark=0;mark<ARRAY_COUNT(marks);++mark)pixel(&s,(int)marks[mark][0],(int)marks[mark][1],true);
        for(unsigned py=0;py<640;++py)for(unsigned px=0;px<480;++px){
            bool white=false;for(unsigned mark=0;mark<ARRAY_COUNT(marks);++mark)
                if(px==479-marks[mark][1]&&py==marks[mark][0])white=true;
            size_t offset=((size_t)py+9)*s.stride+((size_t)px+7)*(bpp/8);
            uint32_t expected=packed(&s,white),actual=0;
            for(unsigned b=0;b<bpp/8;++b)actual|=(uint32_t)s.memory[offset+b]<<(8*b);
            CHECK(actual==expected);
        }
        CHECK(padding_untouched(&s));uint8_t *before=malloc(s.length);CHECK(before!=NULL);
        memcpy(before,s.memory,s.length);pixel(&s,-1,0,true);pixel(&s,0,-1,true);
        pixel(&s,640,0,true);pixel(&s,0,480,true);CHECK(!memcmp(before,s.memory,s.length));
        CHECK(padding_untouched(&s));free(before);
        state=(struct state){.model=find_model("rg28xx")};render(&s,&state);
        CHECK(padding_untouched(&s));s.rotation=180;CHECK(!surface_valid(&s));
        s.rotation=0;CHECK(!surface_valid(&s));free(s.memory);
    }
    state=(struct state){0};struct input_source source={0};
    CHECK(press(&source,RIGHT,true,0,&state));CHECK(state.model==1);CHECK(!press(&source,RIGHT,true,1,&state));CHECK(state.model==1);press(&source,RIGHT,false,2,&state);CHECK(press(&source,RIGHT,true,3,&state));CHECK(state.model==2);
    block_source(&source);CHECK(!press(&source,RIGHT,true,4,&state));CHECK(state.model==2);press(&source,RIGHT,false,5,&state);CHECK(press(&source,RIGHT,true,6,&state));CHECK(state.model==3);
    struct input_event lost={.type=EV_SYN,.code=SYN_DROPPED};event_input(&source,&lost,7,&state);struct input_event fake={.type=EV_KEY,.code=KEY_RIGHT,.value=1};CHECK(!event_input(&source,&fake,8,&state));CHECK(state.model==3);
    struct input_event sync={.type=EV_SYN,.code=SYN_REPORT};event_input(&source,&sync,9,&state);CHECK(!event_input(&source,&fake,10,&state));CHECK(state.model==3);
    fake.value=0;event_input(&source,&fake,11,&state);fake.value=1;CHECK(event_input(&source,&fake,12,&state));CHECK(state.model==4);
    state=(struct state){0};source=(struct input_source){0};press(&source,RIGHT,true,0,&state);CHECK(!repeat_input(&source,449,&state));CHECK(state.model==1);CHECK(repeat_input(&source,450,&state));CHECK(state.model==2);CHECK(!repeat_input(&source,500,&state));CHECK(!repeat_input(&source,10000,&state));CHECK(source.buttons[RIGHT].blocked);CHECK(!repeat_input(&source,20000,&state));press(&source,RIGHT,false,20001,&state);CHECK(press(&source,RIGHT,true,20002,&state));CHECK(state.model==3);
    state=(struct state){.model=find_model("rg35xxh"),.focus=2};uint32_t previous_mask=available_mask;available_mask=0;action(&state,CONFIRM);CHECK(!state.confirmed&&state.unavailable_notice&&state.focus==0);available_mask=previous_mask;
    CHECK(key_action(BTN_DPAD_UP)==UP);CHECK(key_action(BTN_DPAD_DOWN)==DOWN);CHECK(key_action(BTN_DPAD_LEFT)==LEFT);CHECK(key_action(BTN_DPAD_RIGHT)==RIGHT);CHECK(key_action(KEY_A)==CONFIRM);CHECK(key_action(BTN_SOUTH)==CONFIRM);
    const char *required="该机型尚未接入，请重新选择";while(*required){unsigned codepoint=utf8(&required);CHECK(glyph(codepoint)->codepoint==codepoint);}
    unsigned timeout_check_start=checks;bool interacted=false;
    state=(struct state){.model=find_model(DEFAULT_MODEL_ID)};source=(struct input_source){0};
    CHECK(!idle_timeout(interacted,1000,1000,5));CHECK(!idle_timeout(interacted,1000,5999,5));CHECK(idle_timeout(interacted,1000,6000,5));CHECK(idle_timeout(interacted,1000,6001,5));CHECK(!state.confirmed);
    struct input_event input={.type=EV_SYN,.code=SYN_REPORT};
    CHECK(!wait_input(&source,&input,6000,&state,&interacted));CHECK(!interacted);
    input=(struct input_event){.type=EV_ABS,.code=ABS_X,.value=1};CHECK(!wait_input(&source,&input,6000,&state,&interacted));CHECK(!interacted);
    input=(struct input_event){.type=EV_KEY,.code=KEY_RIGHT,.value=2};CHECK(!wait_input(&source,&input,6000,&state,&interacted));CHECK(!interacted);
    input.value=0;CHECK(!wait_input(&source,&input,6000,&state,&interacted));CHECK(!interacted);CHECK(idle_timeout(interacted,1000,6000,5));
    /* Processing this poll's accepted press first must defeat the same deadline. */
    input.value=1;CHECK(wait_input(&source,&input,6000,&state,&interacted));CHECK(interacted);CHECK(!idle_timeout(interacted,1000,6000,5));CHECK(!idle_timeout(interacted,1000,3601000,5));CHECK(!state.confirmed);
    CHECK(!wait_input(&source,&input,6001,&state,&interacted));CHECK(interacted);input.value=0;CHECK(!wait_input(&source,&input,6002,&state,&interacted));CHECK(interacted);
    interacted=false;state=(struct state){0};source=(struct input_source){0};source.buttons[RIGHT].down=true;source.buttons[RIGHT].blocked=true;
    input.value=1;CHECK(!wait_input(&source,&input,6000,&state,&interacted));input.value=2;CHECK(!wait_input(&source,&input,6001,&state,&interacted));CHECK(!repeat_input(&source,6002,&state));CHECK(!interacted);CHECK(idle_timeout(interacted,1000,6002,5));
    input.value=0;CHECK(!wait_input(&source,&input,6003,&state,&interacted));CHECK(!interacted);input.value=1;CHECK(wait_input(&source,&input,6004,&state,&interacted));CHECK(interacted);CHECK(!idle_timeout(interacted,1000,3601000,5));
    interacted=false;state=(struct state){0};source=(struct input_source){0};
    input=(struct input_event){.type=EV_SYN,.code=SYN_DROPPED};CHECK(!wait_input(&source,&input,6000,&state,&interacted));input=(struct input_event){.type=EV_KEY,.code=KEY_RIGHT,.value=1};CHECK(!wait_input(&source,&input,6001,&state,&interacted));CHECK(!interacted);
    input=(struct input_event){.type=EV_SYN,.code=SYN_REPORT};CHECK(!wait_input(&source,&input,6002,&state,&interacted));input=(struct input_event){.type=EV_KEY,.code=KEY_RIGHT,.value=1};CHECK(!wait_input(&source,&input,6003,&state,&interacted));CHECK(!interacted);CHECK(idle_timeout(interacted,1000,6003,5));
    input.value=0;CHECK(!wait_input(&source,&input,6004,&state,&interacted));CHECK(!interacted);input.value=1;CHECK(wait_input(&source,&input,6005,&state,&interacted));CHECK(interacted);CHECK(!idle_timeout(interacted,1000,3601000,5));
    interacted=false;state=(struct state){0};source=(struct input_source){0};source.hat_y=-1;source.buttons[UP].down=true;source.buttons[UP].blocked=true;
    input=(struct input_event){.type=EV_ABS,.code=ABS_HAT0Y,.value=-1};CHECK(!wait_input(&source,&input,6000,&state,&interacted));input.value=0;CHECK(!wait_input(&source,&input,6001,&state,&interacted));CHECK(!interacted);CHECK(idle_timeout(interacted,1000,6001,5));input.value=1;CHECK(wait_input(&source,&input,6002,&state,&interacted));CHECK(interacted);CHECK(state.focus==1);CHECK(!state.confirmed);
    /* Redraw caused by a repeat is not an accepted new user operation. */
    interacted=false;state=(struct state){0};source=(struct input_source){0};press(&source,RIGHT,true,0,&state);CHECK(repeat_input(&source,450,&state));CHECK(!interacted);CHECK(idle_timeout(interacted,0,5000,5));
    interacted=false;state=(struct state){.focus=2};source=(struct input_source){0};input=(struct input_event){.type=EV_KEY,.code=KEY_LEFT,.value=1};CHECK(wait_input(&source,&input,6000,&state,&interacted));CHECK(interacted);CHECK(state.focus==2&&!state.confirmed);CHECK(!idle_timeout(interacted,1000,3601000,5));
    struct input_source second_source={0};input=(struct input_event){.type=EV_KEY,.code=BTN_SOUTH,.value=1};CHECK(wait_input(&second_source,&input,3601000,&state,&interacted));CHECK(interacted);CHECK(state.confirmed);
    printf("{\"pass\":true,\"checks\":%u,\"timeout_checks\":%u,\"models\":%zu,\"hardware_io\":false}\n",checks,checks-timeout_check_start,(size_t)MODEL_COUNT);return 0;
}
static void usage(void) { fprintf(stderr,"Usage: roc-boot-selector --fb /dev/fb0 --input-directory /dev/input --output /run/new-result.json [--initial-model model_id] [--available-models id,id] [--timeout 300] [--rotation 0|90]\n       roc-boot-selector --simulate WxH --ppm new.ppm [--initial-model model_id] [--script LRDDA... ] [--output new.json]\n       roc-boot-selector --selftest\n"); }
int main(int argc,char **argv) {
    const char *fb="/dev/fb0",*inputs="/dev/input/event*",*result=NULL,*initial=DEFAULT_MODEL_ID,*geometry=NULL,*out_ppm=NULL,*script="";unsigned timeout=300,rotation=0;char pattern[PATH_MAX];
    for(int i=1;i<argc;++i){if(!strcmp(argv[i],"--selftest"))return selftest();if(i+1>=argc){usage();return 2;}const char *value=argv[++i];
        if(!strcmp(argv[i-1],"--fb"))fb=value;else if(!strcmp(argv[i-1],"--inputs"))inputs=value;
        else if(!strcmp(argv[i-1],"--input-directory")){int bytes=snprintf(pattern,sizeof(pattern),"%s/event*",value);if(bytes<0||(size_t)bytes>=sizeof(pattern)){usage();return 2;}inputs=pattern;}
        else if(!strcmp(argv[i-1],"--result")||!strcmp(argv[i-1],"--output"))result=value;
        else if(!strcmp(argv[i-1],"--initial")||!strcmp(argv[i-1],"--initial-model"))initial=value;
        else if(!strcmp(argv[i-1],"--available-models")){char *copy=strdup(value),*saveptr=NULL;if(!copy)fail("copy available models");available_mask=0;for(char *id=strtok_r(copy,",",&saveptr);id;id=strtok_r(NULL,",",&saveptr))available_mask|=1u<<find_model(id);free(copy);if(!available_mask){usage();return 2;}}
        else if(!strcmp(argv[i-1],"--rotation")){if(!strcmp(value,"0"))rotation=0;else if(!strcmp(value,"90"))rotation=90;else{usage();return 2;}}
        else if(!strcmp(argv[i-1],"--simulate"))geometry=value;else if(!strcmp(argv[i-1],"--ppm"))out_ppm=value;else if(!strcmp(argv[i-1],"--script"))script=value;else if(!strcmp(argv[i-1],"--timeout")){char *end;unsigned long parsed=strtoul(value,&end,10);if(*end||parsed<5||parsed>3600){usage();return 2;}timeout=(unsigned)parsed;}else{usage();return 2;}}
    if(geometry){unsigned width,height;char extra;if(sscanf(geometry,"%ux%u%c",&width,&height,&extra)!=2||!((width==640&&height==480)||(width==480&&height==640)||(width==720&&(height==480||height==720)))||!out_ppm){usage();return 2;}struct surface s=simulation_surface(width,height,32,3,7);struct state state={.model=find_model(initial)};for(const char *p=script;*p;++p){const char *valid=strchr("LRUDA",*p);if(!valid){usage();return 2;}action(&state,(enum action)(valid-"LRUDA"));}render(&s,&state);ppm(out_ppm,&s);if(result){if(!state.confirmed){fprintf(stderr,"simulate result requires explicit start confirmation\n");return 3;}save_result(result,&state);}bool intact=padding_untouched(&s);free(s.memory);if(!intact){errno=EFAULT;fail("simulation changed padding");}return 0;}
    if(!result){usage();return 2;}return runtime(fb,inputs,result,initial,timeout,rotation);
}
