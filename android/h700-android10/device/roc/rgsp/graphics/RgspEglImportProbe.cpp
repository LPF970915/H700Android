// Allocates temporary off-screen buffers and imports them without drawing or
// attaching anything to a display. This diagnostic is not installed in images.
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#include <hardware/gralloc.h>
#include <ui/GraphicBuffer.h>
#include <cstdio>
#include <cstring>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/mman.h>

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const bool es3 = !std::strcmp(argv[1], "--offscreen-es3") ||
                     !std::strcmp(argv[1], "--offscreen-es3-surfaceless");
    const bool surfaceless = !std::strcmp(argv[1], "--offscreen-es3-surfaceless");
    if (!es3 && std::strcmp(argv[1], "--offscreen-only")) return 2;
    EGLDisplay display = eglGetDisplay(EGL_DEFAULT_DISPLAY);
    EGLint major = 0, minor = 0;
    if (!eglInitialize(display, &major, &minor)) {
        std::printf("EGL_INIT_FAILED error=0x%x\n", eglGetError());
        return 3;
    }
    const EGLint attributes[] = {EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
        EGL_RENDERABLE_TYPE, es3 ? EGL_OPENGL_ES3_BIT_KHR : EGL_OPENGL_ES2_BIT, EGL_RED_SIZE, 8,
        EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_ALPHA_SIZE, 8, EGL_NONE};
    EGLConfig config;
    EGLint count = 0;
    if (!eglChooseConfig(display, attributes, &config, 1, &count) || count != 1) return 4;
    const EGLint contextAttributes[] = {EGL_CONTEXT_CLIENT_VERSION, es3 ? 3 : 2, EGL_NONE};
    const EGLint surfaceAttributes[] = {EGL_WIDTH, 1, EGL_HEIGHT, 1, EGL_NONE};
    EGLContext context = eglCreateContext(display, config, EGL_NO_CONTEXT, contextAttributes);
    EGLSurface surface = surfaceless ? EGL_NO_SURFACE : eglCreatePbufferSurface(display, config, surfaceAttributes);
    if (context == EGL_NO_CONTEXT || (!surfaceless && surface == EGL_NO_SURFACE) ||
            !eglMakeCurrent(display, surface, surface, context)) return 5;
    std::printf("CONTEXT mode=%s version=%s\n", argv[1], glGetString(GL_VERSION));
    auto createImage = reinterpret_cast<PFNEGLCREATEIMAGEKHRPROC>(eglGetProcAddress("eglCreateImageKHR"));
    auto destroyImage = reinterpret_cast<PFNEGLDESTROYIMAGEKHRPROC>(eglGetProcAddress("eglDestroyImageKHR"));
    auto bindImage = reinterpret_cast<PFNGLEGLIMAGETARGETTEXTURE2DOESPROC>(
        eglGetProcAddress("glEGLImageTargetTexture2DOES"));
    if (!createImage || !destroyImage || !bindImage) return 6;
    const uint64_t render = GRALLOC_USAGE_HW_RENDER | GRALLOC_USAGE_HW_COMPOSER;
    struct Scenario { const char* name; uint32_t width, height; uint64_t usage; };
    const Scenario cases[] = {
        {"current_client_target", 720, 480, render | GRALLOC_USAGE_HW_FB},
        {"without_hw_fb", 720, 480, render},
        {"texture_render_composer", 720, 480, render | GRALLOC_USAGE_HW_TEXTURE},
        {"aligned_width_current", 768, 480, render | GRALLOC_USAGE_HW_FB},
        {"portrait_current", 480, 720, render | GRALLOC_USAGE_HW_FB},
    };
    GLuint texture = 0, framebuffer = 0;
    glGenTextures(1, &texture);
    glGenFramebuffers(1, &framebuffer);
    for (const auto& test : cases) {
        android::sp<android::GraphicBuffer> buffer = new android::GraphicBuffer(
            test.width, test.height, HAL_PIXEL_FORMAT_RGBA_8888, 1, test.usage,
            "RGSP-offscreen-import-probe");
        auto status = buffer->initCheck();
        if (status != android::NO_ERROR) {
            std::printf("CASE %s alloc_status=%d\n", test.name, status);
            continue;
        }
        for (int index = 0; index < buffer->handle->numFds; index++) {
            const int fd = buffer->handle->data[index];
            struct stat info = {};
            char path[64], target[160] = {};
            std::snprintf(path, sizeof(path), "/proc/self/fd/%d", fd);
            const auto length = readlink(path, target, sizeof(target) - 1);
            if (length >= 0) target[length] = 0;
            if (fstat(fd, &info) == 0) {
                std::printf("FD %s index=%d size=%lld target=%s\n", test.name, index,
                    static_cast<long long>(info.st_size), target);
                if (info.st_size >= 128 && info.st_size <= 8192) {
                    void* metadata = mmap(nullptr, 128, PROT_READ, MAP_SHARED, fd, 0);
                    if (metadata != MAP_FAILED) {
                        std::printf("OWNED_METADATA %s index=%d", test.name, index);
                        for (int word = 0; word < 32; word++)
                            std::printf(" %08x", static_cast<unsigned int*>(metadata)[word]);
                        std::printf("\n");
                        munmap(metadata, 128);
                    }
                }
            }
        }
        for (int iteration = 0; iteration < 5; iteration++) {
        const EGLint imageAttributes[] = {EGL_NONE};
        EGLImageKHR image = createImage(display, EGL_NO_CONTEXT, EGL_NATIVE_BUFFER_ANDROID,
                                        buffer->getNativeBuffer(), imageAttributes);
        EGLint imageError = eglGetError();
        GLenum importError = GL_NO_ERROR, framebufferStatus = 0;
        if (image != EGL_NO_IMAGE_KHR) {
            glBindTexture(GL_TEXTURE_2D, texture);
            bindImage(GL_TEXTURE_2D, image);
            importError = glGetError();
            glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture, 0);
            framebufferStatus = glCheckFramebufferStatus(GL_FRAMEBUFFER);
            if (framebufferStatus == GL_FRAMEBUFFER_COMPLETE) {
                // Match RenderEngine's clear-before-viewport ordering. These
                // private buffers are never queued or presented to a display.
                glClearColor(0.125f, 0.25f, 0.5f, 1.0f);
                glClear(GL_COLOR_BUFFER_BIT);
                glViewport(0, 0, test.width, test.height);
                glFinish();
            }
            if (iteration == 0 && buffer->handle->numFds >= 2) {
                const int fd = buffer->handle->data[1];
                struct stat info = {};
                if (fstat(fd, &info) == 0 && info.st_size >= 128 && info.st_size <= 8192) {
                    void* metadata = mmap(nullptr, 128, PROT_READ, MAP_SHARED, fd, 0);
                    if (metadata != MAP_FAILED) {
                        std::printf("AFTER_PRIVATE_DRAW %s", test.name);
                        for (int word = 0; word < 32; word++)
                            std::printf(" %08x", static_cast<unsigned int*>(metadata)[word]);
                        std::printf("\n");
                        munmap(metadata, 128);
                    }
                }
            }
            glBindFramebuffer(GL_FRAMEBUFFER, 0);
            destroyImage(display, image);
        }
        std::printf("CASE %s iteration=%d width=%u height=%u stride=%u usage=0x%llx image=%d egl=0x%x gl=0x%x fbo=0x%x\n",
            test.name, iteration, buffer->getWidth(), buffer->getHeight(), buffer->getStride(),
            static_cast<unsigned long long>(test.usage), image != EGL_NO_IMAGE_KHR,
            imageError, importError, framebufferStatus);
        std::fflush(stdout);
        }
    }
    glDeleteFramebuffers(1, &framebuffer);
    glDeleteTextures(1, &texture);
    eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
    if (surface != EGL_NO_SURFACE) eglDestroySurface(display, surface);
    eglDestroyContext(display, context);
    eglTerminate(display);
    return 0;
}
