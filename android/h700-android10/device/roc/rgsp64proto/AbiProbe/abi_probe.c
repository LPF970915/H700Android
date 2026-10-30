#include <jni.h>
JNIEXPORT jint JNICALL Java_com_roc_h700_abiprobe_ProbeActivity_pointerBits(JNIEnv* env, jclass cls) {
    (void)env; (void)cls;
    return sizeof(void*) * 8;
}
