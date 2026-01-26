#pragma once

#include <string>
#include <cstdint>

namespace converter {

/**
 * Protocol type for camera connection
 */
enum class Protocol {
    TCP,    // TCP client - connects to camera server
    UDP     // UDP receiver - binds to port and receives datagrams
};

/**
 * Helper to convert Protocol enum to string
 */
inline const char* protocolToString(Protocol p) {
    switch (p) {
        case Protocol::TCP: return "TCP";
        case Protocol::UDP: return "UDP";
        default: return "Unknown";
    }
}

/**
 * Configuration for TCP/UDP to AEDAT4 Converter
 *
 * Modify these values to match your camera settings.
 * If the image looks wrong, try flipping the bit unpacking flags.
 */
struct Config {

    // =========================================================================
    // FRAME SETTINGS
    // =========================================================================

    int width = 1280;           // Frame width in pixels
    int height = 780;           // Frame height in pixels

    // Auto-calculated (do not modify)
    int pixels_per_channel() const { return width * height; }
    int bytes_per_channel() const { return pixels_per_channel() / 8; }
    int frame_size() const { return 2 * bytes_per_channel(); }  // 2 channels

    // =========================================================================
    // PROTOCOL SELECTION
    // =========================================================================

    Protocol protocol = Protocol::UDP;  // UDP is default (used by FPGA)

    // =========================================================================
    // NETWORK SETTINGS - INPUT (from camera)
    // =========================================================================

    // For TCP: IP address to connect to
    // For UDP: IP to bind to (use "0.0.0.0" to listen on all interfaces)
    std::string camera_ip = "0.0.0.0";
    int camera_port = 5000;                // Camera port (TCP or UDP)

    // Receive buffer size (bytes) - larger = handles bursts better
    int recv_buffer_size = 50 * 1024 * 1024;  // 50 MB

    // =========================================================================
    // UDP-SPECIFIC SETTINGS
    // =========================================================================

    // Maximum UDP packet size to receive
    // Standard: 65535 bytes (max UDP datagram)
    // Jumbo frames on 10G: up to 9000 bytes MTU, ~8972 payload
    // Set this to match your network configuration
    int udp_packet_size = 65535;
    
    // =========================================================================
    // NETWORK SETTINGS - OUTPUT (to DV viewer)
    // =========================================================================
    
    int aedat_port = 7777;      // Port where DV viewer connects
    
    // =========================================================================
    // FRAME HEADER SETTINGS (TCP only)
    // =========================================================================

    // Does the camera send a size header before each frame?
    // Note: FPGA typically sends raw data without headers (set to false)
    bool has_header = false;
    
    // Header size in bytes (only used if has_header = true)
    // Common values: 4 (uint32_t size)
    int header_size = 4;
    
    // =========================================================================
    // BIT UNPACKING SETTINGS
    // Flip these if the image looks wrong!
    // =========================================================================
    
    // Bit order within each byte
    // false = LSB first (bit 0 is first pixel)
    // true  = MSB first (bit 7 is first pixel)
    bool msb_first = false;
    
    // Channel order in frame data
    // true  = [positive channel][negative channel]
    // false = [negative channel][positive channel]
    bool positive_first = true;
    
    // Pixel ordering
    // true  = row-major (pixels go left-to-right, then next row)
    // false = column-major (pixels go top-to-bottom, then next column)
    bool row_major = true;
    
    // =========================================================================
    // TIMING SETTINGS
    // =========================================================================
    
    // Microseconds between frames (for timestamp generation)
    // 2000 us = 500 FPS
    // 1000 us = 1000 FPS
    // 200 us = 5000 FPS (for 10G Ethernet demo)
    int64_t frame_interval_us = 200;
    
    // =========================================================================
    // DEBUG SETTINGS
    // =========================================================================
    
    // Print statistics every N frames (0 = disable)
    int stats_interval = 100;
    
    // Print verbose debug messages
    bool verbose = false;
};

// Global configuration instance
// Modify this in main() or load from file if needed
inline Config config;

} // namespace converter
