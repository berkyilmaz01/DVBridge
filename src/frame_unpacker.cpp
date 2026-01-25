#include "frame_unpacker.hpp"
#include <iostream>
#include <stdexcept>

namespace converter {

FrameUnpacker::FrameUnpacker(const Config& cfg)
    : config_(cfg)
{
    initLookupTables();
}

void FrameUnpacker::initLookupTables()
{
    // Initialize bit position lookup table
    // For each possible byte value (0-255), store which bits are set
    for (int byte_val = 0; byte_val < 256; byte_val++) {
        int count = 0;
        for (int bit = 0; bit < 8; bit++) {
            int actual_bit = config_.msb_first ? (7 - bit) : bit;
            if (byte_val & (1 << actual_bit)) {
                bit_positions_[byte_val][count++] = static_cast<int8_t>(bit);
            }
        }
        bit_counts_[byte_val] = static_cast<int8_t>(count);
        // Fill remaining slots with -1 (unused)
        for (int i = count; i < MAX_BITS_PER_BYTE; i++) {
            bit_positions_[byte_val][i] = -1;
        }
    }

    // Pre-compute base coordinates for each byte index
    int bytes_per_channel = config_.bytes_per_channel();
    byte_to_base_x_.resize(bytes_per_channel);
    byte_to_base_y_.resize(bytes_per_channel);

    for (int byte_idx = 0; byte_idx < bytes_per_channel; byte_idx++) {
        int base_bit = byte_idx * 8;
        if (config_.row_major) {
            // Row-major: bit_index = y * width + x
            byte_to_base_y_[byte_idx] = static_cast<int16_t>(base_bit / config_.width);
            byte_to_base_x_[byte_idx] = static_cast<int16_t>(base_bit % config_.width);
        } else {
            // Column-major: bit_index = x * height + y
            byte_to_base_x_[byte_idx] = static_cast<int16_t>(base_bit / config_.height);
            byte_to_base_y_[byte_idx] = static_cast<int16_t>(base_bit % config_.height);
        }
    }
}

int FrameUnpacker::getExpectedFrameSize() const
{
    return config_.frame_size();
}

cv::Size FrameUnpacker::getResolution() const
{
    return cv::Size(config_.width, config_.height);
}

void FrameUnpacker::unpackChannelFast(
    const uint8_t* channel_data,
    int64_t timestamp,
    bool polarity,
    dv::EventStore& events)
{
    const int bytes_per_channel = config_.bytes_per_channel();
    const int width = config_.width;
    const int height = config_.height;
    const bool row_major = config_.row_major;

    for (int byte_idx = 0; byte_idx < bytes_per_channel; byte_idx++) {
        uint8_t byte_val = channel_data[byte_idx];

        // Skip zero bytes entirely - this is the key optimization!
        // In sparse event data, most bytes are zero
        if (byte_val == 0) {
            continue;
        }

        // Get pre-computed base coordinates for this byte
        int base_x = byte_to_base_x_[byte_idx];
        int base_y = byte_to_base_y_[byte_idx];

        // Process each set bit using lookup table
        int num_bits = bit_counts_[byte_val];
        for (int i = 0; i < num_bits; i++) {
            int bit_offset = bit_positions_[byte_val][i];

            // Calculate actual x, y from base + offset
            int16_t x, y;
            if (row_major) {
                // In row-major, bits advance along x, then wrap to next y
                int total_x = base_x + bit_offset;
                x = static_cast<int16_t>(total_x % width);
                y = static_cast<int16_t>(base_y + total_x / width);
            } else {
                // In column-major, bits advance along y, then wrap to next x
                int total_y = base_y + bit_offset;
                y = static_cast<int16_t>(total_y % height);
                x = static_cast<int16_t>(base_x + total_y / height);
            }

            events.emplace_back(timestamp, x, y, polarity);
        }
    }
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

    // Reserve space for events (estimate based on typical event density)
    events.reserve(config_.pixels_per_channel() / 10);

    // Unpack both channels using optimized byte-level processing
    unpackChannelFast(pos_channel, timestamp, true, events);
    unpackChannelFast(neg_channel, timestamp, false, events);

    if (config_.verbose) {
        std::cout << "Frame " << frame_number << ": unpacked " << events.size() << " events" << std::endl;
    }

    return events.size();
}

} // namespace converter
