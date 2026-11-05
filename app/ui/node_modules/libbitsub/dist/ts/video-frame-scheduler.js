const defaultAnimationFrameScheduler = {
    request: (callback) => requestAnimationFrame(callback),
    cancel: (handle) => cancelAnimationFrame(handle)
};
export function supportsFrameAwareSync(video, enabled = true) {
    return enabled && typeof video.requestVideoFrameCallback === 'function';
}
/**
 * Schedule one callback per presented video frame when possible, with an
 * animation-frame/currentTime compatibility fallback.
 */
export class VideoFrameScheduler {
    video;
    onFrame;
    animationFrames;
    animationFrameHandle = null;
    videoFrameHandle = null;
    generation = 0;
    useVideoFrames;
    constructor(video, frameAware, onFrame, animationFrames = defaultAnimationFrameScheduler) {
        this.video = video;
        this.onFrame = onFrame;
        this.animationFrames = animationFrames;
        this.useVideoFrames = supportsFrameAwareSync(video, frameAware);
    }
    get mode() {
        return this.useVideoFrames ? 'video-frame' : 'animation-frame';
    }
    start() {
        this.stop();
        const generation = this.generation;
        this.schedule(generation);
    }
    stop() {
        this.generation++;
        if (this.videoFrameHandle !== null) {
            const cancelVideoFrameCallback = this.video.cancelVideoFrameCallback;
            if (typeof cancelVideoFrameCallback === 'function') {
                try {
                    cancelVideoFrameCallback.call(this.video, this.videoFrameHandle);
                }
                catch {
                    // A detached or replaced video may reject an otherwise valid handle.
                }
            }
            this.videoFrameHandle = null;
        }
        if (this.animationFrameHandle !== null) {
            this.animationFrames.cancel(this.animationFrameHandle);
            this.animationFrameHandle = null;
        }
    }
    schedule(generation) {
        if (generation !== this.generation)
            return;
        if (this.useVideoFrames) {
            const requestVideoFrameCallback = this.video.requestVideoFrameCallback;
            if (typeof requestVideoFrameCallback === 'function') {
                try {
                    this.videoFrameHandle = requestVideoFrameCallback.call(this.video, (_now, metadata) => {
                        this.videoFrameHandle = null;
                        if (generation !== this.generation)
                            return;
                        const mediaTime = Number.isFinite(metadata.mediaTime) ? metadata.mediaTime : this.video.currentTime;
                        try {
                            this.onFrame({
                                mediaTime,
                                presentedFrames: Number.isFinite(metadata.presentedFrames) ? metadata.presentedFrames : null
                            });
                        }
                        finally {
                            this.schedule(generation);
                        }
                    });
                    return;
                }
                catch {
                    this.useVideoFrames = false;
                }
            }
            else {
                this.useVideoFrames = false;
            }
        }
        this.animationFrameHandle = this.animationFrames.request(() => {
            this.animationFrameHandle = null;
            if (generation !== this.generation)
                return;
            try {
                this.onFrame({ mediaTime: this.video.currentTime, presentedFrames: null });
            }
            finally {
                this.schedule(generation);
            }
        });
    }
}
//# sourceMappingURL=video-frame-scheduler.js.map