    /**
     * Bounded joystick fallback for the four ROC navigation windows only.
     * Ordinary applications retain SyntheticJoystickHandler's original path.
     * All events stay in this ViewRoot's input queue; nothing is injected globally.
     */
    final class RocJoystickGuard extends Handler {
        private static final int MSG_REPEAT = 1;
        private static final int MSG_DEADLINE = 2;
        private static final long INITIAL_REPEAT_MILLIS = 400;
        private static final long REPEAT_MILLIS = 160;
        private static final long MAX_SESSION_MILLIS = 10000;
        private static final int INVALID_AXIS = 2;
        private final ArrayList<Session> mSessions = new ArrayList<>();
        private final java.util.IdentityHashMap<KeyEvent, Delivery> mDeliveries =
                new java.util.IdentityHashMap<>();
        private long mContextBoundary = -1;

        RocJoystickGuard() {
            super(true);
        }

        private final class Session {
            final int deviceId;
            final int source;
            // X, Y, HAT_X, HAT_Y. A blocked channel needs its own neutral sample.
            final int[] values = new int[4];
            final boolean[] blocked = new boolean[4];
            final Held[] held = new Held[2];
            long lastSampleTime = -1;
            long boundary = -1;
            long epoch;
            Deadline deadline;
            Session(int id, int eventSource) {
                deviceId = id;
                source = eventSource;
            }
        }

        private final class Held {
            final Session session;
            final int dimension;
            final int channel;
            final long epoch;
            final long deadlineWhen;
            boolean deliveredDown;
            boolean deliveredUp;
            KeyEvent key;
            Held(Session owner, int dim, int axisChannel, KeyEvent event) {
                session = owner;
                dimension = dim;
                channel = axisChannel;
                epoch = owner.epoch;
                deadlineWhen = owner.deadline.when;
                key = event;
            }
        }

        private final class Delivery {
            final Held held;
            final int sequence;
            final int action;
            Delivery(Held owner, KeyEvent event) {
                held = owner;
                sequence = event.getSequenceNumber();
                action = event.getAction();
            }
        }

        private final class Deadline {
            final Session session;
            final long when;
            Deadline(Session owner, long end) {
                session = owner;
                when = end;
            }
        }

        private Session sessionFor(MotionEvent event) {
            for (int i = 0; i < mSessions.size(); i++) {
                Session session = mSessions.get(i);
                if (session.deviceId == event.getDeviceId()
                        && session.source == event.getSource()) {
                    return session;
                }
            }
            Session session = new Session(event.getDeviceId(), event.getSource());
            mSessions.add(session);
            return session;
        }

        private boolean contextAllowed() {
            return mAdded && mView != null && !mStopped && mAttachInfo.mHasWindowFocus
                    && mDisplay != null && mDisplay.isValid()
                    && mAttachInfo.mDisplayState == Display.STATE_ON;
        }

        private boolean devicePresent(Session session) {
            InputDevice device = InputDevice.getDevice(session.deviceId);
            return device != null && (device.getSources() & session.source) == session.source;
        }

        void process(MotionEvent event) {
            Session session = sessionFor(event);
            if (event.getActionMasked() == MotionEvent.ACTION_CANCEL) {
                stop(session, SystemClock.uptimeMillis());
                return;
            }
            if (event.getActionMasked() != MotionEvent.ACTION_MOVE) {
                return;
            }
            final int historySize = event.getHistorySize();
            for (int h = 0; h < historySize; h++) {
                update(session, event.getHistoricalEventTime(h), event.getMetaState(),
                        event.getHistoricalAxisValue(MotionEvent.AXIS_X, 0, h),
                        event.getHistoricalAxisValue(MotionEvent.AXIS_Y, 0, h),
                        event.getHistoricalAxisValue(MotionEvent.AXIS_HAT_X, 0, h),
                        event.getHistoricalAxisValue(MotionEvent.AXIS_HAT_Y, 0, h));
            }
            update(session, event.getEventTime(), event.getMetaState(),
                    event.getAxisValue(MotionEvent.AXIS_X),
                    event.getAxisValue(MotionEvent.AXIS_Y),
                    event.getAxisValue(MotionEvent.AXIS_HAT_X),
                    event.getAxisValue(MotionEvent.AXIS_HAT_Y));
        }

        private int axisState(float value) {
            if (Float.isNaN(value) || Float.isInfinite(value)) {
                return INVALID_AXIS;
            }
            return value >= 0.5f ? 1 : value <= -0.5f ? -1 : 0;
        }

        private boolean sampleTimeAllowed(Session session, long time, long now) {
            return time >= 0 && time <= now && time >= mContextBoundary
                    && time >= session.boundary && time >= session.lastSampleTime;
        }

        private void update(Session session, long time, int metaState,
                float x, float y, float hatX, float hatY) {
            final long now = SystemClock.uptimeMillis();
            // Reject impossible, stale or out-of-order samples before observing
            // any neutral. Rejected input cannot discharge a channel's debt.
            if (!sampleTimeAllowed(session, time, now)) {
                stop(session, now);
                return;
            }
            session.lastSampleTime = time;
            final boolean allowed = contextAllowed() && devicePresent(session);
            final int[] values = {axisState(x), axisState(y), axisState(hatX), axisState(hatY)};
            for (int channel = 0; channel < 4; channel++) {
                session.values[channel] = values[channel];
                if (values[channel] == 0) {
                    session.blocked[channel] = false;
                } else if (!allowed || values[channel] == INVALID_AXIS) {
                    session.blocked[channel] = true;
                }
            }
            if (!allowed) {
                stop(session, now);
                return;
            }
            if (session.deadline != null && now >= session.deadline.when) {
                stop(session, now);
                return;
            }

            // A malformed value cannot be treated as neutral or hand off its dimension.
            for (int dimension = 0; dimension < 2; dimension++) {
                if (values[dimension] == INVALID_AXIS
                        || values[dimension + 2] == INVALID_AXIS) {
                    if (values[dimension] != 0) session.blocked[dimension] = true;
                    if (values[dimension + 2] != 0) session.blocked[dimension + 2] = true;
                }
                // HAT owns an active dimension. A deflected stick cannot take over
                // merely because that HAT is released; the stick must visit neutral.
                if (eligible(session, dimension + 2) && values[dimension] != 0) {
                    session.blocked[dimension] = true;
                }
            }

            boolean anyEligible = false;
            for (int channel = 0; channel < 4; channel++) {
                anyEligible |= eligible(session, channel);
            }
            if (anyEligible && session.deadline == null) {
                final long start = Math.min(time, now);
                if (now - start >= MAX_SESSION_MILLIS) {
                    stop(session, now);
                    return;
                }
                session.deadline = new Deadline(session, start + MAX_SESSION_MILLIS);
                post(MSG_DEADLINE, session.deadline, session.deadline.when - now);
            }

            for (int dimension = 0; dimension < 2; dimension++) {
                final int channel = eligible(session, dimension + 2) ? dimension + 2
                        : eligible(session, dimension) ? dimension : -1;
                final int keyCode = channel < 0 ? KeyEvent.KEYCODE_UNKNOWN
                        : keyFor(dimension, session.values[channel]);
                Held old = session.held[dimension];
                if (old != null && (old.channel != channel || old.key.getKeyCode() != keyCode)) {
                    release(session, dimension, time, false);
                    old = null;
                }
                if (old == null && channel >= 0) {
                    KeyEvent key = new KeyEvent(time, time, KeyEvent.ACTION_DOWN, keyCode,
                            0, metaState, session.deviceId, 0, KeyEvent.FLAG_FALLBACK,
                            session.source);
                    Held held = new Held(session, dimension, channel, key);
                    session.held[dimension] = held;
                    enqueue(held, key);
                    post(MSG_REPEAT, held, INITIAL_REPEAT_MILLIS);
                }
            }
            if (!anyEligible) {
                clearDeadline(session);
            }
        }

        private boolean eligible(Session session, int channel) {
            return !session.blocked[channel]
                    && (session.values[channel] == -1 || session.values[channel] == 1);
        }

        private int keyFor(int dimension, int state) {
            return dimension == 0
                    ? (state < 0 ? KeyEvent.KEYCODE_DPAD_LEFT : KeyEvent.KEYCODE_DPAD_RIGHT)
                    : (state < 0 ? KeyEvent.KEYCODE_DPAD_UP : KeyEvent.KEYCODE_DPAD_DOWN);
        }

        private void post(int what, Object token, long delay) {
            Message message = obtainMessage(what, token);
            message.setAsynchronous(true);
            sendMessageDelayed(message, delay);
        }

        private void release(Session session, int dimension, long time, boolean canceled) {
            Held held = session.held[dimension];
            if (held == null) return;
            session.held[dimension] = null;
            removeMessages(MSG_REPEAT, held);
            KeyEvent old = held.key;
            enqueue(held, new KeyEvent(old.getDownTime(), Math.max(time, old.getDownTime()),
                    KeyEvent.ACTION_UP, old.getKeyCode(), 0, old.getMetaState(),
                    session.deviceId, 0, KeyEvent.FLAG_FALLBACK
                            | (canceled ? KeyEvent.FLAG_CANCELED : 0), session.source));
        }

        private void clearDeadline(Session session) {
            Deadline old = session.deadline;
            session.deadline = null;
            if (old != null) removeMessages(MSG_DEADLINE, old);
        }

        private void stop(Session session, long time) {
            session.boundary = Math.max(session.boundary, time);
            session.epoch++;
            clearDeadline(session);
            for (int dimension = 0; dimension < 2; dimension++) {
                release(session, dimension, time, true);
            }
            for (int channel = 0; channel < 4; channel++) {
                if (session.values[channel] != 0) session.blocked[channel] = true;
            }
        }

        private void enqueue(Held held, KeyEvent event) {
            mDeliveries.put(event, new Delivery(held, event));
            enqueueRocJoystickEvent(event);
        }

        boolean shouldBlockDelivery(KeyEvent event) {
            Delivery delivery = mDeliveries.get(event);
            if (delivery == null || delivery.sequence != event.getSequenceNumber()
                    || delivery.action != event.getAction()) return true;
            Held held = delivery.held;
            if (event.getAction() == KeyEvent.ACTION_UP) {
                if (held.deliveredUp) return true;
                held.deliveredUp = true;
                return !held.deliveredDown;
            }
            final long now = SystemClock.uptimeMillis();
            Session session = held.session;
            if (event.getAction() != KeyEvent.ACTION_DOWN || held.deliveredUp
                    || held.epoch != session.epoch || now >= held.deadlineWhen
                    || !contextAllowed() || !devicePresent(session)) {
                // A late event must not cancel a newer held key in this identity.
                if (session.held[held.dimension] == held && held.epoch == session.epoch) {
                    stop(session, now);
                }
                return true;
            }
            if (event.getRepeatCount() == 0) {
                if (held.deliveredDown) return true;
                held.deliveredDown = true;
            } else if (!held.deliveredDown) {
                return true;
            }
            return false;
        }

        void finishDelivery(KeyEvent event) {
            // Called before KeyEvent/QueuedInputEvent recycling, including events
            // consumed or dropped before reaching the post-IME gate.
            mDeliveries.remove(event);
        }

        // A prior stage consumed this identity only. Observe its current valid
        // MOVE so an unhandled continuation cannot pretend to be a fresh press.
        void cancel(MotionEvent event) {
            final long now = SystemClock.uptimeMillis();
            Session session = sessionFor(event);
            if (event.getActionMasked() == MotionEvent.ACTION_MOVE
                    && sampleTimeAllowed(session, event.getEventTime(), now)) {
                session.lastSampleTime = event.getEventTime();
                final int[] axes = {MotionEvent.AXIS_X, MotionEvent.AXIS_Y,
                        MotionEvent.AXIS_HAT_X, MotionEvent.AXIS_HAT_Y};
                for (int channel = 0; channel < 4; channel++) {
                    session.values[channel] = axisState(event.getAxisValue(axes[channel]));
                    if (session.values[channel] == 0) session.blocked[channel] = false;
                }
            }
            stop(session, now);
        }

        void cancel() {
            final long now = SystemClock.uptimeMillis();
            mContextBoundary = now;
            for (int i = 0; i < mSessions.size(); i++) {
                stop(mSessions.get(i), now);
            }
        }

        @Override
        public void handleMessage(Message message) {
            final long now = SystemClock.uptimeMillis();
            if (message.what == MSG_DEADLINE) {
                Deadline deadline = (Deadline) message.obj;
                if (deadline.session.deadline != deadline) return;
                stop(deadline.session, now);
            } else if (message.what == MSG_REPEAT) {
                Held held = (Held) message.obj;
                Session session = held.session;
                if (session.held[held.dimension] != held || session.deadline == null) return;
                if (!contextAllowed() || !devicePresent(session) || now >= session.deadline.when) {
                    stop(session, now);
                    return;
                }
                held.key = KeyEvent.changeTimeRepeat(held.key, now, held.key.getRepeatCount() + 1);
                enqueue(held, held.key);
                post(MSG_REPEAT, held, REPEAT_MILLIS);
            }
        }
    }
