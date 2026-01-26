#!/usr/bin/env python3
"""
Fake Camera Simulator (UDP) for TCP/UDP-to-AEDAT4 Converter Testing

Generates binary frames with a moving circle pattern and sends via UDP.
This simulates the FPGA/ZCU board output that the converter expects when
using the 10G Ethernet UDP protocol.

Usage:
    python3 fake_camera_udp.py [--port 5000] [--fps 500] [--target 127.0.0.1]
"""

import socket
import struct
import time
import argparse
import signal
import sys
import math

# Frame configuration (must match config.hpp)
WIDTH = 1280
HEIGHT = 780
CHANNELS = 2  # positive and negative
BYTES_PER_CHANNEL = (WIDTH * HEIGHT) // 8  # 124,800 bytes
FRAME_SIZE = CHANNELS * BYTES_PER_CHANNEL   # 249,600 bytes

# UDP packet size - can be adjusted based on network MTU
# For jumbo frames on 10G: use larger values (e.g., 8972)
# For standard Ethernet: use ~1472 (1500 MTU - 28 bytes IP/UDP headers)
DEFAULT_PACKET_SIZE = 8192

# Running flag for graceful shutdown
running = True

def signal_handler(sig, frame):
    global running
    print("\nShutting down...")
    running = False

def create_circle_frame(cx: int, cy: int, radius: int, positive: bool = True) -> bytes:
    """
    Create a binary frame with a filled circle.
    Returns bytes for one channel (positive or negative).
    """
    # Create bit array (row-major, LSB first to match default config)
    data = bytearray(BYTES_PER_CHANNEL)

    for y in range(HEIGHT):
        for x in range(WIDTH):
            # Check if pixel is inside circle
            dx = x - cx
            dy = y - cy
            if dx*dx + dy*dy <= radius*radius:
                # Set this bit
                bit_index = y * WIDTH + x
                byte_index = bit_index // 8
                bit_offset = bit_index % 8  # LSB first
                data[byte_index] |= (1 << bit_offset)

    return bytes(data)

def create_moving_pattern_frame(frame_num: int) -> bytes:
    """
    Create a frame with a moving circle pattern.
    Positive channel: circle moving right
    Negative channel: circle moving left
    """
    # Circle parameters
    radius = 50

    # Positive circle: moves horizontally
    period_x = 200  # frames for one cycle
    cx_pos = int(WIDTH/2 + (WIDTH/3) * math.sin(2 * math.pi * frame_num / period_x))
    cy_pos = HEIGHT // 2

    # Negative circle: moves vertically, offset position
    period_y = 150
    cx_neg = WIDTH // 2
    cy_neg = int(HEIGHT/2 + (HEIGHT/3) * math.sin(2 * math.pi * frame_num / period_y))

    # Create both channels
    pos_data = create_circle_frame(cx_pos, cy_pos, radius, positive=True)
    neg_data = create_circle_frame(cx_neg, cy_neg, radius, positive=False)

    # Return combined frame (positive first, as per default config)
    return pos_data + neg_data


def send_frame_udp(sock: socket.socket, target: tuple, frame_data: bytes, packet_size: int):
    """
    Send a frame via UDP, splitting into multiple packets if necessary.

    Args:
        sock: UDP socket
        target: (ip, port) tuple
        frame_data: Complete frame data
        packet_size: Maximum bytes per UDP packet
    """
    offset = 0
    while offset < len(frame_data):
        chunk = frame_data[offset:offset + packet_size]
        sock.sendto(chunk, target)
        offset += len(chunk)


def main():
    parser = argparse.ArgumentParser(description="Fake camera simulator (UDP) for testing")
    parser.add_argument("--port", type=int, default=5000, help="UDP port to send to")
    parser.add_argument("--fps", type=int, default=500, help="Frames per second (must be > 0)")
    parser.add_argument("--target", type=str, default="127.0.0.1", help="Target IP address")
    parser.add_argument("--packet-size", type=int, default=DEFAULT_PACKET_SIZE,
                        help=f"UDP packet size (default: {DEFAULT_PACKET_SIZE})")
    args = parser.parse_args()

    # Validate arguments
    if args.fps <= 0:
        print(f"Error: --fps must be a positive integer, got {args.fps}", file=sys.stderr)
        sys.exit(1)

    if args.packet_size <= 0 or args.packet_size > 65535:
        print(f"Error: --packet-size must be between 1 and 65535, got {args.packet_size}", file=sys.stderr)
        sys.exit(1)

    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create UDP socket
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Set socket buffer size for high throughput
    try:
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 50 * 1024 * 1024)
    except OSError:
        print("Warning: Could not set large send buffer size")

    target = (args.target, args.port)
    packets_per_frame = (FRAME_SIZE + args.packet_size - 1) // args.packet_size

    print(f"Fake camera (UDP) sending to {args.target}:{args.port}")
    print(f"Frame size: {FRAME_SIZE} bytes ({WIDTH}x{HEIGHT}, {CHANNELS} channels)")
    print(f"Packet size: {args.packet_size} bytes ({packets_per_frame} packets per frame)")
    print(f"Target FPS: {args.fps}")
    print("Press Ctrl+C to stop...")
    print()

    frame_interval = 1.0 / args.fps
    frame_num = 0
    start_time = time.time()

    while running:
        # Generate frame
        frame_data = create_moving_pattern_frame(frame_num)

        try:
            # Send frame via UDP
            send_frame_udp(udp_socket, target, frame_data, args.packet_size)

            frame_num += 1

            # Print stats every 100 frames
            if frame_num % 100 == 0:
                elapsed = time.time() - start_time
                actual_fps = frame_num / elapsed if elapsed > 0 else 0
                throughput_mbps = (frame_num * FRAME_SIZE * 8) / (elapsed * 1_000_000) if elapsed > 0 else 0
                print(f"Sent {frame_num} frames | FPS: {actual_fps:.1f} | Throughput: {throughput_mbps:.1f} Mbps")

            # Rate limiting
            target_time = start_time + frame_num * frame_interval
            sleep_time = target_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)

        except OSError as e:
            if running:
                print(f"Send error: {e}")
            break

    udp_socket.close()
    print("Fake camera (UDP) shutdown complete")


if __name__ == "__main__":
    main()
