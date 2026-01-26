#pragma once

#include "config.hpp"
#include <vector>
#include <string>
#include <cstdint>
#include <stdexcept>

// Platform-specific includes
#ifdef _WIN32
    #include <winsock2.h>
    #include <ws2tcpip.h>
    #pragma comment(lib, "ws2_32.lib")
    typedef SOCKET socket_t;
    #define INVALID_SOCK INVALID_SOCKET
    #define SOCKET_ERROR_CODE WSAGetLastError()
#else
    #include <sys/socket.h>
    #include <netinet/in.h>
    #include <arpa/inet.h>
    #include <unistd.h>
    typedef int socket_t;
    #define INVALID_SOCK (-1)
    #define SOCKET_ERROR_CODE errno
#endif

namespace converter {

/**
 * UDP Receiver class
 *
 * Receives binary frames via UDP. Supports two modes:
 * 1. Single datagram per frame (for jumbo frames or small frames)
 * 2. Multiple datagrams per frame with sequence numbers (for fragmented frames)
 *
 * The FPGA sends raw frame data without headers, so we accumulate data
 * until we have a complete frame.
 */
class UdpReceiver {
public:
    /**
     * Constructor
     * @param cfg Configuration reference
     */
    explicit UdpReceiver(const Config& cfg);

    /**
     * Destructor - closes socket
     */
    ~UdpReceiver();

    // Disable copy
    UdpReceiver(const UdpReceiver&) = delete;
    UdpReceiver& operator=(const UdpReceiver&) = delete;

    // Enable move
    UdpReceiver(UdpReceiver&& other) noexcept;
    UdpReceiver& operator=(UdpReceiver&& other) noexcept;

    /**
     * Bind to the UDP port and start listening
     * @return true if bind successful
     */
    bool connect();

    /**
     * Close the UDP socket
     */
    void disconnect();

    /**
     * Check if socket is bound and ready
     * @return true if ready to receive
     */
    bool isConnected() const;

    /**
     * Receive one complete frame
     *
     * For UDP, this accumulates data until we have a full frame.
     * If frame boundaries are marked (e.g., by timing or sequence numbers),
     * it will respect those boundaries.
     *
     * @param buffer Output buffer (will be resized to frame size)
     * @return true if frame received successfully, false on error
     */
    bool receiveFrame(std::vector<uint8_t>& buffer);

    /**
     * Get the expected frame size (without header)
     * @return Frame size in bytes
     */
    int getFrameSize() const;

    /**
     * Get total bytes received
     * @return Total bytes received since connection
     */
    uint64_t getTotalBytesReceived() const { return total_bytes_received_; }

    /**
     * Get total frames received
     * @return Total frames received since connection
     */
    uint64_t getTotalFramesReceived() const { return total_frames_received_; }

private:
    /**
     * Initialize socket library (Windows only)
     */
    static bool initSocketLib();

    /**
     * Cleanup socket library (Windows only)
     */
    static void cleanupSocketLib();

    const Config& config_;
    socket_t socket_;
    bool bound_;

    // Receive buffer for individual UDP packets
    std::vector<uint8_t> packet_buffer_;

    // Leftover bytes from previous packet that belong to next frame
    std::vector<uint8_t> leftover_buffer_;
    size_t leftover_bytes_;

    uint64_t total_bytes_received_;
    uint64_t total_frames_received_;

    static bool socket_lib_initialized_;
};

} // namespace converter
