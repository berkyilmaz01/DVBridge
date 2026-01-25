#pragma once

#include "config.hpp"
#include <dv-processing/core/event.hpp>
#include <vector>
#include <array>
#include <cstdint>

namespace converter {

/**
 * Frame Unpacker class (Optimized)
 *
 * Converts binary bit-packed frames into dv::EventStore.
 * Uses byte-level processing with lookup tables for high performance.
 *
 * Input format:
 *   - 2 channels (positive and negative events)
 *   - Each channel: width × height bits (1 bit per pixel)
 *   - Total: 2 × width × height / 8 bytes
 *
 * Output format:
 *   - dv::EventStore containing events with (timestamp, x, y, polarity)
 */
class FrameUnpacker {
public:
    /**
     * Constructor
     * @param cfg Configuration reference
     */
    explicit FrameUnpacker(const Config& cfg);

    /**
     * Unpack a binary frame into events
     *
     * @param frame_data Raw binary frame data
     * @param frame_number Frame sequence number (for timestamp generation)
     * @param events Output event store (will be cleared first)
     * @return Number of events unpacked
     */
    size_t unpack(
        const std::vector<uint8_t>& frame_data,
        uint64_t frame_number,
        dv::EventStore& events
    );

    /**
     * Unpack a binary frame into events (pointer version)
     *
     * @param frame_data Raw binary frame data pointer
     * @param data_size Size of frame data in bytes
     * @param frame_number Frame sequence number (for timestamp generation)
     * @param events Output event store (will be cleared first)
     * @return Number of events unpacked
     */
    size_t unpack(
        const uint8_t* frame_data,
        size_t data_size,
        uint64_t frame_number,
        dv::EventStore& events
    );

    /**
     * Get expected frame size in bytes
     * @return Frame size
     */
    int getExpectedFrameSize() const;

    /**
     * Get resolution
     * @return Resolution as cv::Size
     */
    cv::Size getResolution() const;

private:
    /**
     * Unpack a single channel using optimized byte-level processing
     *
     * @param channel_data Pointer to channel data
     * @param timestamp Event timestamp
     * @param polarity Event polarity (true=positive, false=negative)
     * @param events Output event store
     */
    void unpackChannelFast(
        const uint8_t* channel_data,
        int64_t timestamp,
        bool polarity,
        dv::EventStore& events
    );

    const Config& config_;

    // Pre-computed lookup table: bit_positions_[byte_value][i] = i-th set bit position
    // Using fixed-size arrays for cache efficiency
    static constexpr int MAX_BITS_PER_BYTE = 8;
    std::array<std::array<int8_t, MAX_BITS_PER_BYTE>, 256> bit_positions_;
    std::array<int8_t, 256> bit_counts_;  // Number of set bits per byte value

    // Pre-computed coordinate lookup for row-major layout
    // For each byte index, stores the base (x, y) coordinates
    std::vector<int16_t> byte_to_base_x_;
    std::vector<int16_t> byte_to_base_y_;

    /**
     * Initialize lookup tables
     */
    void initLookupTables();
};

} // namespace converter
