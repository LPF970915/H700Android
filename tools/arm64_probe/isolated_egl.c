/* Isolated loader/EGL probe: 16x16 pbuffer only, no window or scanout. */
#include <stdio.h>
#include <string.h>
#include <dlfcn.h>
#include <EGL/egl.h>
#include <GLES2/gl2.h>
#ifdef DIRECT_MALI
#define LOAD(n) __typeof__(&n) p_##n = &n
#else
#define LOAD(n) __typeof__(&n) p_##n = (__typeof__(&n))dlsym(h, #n); \
    if (!p_##n) { printf("MISSING_SYMBOL %s %s\n", #n, dlerror()); return 12; }
#endif
int main(int argc, char **argv) {
    setbuf(stdout, NULL);
    printf("DYNAMIC_ANDROID_OK pointer_bits=%zu\n", sizeof(void*)*8);
    printf("ARGC %d\n", argc);
    for (int i=0;i<argc && i<8;i++) printf("ARGV %d %s\n",i,argv[i]);
    int base = argc > 1 && strstr(argv[0], "linker64") ? 2 : 1;
    if (argc <= base) return 0;
    void *h = 0;
#ifdef DIRECT_MALI
    printf("MALI_DT_NEEDED_STARTUP_OK\n");
#else
    h = dlopen(argv[base], RTLD_NOW | RTLD_LOCAL);
    if (!h) { printf("MALI_DLOPEN_FAILED %s\n", dlerror()); return 11; }
    printf("MALI_DLOPEN_OK\n");
#endif
    if (argc <= base+1 || strcmp(argv[base+1], "--egl")) { if (h) dlclose(h); return 0; }
    LOAD(eglGetDisplay); LOAD(eglInitialize); LOAD(eglGetError); LOAD(eglQueryString);
    LOAD(eglChooseConfig); LOAD(eglBindAPI); LOAD(eglCreateContext);
    LOAD(eglCreatePbufferSurface); LOAD(eglMakeCurrent); LOAD(eglDestroySurface);
    LOAD(eglDestroyContext); LOAD(eglTerminate);
    EGLDisplay d = p_eglGetDisplay(EGL_DEFAULT_DISPLAY);
    printf("EGL_GET_DISPLAY %p error=0x%x\n", d, p_eglGetError());
    EGLint major=0, minor=0;
    if (d == EGL_NO_DISPLAY || !p_eglInitialize(d, &major, &minor)) {
        printf("EGL_INITIALIZE_FAILED error=0x%x\n", p_eglGetError()); return 21;
    }
    printf("EGL_INITIALIZE_OK %d.%d vendor=%s\n", major, minor, p_eglQueryString(d, EGL_VENDOR));
    EGLint attrs[] = {EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,EGL_OPENGL_ES2_BIT,
        EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,8,EGL_NONE};
    EGLConfig config; EGLint count=0;
    if (!p_eglChooseConfig(d,attrs,&config,1,&count) || !count || !p_eglBindAPI(EGL_OPENGL_ES_API)) return 22;
    EGLint ctxattr[]={EGL_CONTEXT_CLIENT_VERSION,2,EGL_NONE}, surfattr[]={EGL_WIDTH,16,EGL_HEIGHT,16,EGL_NONE};
    EGLContext ctx=p_eglCreateContext(d,config,EGL_NO_CONTEXT,ctxattr);
    EGLSurface surf=p_eglCreatePbufferSurface(d,config,surfattr);
    if (ctx==EGL_NO_CONTEXT || surf==EGL_NO_SURFACE || !p_eglMakeCurrent(d,surf,surf,ctx)) {
        printf("EGL_PBUFFER_CONTEXT_FAILED error=0x%x\n",p_eglGetError()); return 23;
    }
    LOAD(glGetString); LOAD(glClearColor); LOAD(glClear); LOAD(glReadPixels); LOAD(glFinish); LOAD(glGetError);
    printf("GL_RENDERER %s\n", p_glGetString(GL_RENDERER));
    unsigned char pixel[4]={0};
    p_glClearColor(1,0,0,1);p_glClear(GL_COLOR_BUFFER_BIT);p_glFinish();
    p_glReadPixels(8,8,1,1,GL_RGBA,GL_UNSIGNED_BYTE,pixel);
    GLenum error=p_glGetError();
    printf("PIXEL_RED %u %u %u %u error=0x%x\n",pixel[0],pixel[1],pixel[2],pixel[3],error);
    int pass=error==GL_NO_ERROR && pixel[0]>240 && pixel[1]<15 && pixel[2]<15 && pixel[3]>240;
    p_eglMakeCurrent(d,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT);
    p_eglDestroySurface(d,surf);p_eglDestroyContext(d,ctx);p_eglTerminate(d);if (h) dlclose(h);
    printf("OFFSCREEN_READBACK_%s\n",pass?"PASS":"FAIL");return pass?0:24;
}
