#include "frame_receiver.hpp"
#include "frame_cache.hpp"
#include <arpa/inet.h>
#include <chrono>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <sys/socket.h>
#include <sys/un.h>
#include <thread>
#include <unistd.h>

using namespace std::chrono_literals;
void require(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}
int connect_to(const std::string& path) {
  int fd = socket(AF_UNIX, SOCK_STREAM, 0);
  sockaddr_un address{};
  address.sun_family = AF_UNIX;
  std::strcpy(address.sun_path, path.c_str());
  require(connect(fd, reinterpret_cast<sockaddr*>(&address), sizeof(address)) == 0, "connect");
  return fd;
}
template <class Predicate> void eventually(Predicate predicate) {
  for (int attempt = 0; attempt < 200; ++attempt) {
    if (predicate()) return;
    std::this_thread::sleep_for(5ms);
  }
  throw std::runtime_error("Timed out waiting for receiver");
}
int main() {
  try {
    const std::string path = "/tmp/oak-webcam-test-" + std::to_string(getpid()) + ".sock";
    webcam::FrameReceiver receiver(path);
    receiver.start();
    unsigned char output[20]{};
    webcam::FrameCache cache;
    require(!cache.refresh(receiver), "cache waits for first complete JPEG");
    require(receiver.copy_latest(output, sizeof(output)) == 0, "initially empty");
    int client = connect_to(path);
    const unsigned char jpeg[] = {0xff, 0xd8, 1, 2, 3, 0xff, 0xd9};
    const auto header = htonl(sizeof(jpeg));
    // Fragment both header and payload to exercise stream framing.
    const auto* header_bytes = reinterpret_cast<const unsigned char*>(&header);
    for (unsigned int i = 0; i < sizeof(header); ++i)
      require(send(client, header_bytes + i, 1, MSG_NOSIGNAL) == 1, "header send");
    require(send(client, jpeg, 3, MSG_NOSIGNAL) == 3, "partial payload send");
    std::this_thread::sleep_for(20ms);
    require(receiver.copy_latest(output, sizeof(output)) == 0, "partial frame not published");
    require(send(client, jpeg + 3, sizeof(jpeg) - 3, MSG_NOSIGNAL) == sizeof(jpeg) - 3, "payload send");
    eventually([&] { return receiver.copy_latest(output, sizeof(output)) == sizeof(jpeg); });
    require(std::memcmp(output, jpeg, sizeof(jpeg)) == 0, "frame bytes preserved");
    require(cache.refresh(receiver), "first JPEG makes cache ready");
    require(receiver.copy_latest(output, 2) == 0, "oversize never truncated");
    close(client);
    eventually([&] { return receiver.copy_latest(output, sizeof(output)) == 0; });
    require(cache.refresh(receiver), "cache remains ready after disconnect");
    require(cache.copy(output, sizeof(output)) == sizeof(jpeg), "disconnect repeats complete JPEG");
    require(std::memcmp(output, jpeg, sizeof(jpeg)) == 0, "cached JPEG preserved");
    require(cache.copy(output, 2) == 0, "cache never truncates JPEG");
    client = connect_to(path);
    const auto oversized = htonl(webcam::max_frame_size + 1);
    require(send(client, &oversized, sizeof(oversized), MSG_NOSIGNAL) == sizeof(oversized), "oversize header send");
    char byte;
    eventually([&] { return recv(client, &byte, 1, MSG_DONTWAIT) == 0; });
    close(client);
    client = connect_to(path);
    require(send(client, &header, sizeof(header), MSG_NOSIGNAL) == sizeof(header), "reconnect header");
    require(send(client, jpeg, sizeof(jpeg), MSG_NOSIGNAL) == sizeof(jpeg), "reconnect payload");
    eventually([&] { return receiver.copy_latest(output, sizeof(output)) == sizeof(jpeg); });
    // Stop while a connected client is idle; bounded polling must release it.
    receiver.stop();
    close(client);
    require(access(path.c_str(), F_OK) != 0, "socket cleaned up");
    std::cout << "Framing, partial reads, size limit, reconnect, shutdown passed\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
