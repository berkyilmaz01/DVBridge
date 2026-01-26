#include "udp_receiver.hpp"
#include <iostream>
#include <cstring>

// Windows doesn't define ssize_t
#ifdef _WIN32
typedef int ssize_t;
#endif

namespace converter {

// Static member initialization
bool UdpReceiver::socket_lib_initialized_ = false;

UdpReceiver::UdpReceiver(const Config& cfg)
    : config_(cfg)
    , socket_(INVALID_SOCK)
    , bound_(false)
    , accumulated_bytes_(0)
    , total_bytes_received_(0)
    , total_frames_received_(0)
{
    initSocketLib();

    // Pre-allocate buffers
    accumulation_buffer_.resize(cfg.frame_size());
    // UDP max packet size - typically 65535, but we use configured value
    packet_buffer_.resize(cfg.udp_packet_size);
}

UdpReceiver::~UdpReceiver()
{
    disconnect();
}

UdpReceiver::UdpReceiver(UdpReceiver&& other) noexcept
    : config_(other.config_)
    , socket_(other.socket_)
    , bound_(other.bound_)
    , accumulation_buffer_(std::move(other.accumulation_buffer_))
    , accumulated_bytes_(other.accumulated_bytes_)
    , packet_buffer_(std::move(other.packet_buffer_))
    , total_bytes_received_(other.total_bytes_received_)
    , total_frames_received_(other.total_frames_received_)
{
    other.socket_ = INVALID_SOCK;
    other.bound_ = false;
}

UdpReceiver& UdpReceiver::operator=(UdpReceiver&& other) noexcept
{
    if (this != &other) {
        disconnect();
        socket_ = other.socket_;
        bound_ = other.bound_;
        accumulation_buffer_ = std::move(other.accumulation_buffer_);
        accumulated_bytes_ = other.accumulated_bytes_;
        packet_buffer_ = std::move(other.packet_buffer_);
        total_bytes_received_ = other.total_bytes_received_;
        total_frames_received_ = other.total_frames_received_;
        other.socket_ = INVALID_SOCK;
        other.bound_ = false;
    }
    return *this;
}

bool UdpReceiver::initSocketLib()
{
#ifdef _WIN32
    if (!socket_lib_initialized_) {
        WSADATA wsaData;
        int result = WSAStartup(MAKEWORD(2, 2), &wsaData);
        if (result != 0) {
            std::cerr << "WSAStartup failed: " << result << std::endl;
            return false;
        }
        socket_lib_initialized_ = true;
    }
#endif
    return true;
}

void UdpReceiver::cleanupSocketLib()
{
#ifdef _WIN32
    if (socket_lib_initialized_) {
        WSACleanup();
        socket_lib_initialized_ = false;
    }
#endif
}

bool UdpReceiver::connect()
{
    if (bound_) {
        std::cerr << "Already bound to UDP port" << std::endl;
        return true;
    }

    // Create UDP socket
    socket_ = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (socket_ == INVALID_SOCK) {
        std::cerr << "Failed to create UDP socket: " << SOCKET_ERROR_CODE << std::endl;
        return false;
    }

    // Set receive buffer size (important for high-throughput)
    int rcvbuf = config_.recv_buffer_size;
    if (setsockopt(socket_, SOL_SOCKET, SO_RCVBUF,
                   reinterpret_cast<const char*>(&rcvbuf), sizeof(rcvbuf)) < 0) {
        std::cerr << "Warning: Failed to set receive buffer size to " << rcvbuf << std::endl;
    }

    // Allow address reuse for quick restarts
    int reuse = 1;
    if (setsockopt(socket_, SOL_SOCKET, SO_REUSEADDR,
                   reinterpret_cast<const char*>(&reuse), sizeof(reuse)) < 0) {
        std::cerr << "Warning: Failed to set SO_REUSEADDR" << std::endl;
    }

    // Bind to local address
    struct sockaddr_in local_addr;
    std::memset(&local_addr, 0, sizeof(local_addr));
    local_addr.sin_family = AF_INET;
    local_addr.sin_port = htons(config_.camera_port);

    // Bind to specific IP if configured, otherwise INADDR_ANY
    if (config_.camera_ip.empty() || config_.camera_ip == "0.0.0.0") {
        local_addr.sin_addr.s_addr = INADDR_ANY;
    } else {
        if (inet_pton(AF_INET, config_.camera_ip.c_str(), &local_addr.sin_addr) <= 0) {
            std::cerr << "Invalid bind IP address: " << config_.camera_ip << std::endl;
            disconnect();
            return false;
        }
    }

    std::cout << "Binding UDP socket to port " << config_.camera_port << "..." << std::endl;

    if (bind(socket_, reinterpret_cast<struct sockaddr*>(&local_addr), sizeof(local_addr)) < 0) {
        std::cerr << "Failed to bind UDP socket to port " << config_.camera_port
                  << ": " << SOCKET_ERROR_CODE << std::endl;
        disconnect();
        return false;
    }

    bound_ = true;
    total_bytes_received_ = 0;
    total_frames_received_ = 0;
    accumulated_bytes_ = 0;

    std::cout << "UDP socket bound successfully! Waiting for data on port "
              << config_.camera_port << std::endl;
    return true;
}

void UdpReceiver::disconnect()
{
    if (socket_ != INVALID_SOCK) {
#ifdef _WIN32
        closesocket(socket_);
#else
        close(socket_);
#endif
        socket_ = INVALID_SOCK;
    }
    bound_ = false;
    accumulated_bytes_ = 0;
}

bool UdpReceiver::isConnected() const
{
    return bound_;
}

bool UdpReceiver::receiveFrame(std::vector<uint8_t>& buffer)
{
    if (!bound_) {
        std::cerr << "UDP socket not bound" << std::endl;
        return false;
    }

    int frame_size = getFrameSize();
    buffer.resize(frame_size);

    // Reset accumulation for new frame
    accumulated_bytes_ = 0;

    // Accumulate UDP packets until we have a complete frame
    while (accumulated_bytes_ < static_cast<size_t>(frame_size)) {
        struct sockaddr_in sender_addr;
        socklen_t sender_len = sizeof(sender_addr);

        ssize_t received = recvfrom(
            socket_,
            reinterpret_cast<char*>(packet_buffer_.data()),
            packet_buffer_.size(),
            0,
            reinterpret_cast<struct sockaddr*>(&sender_addr),
            &sender_len
        );

        if (received <= 0) {
            if (received == 0) {
                std::cerr << "UDP socket closed" << std::endl;
            } else {
                std::cerr << "UDP receive error: " << SOCKET_ERROR_CODE << std::endl;
            }
            bound_ = false;
            return false;
        }

        // Calculate how many bytes we can use from this packet
        size_t bytes_needed = frame_size - accumulated_bytes_;
        size_t bytes_to_copy = std::min(bytes_needed, static_cast<size_t>(received));

        // Copy to output buffer
        std::memcpy(buffer.data() + accumulated_bytes_, packet_buffer_.data(), bytes_to_copy);
        accumulated_bytes_ += bytes_to_copy;
        total_bytes_received_ += received;

        if (config_.verbose) {
            char sender_ip[INET_ADDRSTRLEN];
            inet_ntop(AF_INET, &sender_addr.sin_addr, sender_ip, sizeof(sender_ip));
            std::cout << "Received UDP packet: " << received << " bytes from "
                      << sender_ip << ":" << ntohs(sender_addr.sin_port)
                      << " (accumulated: " << accumulated_bytes_ << "/" << frame_size << ")"
                      << std::endl;
        }

        // If packet was larger than needed (unusual case), we discard the extra
        // This can happen if the sender's frame size doesn't match ours
        if (static_cast<size_t>(received) > bytes_needed && config_.verbose) {
            std::cerr << "Warning: Discarded " << (received - bytes_to_copy)
                      << " extra bytes from UDP packet" << std::endl;
        }
    }

    total_frames_received_++;

    if (config_.verbose) {
        std::cout << "Received complete frame " << total_frames_received_
                  << " (" << frame_size << " bytes)" << std::endl;
    }

    return true;
}

int UdpReceiver::getFrameSize() const
{
    return config_.frame_size();
}

} // namespace converter
