// Bounded, self-owned SurfaceFlinger window; does not change display configuration.
#include <binder/ProcessState.h>
#include <gui/Surface.h>
#include <gui/SurfaceComposerClient.h>
#include <gui/SurfaceControl.h>
#include <EGL/egl.h>
#include <GLES2/gl2.h>
#include <cstdio>
#include <cstdlib>
#include <unistd.h>

using namespace android;
int main(int argc, char** argv) {
    setbuf(stdout, nullptr);
    const int seconds = argc == 2 ? atoi(argv[1]) : 10;
    if (seconds < 1 || seconds > 30) return 2;
    printf("WINDOW_PROBE_BITS=%zu\n", sizeof(void*) * 8);
    ProcessState::self()->startThreadPool();
    sp<SurfaceComposerClient> client = new SurfaceComposerClient;
    if (client->initCheck() != NO_ERROR) return 10;
    sp<SurfaceControl> control = client->createSurface(
        String8("H700-DualABI-WindowProbe"), 256, 192, PIXEL_FORMAT_RGBA_8888);
    if (!control || !control->isValid()) return 11;
    SurfaceComposerClient::Transaction transaction;
    if (transaction.setLayer(control, 100000).setPosition(control, 32, 32)
            .show(control).apply(true) != NO_ERROR) return 12;
    sp<Surface> window = control->getSurface();
    EGLDisplay display = eglGetDisplay(EGL_DEFAULT_DISPLAY);
    EGLint major = 0, minor = 0;
    if (!eglInitialize(display, &major, &minor)) return 20;
    EGLint attributes[] = {EGL_SURFACE_TYPE, EGL_WINDOW_BIT,
        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT, EGL_RED_SIZE, 8,
        EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_ALPHA_SIZE, 8, EGL_NONE};
    EGLConfig config; EGLint count = 0;
    if (!eglChooseConfig(display, attributes, &config, 1, &count) || count != 1) return 21;
    EGLint contextAttributes[] = {EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE};
    EGLContext context = eglCreateContext(display, config, EGL_NO_CONTEXT, contextAttributes);
    EGLSurface surface = eglCreateWindowSurface(display, config, window.get(), nullptr);
    if (context == EGL_NO_CONTEXT || surface == EGL_NO_SURFACE ||
            !eglMakeCurrent(display, surface, surface, context)) {
        printf("WINDOW_EGL_ERROR=0x%x\n", eglGetError()); return 22;
    }
    printf("WINDOW_RENDERER=%s EGL=%d.%d\n", glGetString(GL_RENDERER), major, minor);
    glViewport(0, 0, 256, 192);
    glClearColor(0, 1, 0, 1); glClear(GL_COLOR_BUFFER_BIT);
    unsigned char pixel[4] = {};
    glReadPixels(128, 96, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel);
    GLenum error = glGetError();
    printf("WINDOW_PIXEL=%u,%u,%u,%u GL_ERROR=0x%x\n", pixel[0], pixel[1], pixel[2], pixel[3], error);
    if (error || pixel[0] > 15 || pixel[1] < 240 || pixel[2] > 15) return 23;
    if (!eglSwapBuffers(display, surface)) return 24;
    puts("WINDOW_SWAP_OK");
    sleep(seconds);
    eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
    eglDestroySurface(display, surface); eglDestroyContext(display, context); eglTerminate(display);
    SurfaceComposerClient::Transaction().hide(control).apply(true);
    window.clear(); control.clear(); client->dispose(); client.clear();
    puts("WINDOW_CLEANUP_OK");
    // Binder worker threads are terminated with this process.
    return 0;
}
