cmake_minimum_required(VERSION 3.20)
project(oak_webcam LANGUAGES C CXX)
include(GNUInstallDirs)

find_package(Threads REQUIRED)
add_library(frame_receiver native/frame_receiver.cpp)
target_compile_features(frame_receiver PUBLIC cxx_std_17)
target_include_directories(frame_receiver PUBLIC native)
target_link_libraries(frame_receiver PUBLIC Threads::Threads)
target_compile_options(frame_receiver PRIVATE -Wall -Wextra -Wpedantic)

option(BUILD_UVC_BRIDGE "Build the Linux USB gadget bridge" ON)
if(BUILD_UVC_BRIDGE)
  add_subdirectory(vendor/uvc-gadget)
  # Linux output drivers may interpret bytesused=0 as a full buffer. Guard
  # both static-source queue paths so a failed fill never submits invalid JPEG.
  # Generate the narrowly patched source without modifying the pinned vendor.
  file(READ "${CMAKE_CURRENT_SOURCE_DIR}/vendor/uvc-gadget/lib/stream.c" stream_source)
  string(REPLACE "\tv4l2_queue_buffer(sink, &buf);"
    "\tif (buf.bytesused) v4l2_queue_buffer(sink, &buf);"
    stream_source "${stream_source}")
  string(REPLACE "\t\tret = v4l2_queue_buffer(sink, &buf);"
    "\t\tif (!buf.bytesused) return -EINVAL;\n\t\tret = v4l2_queue_buffer(sink, &buf);"
    stream_source "${stream_source}")
  file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/uvc-stream-safe.c" "${stream_source}")
  get_target_property(uvc_sources uvcgadget SOURCES)
  list(REMOVE_ITEM uvc_sources stream.c)
  set_property(TARGET uvcgadget PROPERTY SOURCES "${uvc_sources}")
  target_sources(uvcgadget PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/uvc-stream-safe.c")
  add_executable(oak-webcam-bridge native/main.cpp)
  target_link_libraries(oak-webcam-bridge PRIVATE frame_receiver uvcgadget)
  # OAK runtime images need not search /usr/local/lib in the loader cache.
  set_target_properties(oak-webcam-bridge PROPERTIES INSTALL_RPATH "$ORIGIN/../${CMAKE_INSTALL_LIBDIR}")
  install(TARGETS oak-webcam-bridge RUNTIME DESTINATION bin)
endif()

include(CTest)
if(BUILD_TESTING)
  add_executable(frame-receiver-test native/tests/frame_receiver_test.cpp)
  target_link_libraries(frame-receiver-test PRIVATE frame_receiver)
  add_test(NAME frame-receiver COMMAND frame-receiver-test)
  set_tests_properties(frame-receiver PROPERTIES TIMEOUT 10)
endif()
