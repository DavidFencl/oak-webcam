# Third-party sources

USB integration is adapted from Luxonis oak-examples/cpp/uvc (MIT).
Reference: https://github.com/luxonis/oak-examples/tree/main/cpp/uvc

vendor/uvc-gadget is https://github.com/luxonis/uvc-gadget at commit
860b0b506bf2e17662458d5c642eaba5bfc07831, the submodule revision pinned by
the local oak-examples reference. Retain its COPYING, LICENSE and per-file notices.
The native bridge uses this library; it does not compile DepthAI from source.
