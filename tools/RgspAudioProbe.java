import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioTrack;

/** Two seconds at -36 dBFS, additionally attenuated by STREAM_MUSIC. */
public final class RgspAudioProbe {
    public static void main(String[] args) throws Exception {
        final int rate = 48000;
        final int frames = rate * 2;
        short[] samples = new short[frames * 2];
        for (int i = 0; i < frames; i++) {
            double envelope = Math.min(1.0, Math.min(i, frames - 1 - i) / 960.0);
            short sample = (short) (500.0 * envelope *
                    Math.sin(2.0 * Math.PI * 440.0 * i / rate));
            samples[2 * i] = sample;
            samples[2 * i + 1] = sample;
        }
        AudioTrack track = new AudioTrack.Builder()
                .setAudioAttributes(new AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_MEDIA)
                        .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build())
                .setAudioFormat(new AudioFormat.Builder()
                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .setSampleRate(rate)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_STEREO).build())
                .setTransferMode(AudioTrack.MODE_STATIC)
                .setBufferSizeInBytes(samples.length * 2)
                .build();
        try {
            int written = track.write(samples, 0, samples.length);
            if (written != samples.length) {
                throw new IllegalStateException("Short write: " + written);
            }
            track.play();
            int head = 0;
            for (int i = 0; i < 14; i++) {
                Thread.sleep(250);
                head = track.getPlaybackHeadPosition();
                System.out.println("RGSP_AUDIO_HEAD=" + head);
                if (head >= frames) break;
            }
            if (head < frames) {
                throw new IllegalStateException("Playback did not drain: " + head);
            }
            System.out.println("RGSP_AUDIO_FRAMES_PASS=" + head);
            System.out.println("AUDIBLE_OUTPUT_REQUIRES_USER_CONFIRMATION");
        } finally {
            track.release();
        }
    }
}
