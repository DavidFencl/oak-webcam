#pragma once
#include "frame_receiver.hpp"
#include <cstring>

namespace webcam {
// Owned only by the UVC event thread. Retain a complete frame if the producer
// is temporarily unavailable or its next frame cannot fit the USB buffer.
class FrameCache {
 public:
  bool refresh(FrameReceiver& receiver, std::size_t capacity = max_frame_size) {
    const auto size = receiver.copy_latest(candidate_.data(), candidate_.size());
    if (size && size <= capacity) {
      cached_.swap(candidate_);
      size_ = size;
    }
    return size_ != 0;
  }
  std::size_t copy(void* destination, std::size_t capacity) const {
    if (!size_ || size_ > capacity) return 0;
    std::memcpy(destination, cached_.data(), size_);
    return size_;
  }
 private:
  std::vector<std::uint8_t> cached_ = std::vector<std::uint8_t>(max_frame_size);
  std::vector<std::uint8_t> candidate_ = std::vector<std::uint8_t>(max_frame_size);
  std::size_t size_ = 0;
};
}
