    // Only the four system-navigation packages use this guard. Games retain
    // the existing input stages. This state belongs to this ViewRoot only.
    private RocDpadKeyGuard mRocDpadKeyGuard;

    private boolean rocShouldBlockDpad(QueuedInputEvent q) {
        if (!isRocNavigationGuardEnabled()) return false;
        if (mRocDpadKeyGuard == null) mRocDpadKeyGuard = new RocDpadKeyGuard();
        return mRocDpadKeyGuard.shouldBlock(q);
    }

    private void rocCancelDpadForContext() {
        if (mRocDpadKeyGuard != null) mRocDpadKeyGuard.onContextLost();
    }

    private void rocFinishDpadInputEvent(QueuedInputEvent q) {
        if (mRocDpadKeyGuard != null) mRocDpadKeyGuard.onInputEventFinished(q);
    }

    final class RocDpadKeyGuard {
        private static final long SESSION_MS = 10000;
        private static final long FIRST_REPEAT_MS = 400;
        private static final long REPEAT_MS = 160;
        private final java.util.ArrayList<Stream> streams = new java.util.ArrayList<>();
        private final java.util.ArrayList<Release> releases = new java.util.ArrayList<>();
        private final java.util.ArrayList<Release> repeats = new java.util.ArrayList<>();
        private long boundary = -1;

        final class Press {
            final int code, scan;
            long downTime = -1, startTime = -1, lastTime = -1, generation;
            int repeatCount;
            boolean active, needsUp;
            KeyEvent template;
            Runnable repeatTask;
            Press(int code, int scan) { this.code = code; this.scan = scan; }
        }

        final class Stream {
            final int device, source;
            final java.util.ArrayList<Press> presses = new java.util.ArrayList<>();
            long deadline = -1, generation;
            boolean blocked;
            Runnable timeout;
            Stream(int device, int source) { this.device = device; this.source = source; }
        }

        final class Release {
            final Stream stream;
            final Press press;
            final long generation;
            final KeyEvent event;
            Release(Stream stream, Press press, KeyEvent event) {
                this.stream = stream; this.press = press;
                this.generation = press.generation; this.event = event;
            }
        }

        private boolean direction(int key) {
            return key == KeyEvent.KEYCODE_DPAD_UP || key == KeyEvent.KEYCODE_DPAD_DOWN
                    || key == KeyEvent.KEYCODE_DPAD_LEFT || key == KeyEvent.KEYCODE_DPAD_RIGHT;
        }

        private boolean live() {
            return mAdded && mView != null && !mStopped && mAttachInfo.mHasWindowFocus
                    && mDisplay != null && mDisplay.isValid()
                    && mDisplay.getState() == Display.STATE_ON;
        }

        private Stream stream(KeyEvent event) {
            for (Stream stream : streams) {
                if (stream.device == event.getDeviceId() && stream.source == event.getSource())
                    return stream;
            }
            Stream stream = new Stream(event.getDeviceId(), event.getSource());
            streams.add(stream);
            return stream;
        }

        private Press press(Stream stream, KeyEvent event) {
            for (Press press : stream.presses) {
                if (press.code == event.getKeyCode() && press.scan == event.getScanCode()) return press;
            }
            Press press = new Press(event.getKeyCode(), event.getScanCode());
            stream.presses.add(press);
            return press;
        }

        private boolean held(Stream stream) {
            for (Press press : stream.presses) if (press.active) return true;
            return false;
        }

        private boolean awaitingUp(Stream stream) {
            for (Press press : stream.presses) if (press.needsUp) return true;
            return false;
        }

        private void clearTimer(Stream stream) {
            if (stream.timeout != null) mHandler.removeCallbacks(stream.timeout);
            stream.timeout = null;
            stream.deadline = -1;
            stream.generation++;
        }

        private void schedule(final Stream stream, long firstEventTime) {
            clearTimer(stream);
            stream.deadline = firstEventTime + SESSION_MS;
            final long generation = stream.generation;
            stream.timeout = new Runnable() {
                @Override public void run() {
                    if (stream.generation != generation || stream.timeout != this) return;
                    if (!live()) { onContextLost(); return; }
                    if (SystemClock.uptimeMillis() >= stream.deadline) stop(stream, true);
                }
            };
            mHandler.postDelayed(stream.timeout,
                    Math.max(0, stream.deadline - SystemClock.uptimeMillis()));
        }

        private void release(Stream stream, Press press, boolean timeout) {
            if (!press.active) return;
            press.active = false;
            press.needsUp |= timeout;
            cancelRepeat(press);
            KeyEvent old = press.template;
            KeyEvent up = new KeyEvent(press.downTime, SystemClock.uptimeMillis(),
                    KeyEvent.ACTION_UP, press.code, 0, old.getMetaState(), stream.device,
                    press.scan, (old.getFlags() & ~KeyEvent.FLAG_LONG_PRESS)
                            | KeyEvent.FLAG_CANCELED, stream.source);
            releases.add(new Release(stream, press, up));
            // Private queue metadata distinguishes our balancing UP from a
            // physical release. It must never pay the physical-release debt.
            enqueueInputEvent(up, null, QueuedInputEvent.FLAG_ROC_DPAD_RELEASE, false);
            old.recycle();
            press.template = null;
        }

        private void stop(Stream stream, boolean timeout) {
            clearTimer(stream);
            for (Press press : stream.presses) release(stream, press, timeout);
            stream.blocked |= awaitingUp(stream);
        }

        void onContextLost() {
            boundary = SystemClock.uptimeMillis();
            for (Stream stream : streams) stop(stream, false);
        }

        private void cancelRepeat(Press press) {
            if (press.repeatTask != null) mHandler.removeCallbacks(press.repeatTask);
            press.repeatTask = null;
        }

        private void scheduleRepeat(final Stream stream, final Press press) {
            final long generation = press.generation;
            press.repeatTask = new Runnable() {
                @Override public void run() {
                    if (!press.active || press.generation != generation || press.repeatTask != this)
                        return;
                    if (!live()) { onContextLost(); return; }
                    final long now = SystemClock.uptimeMillis();
                    if (stream.deadline < 0 || now >= stream.deadline) { stop(stream, true); return; }
                    KeyEvent old = press.template;
                    KeyEvent repeat = new KeyEvent(press.downTime, now, KeyEvent.ACTION_DOWN,
                            press.code, ++press.repeatCount, old.getMetaState(), stream.device,
                            press.scan, old.getFlags() & ~KeyEvent.FLAG_LONG_PRESS, stream.source);
                    repeats.add(new Release(stream, press, repeat));
                    enqueueInputEvent(repeat, null, QueuedInputEvent.FLAG_ROC_DPAD_REPEAT, false);
                    mHandler.postDelayed(this, REPEAT_MS);
                }
            };
            mHandler.postDelayed(press.repeatTask,
                    Math.max(0, press.startTime + FIRST_REPEAT_MS - SystemClock.uptimeMillis()));
        }

        private boolean generatedRepeat(QueuedInputEvent q) {
            for (int i = 0; i < repeats.size(); i++) {
                Release repeat = repeats.get(i);
                if (repeat.event == q.mEvent) {
                    repeats.remove(i);
                    if (!live()) { onContextLost(); return true; }
                    if (!repeat.press.active || repeat.press.generation != repeat.generation)
                        return true;
                    // Delivery can be delayed after this event was queued.
                    // Recheck the absolute deadline, even before timeout runs.
                    if (repeat.stream.deadline < 0
                            || SystemClock.uptimeMillis() >= repeat.stream.deadline) {
                        stop(repeat.stream, true);
                        return true;
                    }
                    return false;
                }
            }
            return true;
        }

        private boolean balancingRelease(QueuedInputEvent q) {
            for (int i = 0; i < releases.size(); i++) {
                Release release = releases.get(i);
                if (release.event == q.mEvent) {
                    releases.remove(i);
                    // An older queued cancellation cannot release a newer DOWN.
                    return release.press.generation != release.generation || release.press.active;
                }
            }
            return true;
        }

        void onInputEventFinished(QueuedInputEvent q) {
            // An earlier input stage may consume/drop a private event before
            // shouldBlock() sees it. Forget its identity before the queue item
            // is recycled, without changing the physical-release debt.
            for (int i = releases.size() - 1; i >= 0; i--) {
                if (releases.get(i).event == q.mEvent) releases.remove(i);
            }
            for (int i = repeats.size() - 1; i >= 0; i--) {
                if (repeats.get(i).event == q.mEvent) repeats.remove(i);
            }
        }

        boolean shouldBlock(QueuedInputEvent q) {
            if ((q.mFlags & QueuedInputEvent.FLAG_ROC_DPAD_RELEASE) != 0)
                return balancingRelease(q);
            if ((q.mFlags & QueuedInputEvent.FLAG_ROC_DPAD_REPEAT) != 0)
                return generatedRepeat(q);
            KeyEvent event = (KeyEvent) q.mEvent;
            if (!direction(event.getKeyCode())) return false;
            // Only our joystick producer owns another bounded repeat session.
            // FLAG_FALLBACK alone also identifies keyboard/trackball fallbacks.
            if ((q.mFlags & QueuedInputEvent.FLAG_ROC_JOYSTICK_GUARDED) != 0) return false;
            if (event.getAction() != KeyEvent.ACTION_DOWN && event.getAction() != KeyEvent.ACTION_UP)
                return false;

            Stream stream = stream(event);
            Press press = press(stream, event);
            final long now = SystemClock.uptimeMillis();
            final long time = event.getEventTime();
            final long down = event.getDownTime();
            if (time < 0 || down < 0 || time > now || down > time || time < press.lastTime)
                return true;
            press.lastTime = time;

            if (!live()) {
                onContextLost();
                if (event.getAction() == KeyEvent.ACTION_DOWN) {
                    press.downTime = down;
                    press.startTime = time;
                    press.needsUp = true;
                    stream.blocked = true;
                } else if (!event.isCanceled() && time >= press.startTime) {
                    press.needsUp = false;
                    if (!awaitingUp(stream)) stream.blocked = false;
                }
                return true;
            }

            if (event.getAction() == KeyEvent.ACTION_UP) {
                // KeyboardInputMapper shares/refreshes downTime across keys.
                // A real release is identified by the channel and event order.
                if (time < press.startTime) return true;
                if (!event.isCanceled()) press.needsUp = false;
                if (!awaitingUp(stream)) stream.blocked = false;
                else stream.blocked = true;
                if (!press.active) return true;
                press.active = false;
                cancelRepeat(press);
                press.template.recycle();
                press.template = null;
                if (!held(stream)) clearTimer(stream);
                return false;
            }

            if (event.isCanceled() || time < boundary)
                return true;
            if (press.needsUp || stream.blocked) {
                press.needsUp = true;
                press.startTime = time;
                stream.blocked = true;
                return true;
            }
            if (stream.deadline >= 0 && now >= stream.deadline) {
                stop(stream, true);
                // This newly observed held direction also needs a real UP.
                // It may have arrived before the queued timeout callback.
                press.needsUp = true;
                press.startTime = time;
                stream.blocked = true;
                return true;
            }
            if (press.active) {
                // Hardware repeats can refresh downTime or arrive with repeat=0.
                // Only our bounded timer produces repeats; raw repeats are consumed.
                return true;
            }
            // A window must not adopt another window's already-running repeat.
            // InputDispatcher may count a second device's fresh initial DOWN
            // as a repeat; downTime==eventTime still identifies that fresh edge.
            if (event.getRepeatCount() != 0 && down != time) return true;
            if (time <= press.startTime || now - time >= SESSION_MS) return true;
            press.downTime = down;
            press.startTime = time;
            press.generation++;
            press.active = true;
            press.repeatCount = 0;
            press.template = new KeyEvent(event);
            if (stream.deadline < 0) schedule(stream, time);
            scheduleRepeat(stream, press);
            return false;
        }
    }

