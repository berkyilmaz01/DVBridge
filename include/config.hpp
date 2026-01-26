#pragma once

#include <string>
#include <cstdint>

namespace converter {

/**
 * Configuration for TCP to AEDAT4 Converter
 * 
 * Modify these values to match your camera settings.
 * If the image looks wrong, try flipping the bit unpacking flags.
 */
struct Config {
    
    // =========================================================================
    // FRAME SETTINGS
    // =========================================================================
    
    int width = 2048;           // Frame width in pixels (2048x2048 = 1MB frames)
    int height = 2048;          // Frame height in pixels
    
    // Auto-calculated (do not modify)
    int pixels_per_channel() const { return width * height; }
    int bytes_per_channel() const { return pixels_per_channel() / 8; }
    int frame_size() const { return 2 * bytes_per_channel(); }  // 2 channels
    
    // =========================================================================
    // NETWORK SETTINGS - INPUT (from camera)
    // =========================================================================
    
    std::string camera_ip = "127.0.0.1";  // Camera IP address
    int camera_port = 5000;                // Camera TCP port
    
    // TCP receive buffer size (bytes) - larger = handles bursts better
    int recv_buffer_size = 50 * 1024 * 1024;  // 50 MB
    
    // =========================================================================
    // NETWORK SETTINGS - OUTPUT (to DV viewer)
    // =========================================================================
    
    int aedat_port = 7777;      // Port where DV viewer connects
    
    // =========================================================================
    // FRAME HEADER SETTINGS
    // =========================================================================
    
    // Does the camera send a size header before each frame?
    bool has_header = false;  // No header - raw frames back-to-back
    
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
    int64_t frame_interval_us = 2000;
    
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
