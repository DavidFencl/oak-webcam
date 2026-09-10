#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace webcam {
constexpr std::size_t max_frame_size = 3840 * 2160 * 2;

// One producer and a non-waiting UVC consumer. No unbounded frame queue.
class FrameReceiver {
 public:
  explicit FrameReceiver(std::string path);
  ~FrameReceiver();
  FrameReceiver(const FrameReceiver&) = delete;
  FrameReceiver& operator=(const FrameReceiver&) = delete;
  void start();
  void stop();
  // Returns zero if unavailable, contended, or larger than the destination.
  std::size_t copy_latest(void* destination, std::size_t capacity);

 private:
  void receive_loop();
  bool read_exact(int fd, void* destination, std::size_t size);
  std::string path_;
  int listener_ = -1;
  bool owns_socket_ = false;
  std::atomic<bool> stopped_{false};
  std::thread thread_;
  std::mutex mutex_;
  std::vector<std::uint8_t> latest_;
};
}  // namespace webcam
