#include "config.hpp"
#include "tcp_receiver.hpp"
#include "udp_receiver.hpp"
#include "frame_unpacker.hpp"

#include <dv-processing/io/network_writer.hpp>
#include <dv-processing/io/stream.hpp>
#include <dv-processing/core/event.hpp>

#include <iostream>
#include <iomanip>
#include <chrono>
#include <thread>
#include <csignal>
#include <atomic>
#include <memory>
#include <variant>

// Global flag for graceful shutdown
std::atomic<bool> running{true};

void signalHandler(int signum)
{
    std::cout << "\nInterrupt signal (" << signum << ") received. Shutting down..." << std::endl;
    running = false;
}

void printStats(
    uint64_t frame_count,
    uint64_t total_events,
    uint64_t total_bytes,
    std::chrono::steady_clock::time_point start_time)
{
    auto now = std::chrono::steady_clock::now();
    double elapsed = std::chrono::duration<double>(now - start_time).count();
    
    if (elapsed > 0) {
        double fps = frame_count / elapsed;
        double mbps = (total_bytes * 8.0) / (elapsed * 1000000.0);
        double meps = total_events / (elapsed * 1000000.0);  // Million events per second
        
        std::cout << "Stats: "
                  << "Frames: " << frame_count
                  << " | FPS: " << std::fixed << std::setprecision(1) << fps
                  << " | Events: " << total_events
                  << " | MEv/s: " << std::setprecision(2) << meps
                  << " | Throughput: " << std::setprecision(1) << mbps << " Mbps"
                  << std::endl;
    }
}

int main(int argc, char* argv[])
{
    std::cout << "============================================" << std::endl;
    std::cout << "   TCP/UDP to AEDAT4 Converter" << std::endl;
    std::cout << "============================================" << std::endl;

    // Setup signal handler for graceful shutdown
    std::signal(SIGINT, signalHandler);
    std::signal(SIGTERM, signalHandler);

    // Use global config (modify in config.hpp or add command line parsing)
    converter::Config& config = converter::config;

    // Print configuration
    std::cout << "\nConfiguration:" << std::endl;
    std::cout << "  Protocol: " << converter::protocolToString(config.protocol) << std::endl;
    std::cout << "  Frame size: " << config.width << " x " << config.height << std::endl;
    std::cout << "  Frame data size: " << config.frame_size() << " bytes" << std::endl;
    if (config.protocol == converter::Protocol::TCP) {
        std::cout << "  Camera (connect to): " << config.camera_ip << ":" << config.camera_port << std::endl;
    } else {
        std::cout << "  Listen port: " << config.camera_port << std::endl;
        std::cout << "  UDP packet size: " << config.udp_packet_size << " bytes" << std::endl;
    }
    std::cout << "  AEDAT4 output port: " << config.aedat_port << std::endl;
    std::cout << "  Frame interval: " << config.frame_interval_us << " us" << std::endl;
    if (config.protocol == converter::Protocol::TCP) {
        std::cout << "  Has header: " << (config.has_header ? "yes" : "no") << std::endl;
    }
    std::cout << "  MSB first: " << (config.msb_first ? "yes" : "no") << std::endl;
    std::cout << "  Positive first: " << (config.positive_first ? "yes" : "no") << std::endl;
    std::cout << "  Row major: " << (config.row_major ? "yes" : "no") << std::endl;
    std::cout << std::endl;

    // Create receiver based on protocol
    using ReceiverVariant = std::variant<converter::TcpReceiver, converter::UdpReceiver>;
    std::unique_ptr<ReceiverVariant> receiver_ptr;

    if (config.protocol == converter::Protocol::TCP) {
        receiver_ptr = std::make_unique<ReceiverVariant>(std::in_place_type<converter::TcpReceiver>, config);
    } else {
        receiver_ptr = std::make_unique<ReceiverVariant>(std::in_place_type<converter::UdpReceiver>, config);
    }

    // Helper lambdas to work with the variant
    auto connect_receiver = [&]() -> bool {
        return std::visit([](auto& r) { return r.connect(); }, *receiver_ptr);
    };

    auto disconnect_receiver = [&]() {
        std::visit([](auto& r) { r.disconnect(); }, *receiver_ptr);
    };

    auto receive_frame = [&](std::vector<uint8_t>& buffer) -> bool {
        return std::visit([&buffer](auto& r) { return r.receiveFrame(buffer); }, *receiver_ptr);
    };

    auto get_total_bytes = [&]() -> uint64_t {
        return std::visit([](auto& r) { return r.getTotalBytesReceived(); }, *receiver_ptr);
    };

    converter::FrameUnpacker unpacker(config);
    
    // Create AEDAT4 TCP server (DV viewer connects here)
    std::cout << "Starting AEDAT4 server on port " << config.aedat_port << "..." << std::endl;
    cv::Size resolution = unpacker.getResolution();

    // Create event stream for the NetworkWriter
    dv::io::Stream eventStream = dv::io::Stream::EventStream(0, "events", "DVS", resolution);

    dv::io::NetworkWriter writer(
        "0.0.0.0",
        static_cast<uint16_t>(config.aedat_port),
        eventStream
    );
    
    std::cout << "AEDAT4 server started. DV viewer can connect to port " << config.aedat_port << std::endl;
    std::cout << std::endl;
    
    // Connect/bind to receive data
    if (config.protocol == converter::Protocol::TCP) {
        std::cout << "Connecting to camera..." << std::endl;
    } else {
        std::cout << "Binding UDP socket..." << std::endl;
    }

    if (!connect_receiver()) {
        std::cerr << "Failed to initialize receiver. Exiting." << std::endl;
        return 1;
    }
    
    std::cout << std::endl;
    std::cout << "Starting main loop. Press Ctrl+C to stop." << std::endl;
    std::cout << "============================================" << std::endl;
    std::cout << std::endl;
    
    // Main loop variables
    std::vector<uint8_t> frame_buffer;
    dv::EventStore events;
    uint64_t frame_count = 0;
    uint64_t total_events = 0;
    auto start_time = std::chrono::steady_clock::now();
    
    // Main loop
    while (running) {
        // Receive frame from camera
        if (!receive_frame(frame_buffer)) {
            if (running) {
                std::cerr << "Failed to receive frame. Reconnecting..." << std::endl;
                disconnect_receiver();

                // Wait a bit before reconnecting
                std::this_thread::sleep_for(std::chrono::seconds(1));

                if (!connect_receiver()) {
                    std::cerr << "Reconnection failed. Exiting." << std::endl;
                    break;
                }
            }
            continue;
        }
        
        // Unpack frame to events
        size_t num_events = unpacker.unpack(frame_buffer, frame_count, events);
        
        // Send events to AEDAT4 stream
        if (num_events > 0) {
            writer.writeEvents(events);
        }
        
        // Update counters
        frame_count++;
        total_events += num_events;
        
        // Print statistics periodically
        if (config.stats_interval > 0 && frame_count % config.stats_interval == 0) {
            printStats(frame_count, total_events, get_total_bytes(), start_time);
        }
    }

    // Final statistics
    std::cout << std::endl;
    std::cout << "============================================" << std::endl;
    std::cout << "Final Statistics:" << std::endl;
    printStats(frame_count, total_events, get_total_bytes(), start_time);
    std::cout << "============================================" << std::endl;

    // Cleanup
    disconnect_receiver();
    
    std::cout << "Shutdown complete." << std::endl;
    return 0;
}
