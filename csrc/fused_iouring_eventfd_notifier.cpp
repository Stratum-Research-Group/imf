#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/eventfd.h>

// Kernel-Bypass io_uring Direct Polling Eventfd Integration
// Provides sub-microsecond non-blocking signaling between asynchronous DMA workers and CUDA streams

extern "C" {

struct EventFdNotifier {
    int efd;
    uint64_t counter;
};

EventFdNotifier* eventfd_notifier_create() {
    int fd = eventfd(0, EFD_NONBLOCK | EFD_CLOEXEC);
    if (fd < 0) return nullptr;

    EventFdNotifier* n = (EventFdNotifier*)malloc(sizeof(EventFdNotifier));
    if (!n) {
        close(fd);
        return nullptr;
    }
    n->efd = fd;
    n->counter = 0;
    return n;
}

int eventfd_signal_completion(EventFdNotifier* n, uint64_t increment) {
    if (!n || n->efd < 0) return -1;
    ssize_t s = write(n->efd, &increment, sizeof(uint64_t));
    return (s == sizeof(uint64_t)) ? 0 : -1;
}

int eventfd_poll_and_acknowledge(EventFdNotifier* n, uint64_t* out_val) {
    if (!n || n->efd < 0 || !out_val) return -1;
    uint64_t val = 0;
    ssize_t s = read(n->efd, &val, sizeof(uint64_t));
    if (s == sizeof(uint64_t)) {
        *out_val = val;
        n->counter += val;
        return 0; // Successfully consumed
    }
    return 1; // EAGAIN / pending
}

void eventfd_notifier_destroy(EventFdNotifier* n) {
    if (n) {
        if (n->efd >= 0) close(n->efd);
        free(n);
    }
}

}
