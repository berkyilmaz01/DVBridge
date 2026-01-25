#include "frame_unpacker.hpp"
#include <iostream>
#include <stdexcept>

namespace converter {

FrameUnpacker::FrameUnpacker(const Config& cfg)
    : config_(cfg)
{
}

int FrameUnpacker::getExpectedFrameSize() const
{
    return config_.frame_size();
}

cv::Size FrameUnpacker::getResolution() const
{
    return cv::Size(config_.width, config_.height);
}

int FrameUnpacker::getBitIndex(int x, int y) const
{
    if (config_.row_major) {
        // Row-major: pixels go left-to-right, then next row
        return y * config_.width + x;
    } else {
        // Column-major: pixels go top-to-bottom, then next column
        return x * config_.height + y;
    }
}

bool FrameUnpacker::getBit(const uint8_t* data, int x, int y) const
{
    int bit_index = getBitIndex(x, y);
    int byte_index = bit_index / 8;
    int bit_offset = bit_index % 8;
    
    if (config_.msb_first) {
        // MSB first: bit 7 is first pixel in byte
        bit_offset = 7 - bit_offset;
    }
    // else: LSB first: bit 0 is first pixel in byte
    
    return (data[byte_index] & (1 << bit_offset)) != 0;
}

size_t FrameUnpacker::unpack(
    const std::vector<uint8_t>& frame_data,
    uint64_t frame_number,
    dv::EventStore& events)
{
    return unpack(frame_data.data(), frame_data.size(), frame_number, events);
}

size_t FrameUnpacker::unpack(
    const uint8_t* frame_data,
    size_t data_size,
    uint64_t frame_number,
    dv::EventStore& events)
{
    // Validate frame size
    int expected_size = getExpectedFrameSize();
    if (static_cast<int>(data_size) < expected_size) {
        std::cerr << "Warning: Frame data size (" << data_size 
                  << ") is smaller than expected (" << expected_size << ")" << std::endl;
        return 0;
    }
    
    // Clear output
    events = dv::EventStore();
    
    // Calculate timestamp for this frame
    int64_t timestamp = static_cast<int64_t>(frame_number) * config_.frame_interval_us;
    
    // Get pointers to positive and negative channels
    const uint8_t* pos_channel;
    const uint8_t* neg_channel;
    
    if (config_.positive_first) {
        pos_channel = frame_data;
        neg_channel = frame_data + config_.bytes_per_channel();
    } else {
        neg_channel = frame_data;
        pos_channel = frame_data + config_.bytes_per_channel();
    }
    
    // Unpack all pixels
    for (int y = 0; y < config_.height; y++) {
        for (int x = 0; x < config_.width; x++) {
            // Check positive channel
            if (getBit(pos_channel, x, y)) {
                events.emplace_back(timestamp, static_cast<int16_t>(x), static_cast<int16_t>(y), true);
            }
            
            // Check negative channel
            if (getBit(neg_channel, x, y)) {
                events.emplace_back(timestamp, static_cast<int16_t>(x), static_cast<int16_t>(y), false);
            }
        }
    }
    
    if (config_.verbose) {
        std::cout << "Frame " << frame_number << ": unpacked " << events.size() << " events" << std::endl;
    }
    
    return events.size();
}

} // namespace converter
