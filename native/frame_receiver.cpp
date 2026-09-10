#include "frame_receiver.hpp"

#include <arpa/inet.h>
#include <cerrno>
#include <cstring>
#include <poll.h>
#include <stdexcept>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <unistd.h>

namespace webcam {
FrameReceiver::FrameReceiver(std::string path) : path_(std::move(path)) {}
FrameReceiver::~FrameReceiver() { stop(); }

void FrameReceiver::start() {
  if (listener_ != -1) throw std::runtime_error("Receiver already started");
  sockaddr_un address{};
  address.sun_family = AF_UNIX;
  if (path_.empty() || path_.size() >= sizeof(address.sun_path))
    throw std::runtime_error("Invalid webcam socket path");
  std::memcpy(address.sun_path, path_.c_str(), path_.size() + 1);
  listener_ = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC | SOCK_NONBLOCK, 0);
  if (listener_ < 0) throw std::runtime_error("Cannot create webcam socket");
  // Never remove a pre-existing path: it may belong to another process.
  if (bind(listener_, reinterpret_cast<sockaddr*>(&address), sizeof(address)) < 0) {
    const auto error = std::string(std::strerror(errno));
    close(listener_);
    listener_ = -1;
    throw std::runtime_error("Cannot bind webcam socket: " + error);
  }
  owns_socket_ = true;
  if (chmod(path_.c_str(), 0600) < 0 || listen(listener_, 1) < 0) {
    stop();
    throw std::runtime_error("Cannot configure webcam socket");
  }
  stopped_ = false;
  thread_ = std::thread(&FrameReceiver::receive_loop, this);
}

void FrameReceiver::stop() {
  stopped_ = true;
  if (thread_.joinable()) thread_.join();
  if (listener_ >= 0) close(listener_);
  listener_ = -1;
  if (owns_socket_) unlink(path_.c_str());
  owns_socket_ = false;
}

bool FrameReceiver::read_exact(int fd, void* destination, std::size_t size) {
  auto* bytes = static_cast<std::uint8_t*>(destination);
  while (size && !stopped_) {
    pollfd descriptor{fd, POLLIN, 0};
    const int ready = poll(&descriptor, 1, 100);
    if (ready < 0) { if (errno == EINTR) continue; return false; }
    if (!ready) continue;
    const auto received = recv(fd, bytes, size, MSG_DONTWAIT);
    if (received < 0 && (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK))
      continue;
    if (received <= 0) return false;
    bytes += received;
    size -= static_cast<std::size_t>(received);
  }
  return size == 0 && !stopped_;
}

void FrameReceiver::receive_loop() {
  while (!stopped_) {
    pollfd descriptor{listener_, POLLIN, 0};
    if (poll(&descriptor, 1, 100) <= 0) continue;
    const int client = accept4(listener_, nullptr, nullptr, SOCK_CLOEXEC | SOCK_NONBLOCK);
    if (client < 0) continue;
    while (!stopped_) {
      std::uint32_t header;
      if (!read_exact(client, &header, sizeof(header))) break;
      const auto size = ntohl(header);
      if (size < 4 || size > max_frame_size) break;
      std::vector<std::uint8_t> frame(size);
      if (!read_exact(client, frame.data(), size)) break;
      // Reject obviously invalid messages; JPEG decoding belongs to the host.
      if (frame[0] != 0xff || frame[1] != 0xd8 ||
          frame[size - 2] != 0xff || frame[size - 1] != 0xd9) break;
      std::lock_guard<std::mutex> lock(mutex_);
      latest_.swap(frame);
    }
    close(client);
    std::lock_guard<std::mutex> lock(mutex_);
    latest_.clear();
  }
}

std::size_t FrameReceiver::copy_latest(void* destination, std::size_t capacity) {
  std::unique_lock<std::mutex> lock(mutex_, std::try_to_lock);
  if (!lock.owns_lock() || latest_.empty() || latest_.size() > capacity) return 0;
  std::memcpy(destination, latest_.data(), latest_.size());
  return latest_.size();
}
}  // namespace webcam
