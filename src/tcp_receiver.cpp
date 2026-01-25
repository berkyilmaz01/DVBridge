#include "tcp_receiver.hpp"
#include <iostream>
#include <cstring>

// Windows doesn't define ssize_t
#ifdef _WIN32
typedef int ssize_t;
#endif

namespace converter {

// Static member initialization
bool TcpReceiver::socket_lib_initialized_ = false;

TcpReceiver::TcpReceiver(const Config& cfg)
    : config_(cfg)
    , socket_(INVALID_SOCK)
    , connected_(false)
    , total_bytes_received_(0)
    , total_frames_received_(0)
{
    initSocketLib();
}

TcpReceiver::~TcpReceiver()
{
    disconnect();
}

TcpReceiver::TcpReceiver(TcpReceiver&& other) noexcept
    : config_(other.config_)
    , socket_(other.socket_)
    , connected_(other.connected_)
    , total_bytes_received_(other.total_bytes_received_)
    , total_frames_received_(other.total_frames_received_)
{
    other.socket_ = INVALID_SOCK;
    other.connected_ = false;
}

TcpReceiver& TcpReceiver::operator=(TcpReceiver&& other) noexcept
{
    if (this != &other) {
        disconnect();
        socket_ = other.socket_;
        connected_ = other.connected_;
        total_bytes_received_ = other.total_bytes_received_;
        total_frames_received_ = other.total_frames_received_;
        other.socket_ = INVALID_SOCK;
        other.connected_ = false;
    }
    return *this;
}

bool TcpReceiver::initSocketLib()
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

void TcpReceiver::cleanupSocketLib()
{
#ifdef _WIN32
    if (socket_lib_initialized_) {
        WSACleanup();
        socket_lib_initialized_ = false;
    }
#endif
}

bool TcpReceiver::connect()
{
    if (connected_) {
        std::cerr << "Already connected" << std::endl;
        return true;
    }
    
    // Create socket
    socket_ = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (socket_ == INVALID_SOCK) {
        std::cerr << "Failed to create socket: " << SOCKET_ERROR_CODE << std::endl;
        return false;
    }
    
    // Set receive buffer size
    int rcvbuf = config_.recv_buffer_size;
    if (setsockopt(socket_, SOL_SOCKET, SO_RCVBUF, 
                   reinterpret_cast<const char*>(&rcvbuf), sizeof(rcvbuf)) < 0) {
        std::cerr << "Warning: Failed to set receive buffer size" << std::endl;
    }
    
    // Disable Nagle's algorithm for lower latency
    int flag = 1;
    if (setsockopt(socket_, IPPROTO_TCP, TCP_NODELAY,
                   reinterpret_cast<const char*>(&flag), sizeof(flag)) < 0) {
        std::cerr << "Warning: Failed to disable Nagle's algorithm" << std::endl;
    }
    
    // Setup server address
    struct sockaddr_in server_addr;
    std::memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(config_.camera_port);
    
    if (inet_pton(AF_INET, config_.camera_ip.c_str(), &server_addr.sin_addr) <= 0) {
        std::cerr << "Invalid IP address: " << config_.camera_ip << std::endl;
        disconnect();
        return false;
    }
    
    // Connect to server
    std::cout << "Connecting to " << config_.camera_ip << ":" << config_.camera_port << "..." << std::endl;
    
    if (::connect(socket_, reinterpret_cast<struct sockaddr*>(&server_addr), sizeof(server_addr)) < 0) {
        std::cerr << "Failed to connect: " << SOCKET_ERROR_CODE << std::endl;
        disconnect();
        return false;
    }
    
    connected_ = true;
    total_bytes_received_ = 0;
    total_frames_received_ = 0;
    
    std::cout << "Connected successfully!" << std::endl;
    return true;
}

void TcpReceiver::disconnect()
{
    if (socket_ != INVALID_SOCK) {
#ifdef _WIN32
        closesocket(socket_);
#else
        close(socket_);
#endif
        socket_ = INVALID_SOCK;
    }
    connected_ = false;
}

bool TcpReceiver::isConnected() const
{
    return connected_;
}

bool TcpReceiver::receiveExact(uint8_t* buffer, size_t size)
{
    size_t total_received = 0;
    
    while (total_received < size) {
        ssize_t received = recv(socket_, 
                                reinterpret_cast<char*>(buffer + total_received),
                                size - total_received, 
                                0);
        
        if (received <= 0) {
            if (received == 0) {
                std::cerr << "Connection closed by server" << std::endl;
            } else {
                std::cerr << "Receive error: " << SOCKET_ERROR_CODE << std::endl;
            }
            connected_ = false;
            return false;
        }
        
        total_received += received;
        total_bytes_received_ += received;
    }
    
    return true;
}

bool TcpReceiver::receiveFrame(std::vector<uint8_t>& buffer)
{
    if (!connected_) {
        std::cerr << "Not connected" << std::endl;
        return false;
    }
    
    int frame_size = getFrameSize();
    
    // If has header, read frame size from header first
    if (config_.has_header) {
        uint32_t header_frame_size = 0;
        
        if (!receiveExact(reinterpret_cast<uint8_t*>(&header_frame_size), config_.header_size)) {
            return false;
        }
        
        // Use header frame size if valid, otherwise use configured size
        if (header_frame_size > 0 && header_frame_size < 100000000) {  // Sanity check: < 100MB
            frame_size = header_frame_size;
        }
        
        if (config_.verbose) {
            std::cout << "Frame header: size = " << frame_size << " bytes" << std::endl;
        }
    }
    
    // Resize buffer and receive frame data
    buffer.resize(frame_size);
    
    if (!receiveExact(buffer.data(), frame_size)) {
        return false;
    }
    
    total_frames_received_++;
    
    if (config_.verbose) {
        std::cout << "Received frame " << total_frames_received_ 
                  << " (" << frame_size << " bytes)" << std::endl;
    }
    
    return true;
}

int TcpReceiver::getFrameSize() const
{
    return config_.frame_size();
}

} // namespace converter
