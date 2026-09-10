#include "frame_receiver.hpp"
#include "frame_cache.hpp"

#include <csignal>
#include <cstdlib>
#include <iostream>
#include <chrono>
#include <cstring>
#include <poll.h>
#include <pthread.h>
#include <stdexcept>
#include <sys/signalfd.h>
#include <unistd.h>

extern "C" {
#include "configfs.h"
#include "depthai-source.h"
#include "events.h"
#include "stream.h"
#include "video-buffers.h"
#include "video-source.h"
}

namespace {
webcam::FrameReceiver* receiver = nullptr;
events* active_events = nullptr;
webcam::FrameCache cache;
void fill_buffer(video_source*, video_buffer* buffer) {
  cache.refresh(*receiver, buffer->size);
  buffer->bytesused = cache.copy(buffer->mem, buffer->size);
  if (!buffer->bytesused) {
    std::cerr << "UVC buffer cannot hold a complete JPEG; stopping\n";
    events_stop(active_events);
    return;
  }
}
void stop_events(void* context) { events_stop(static_cast<events*>(context)); }
}

int main(int argc, char** argv) {
  std::string socket_path = std::getenv("OAK_WEBCAM_SOCKET")
      ? std::getenv("OAK_WEBCAM_SOCKET") : "/tmp/oak-webcam.sock";
  std::string function = "uvc.oakwebcam";
  std::string device;
  for (int i = 1; i < argc; ++i) {
    const std::string option = argv[i];
    if (option == "--help") {
      std::cout << "oak-webcam-bridge [--socket PATH] [--function NAME] [--device /dev/videoN]\n";
      return 0;
    }
    if (i + 1 >= argc || (option != "--socket" && option != "--function" && option != "--device")) {
      std::cerr << "Unknown option or missing value: " << option << '\n';
      return 2;
    }
    const std::string value = argv[++i];
    if (option == "--socket") socket_path = value;
    else if (option == "--function") function = value;
    else device = value;
  }

  // signalfd wakes the event loop without running unsafe code in a handler.
  sigset_t signals;
  sigemptyset(&signals);
  sigaddset(&signals, SIGINT);
  sigaddset(&signals, SIGTERM);
  if (pthread_sigmask(SIG_BLOCK, &signals, nullptr) != 0) return 1;
  const int signal_fd = signalfd(-1, &signals, SFD_CLOEXEC | SFD_NONBLOCK);
  if (signal_fd < 0) return 1;

  events loop;
  events_init(&loop);
  events_watch_fd(&loop, signal_fd, EVENT_READ, stop_events, &loop);
  uvc_function_config* config = nullptr;
  video_source* source = nullptr;
  uvc_stream* stream = nullptr;
  bool initialized = false;
  int result = 1;
  webcam::FrameReceiver frames(socket_path);
  try {
    config = configfs_parse_uvc_function(function.c_str());
    if (!config) throw std::runtime_error("Cannot parse bound UVC function " + function);
    source = depthai_video_source_create();
    if (!source) throw std::runtime_error("Cannot allocate UVC source");
    stream = uvc_stream_new(device.empty() ? config->video : device.c_str());
    if (!stream) throw std::runtime_error("Cannot open UVC video device");
    frames.start();
    receiver = &frames;
    active_events = &loop;
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(30);
    while (!cache.refresh(frames)) {
      pollfd descriptor{signal_fd, POLLIN, 0};
      if (poll(&descriptor, 1, 20) > 0)
        throw std::runtime_error("Stopped while waiting for first JPEG");
      if (std::chrono::steady_clock::now() >= deadline)
        throw std::runtime_error("No first JPEG received within 30 seconds");
    }
    depthai_uvc_register_get_buffer(fill_buffer);
    depthai_video_source_init(source, &loop);
    uvc_stream_set_event_handler(stream, &loop);
    uvc_stream_set_video_source(stream, source);
    uvc_stream_init_uvc(stream, config);
    initialized = true;
    std::cout << "OAK webcam bridge listening on " << socket_path << std::endl;
    result = events_loop(&loop) ? 1 : 0;
  } catch (const std::exception& error) {
    std::cerr << "OAK webcam bridge: " << error.what() << '\n';
  }
  if (stream) {
    if (initialized) uvc_stream_enable(stream, 0);
    uvc_stream_delete(stream);
  }
  if (source) video_source_destroy(source);
  frames.stop();
  receiver = nullptr;
  events_cleanup(&loop);
  if (config) configfs_free_uvc_function(config);
  close(signal_fd);
  return result;
}
