#!/usr/bin/env python3
"""
Fast UDP Camera Simulator - Pre-generates frames for maximum throughput
Matches converter config: 1280x780, UDP protocol

Usage:
    python3 fake_camera_udp_fast.py --port 5000 --fps 5000
"""

import socket
import time
import argparse
import signal
import sys
import math

# Frame configuration - MUST match config.hpp
WIDTH = 1280
HEIGHT = 780
CHANNELS = 2
BYTES_PER_CHANNEL = (WIDTH * HEIGHT) // 8  # 124,800 bytes
FRAME_SIZE = CHANNELS * BYTES_PER_CHANNEL   # 249,600 bytes

running = True

def signal_handler(sig, frame):
    global running
    print("\nShutting down...")
    running = False

def create_circle_frame(cx: int, cy: int, radius: int) -> bytes:
    """Create a binary frame with a filled circle."""
    data = bytearray(BYTES_PER_CHANNEL)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            dx = x - cx
            dy = y - cy
            if dx*dx + dy*dy <= radius*radius:
                bit_index = y * WIDTH + x
                byte_index = bit_index // 8
                bit_offset = bit_index % 8
                data[byte_index] |= (1 << bit_offset)
    return bytes(data)

def pregenerate_frames(num_frames: int) -> list:
    """Pre-generate frames with moving circle pattern."""
    print(f"Pre-generating {num_frames} frames...")
    frames = []
    radius = 50

    for frame_num in range(num_frames):
        # Positive circle: moves horizontally
        period_x = 200
        cx_pos = int(WIDTH/2 + (WIDTH/3) * math.sin(2 * math.pi * frame_num / period_x))
        cy_pos = HEIGHT // 2

        # Negative circle: moves vertically
        period_y = 150
        cx_neg = WIDTH // 2
        cy_neg = int(HEIGHT/2 + (HEIGHT/3) * math.sin(2 * math.pi * frame_num / period_y))

        pos_data = create_circle_frame(cx_pos, cy_pos, radius)
        neg_data = create_circle_frame(cx_neg, cy_neg, radius)

        frames.append(pos_data + neg_data)

        if (frame_num + 1) % 50 == 0:
            print(f"  Generated {frame_num + 1}/{num_frames} frames")

    print(f"Pre-generation complete!")
    return frames

def main():
    parser = argparse.ArgumentParser(description="Fast UDP camera simulator")
    parser.add_argument("--port", type=int, default=5000, help="UDP port")
    parser.add_argument("--target", type=str, default="127.0.0.1", help="Target IP")
    parser.add_argument("--fps", type=int, default=5000, help="Target FPS (0=unlimited)")
    parser.add_argument("--packet-size", type=int, default=8192, help="UDP packet size")
    parser.add_argument("--pregenerate", type=int, default=200, help="Number of frames to pre-generate")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Pre-generate frames with circle pattern (low event density)
    frames = pregenerate_frames(args.pregenerate)
    num_frames = len(frames)

    # Pre-split each frame into packets
    all_packets = []
    for frame_data in frames:
        packets = []
        offset = 0
        while offset < FRAME_SIZE:
            packets.append(frame_data[offset:offset + args.packet_size])
            offset += args.packet_size
        all_packets.append(packets)

    print(f"Frame size: {FRAME_SIZE:,} bytes ({WIDTH}x{HEIGHT})")
    print(f"Packets per frame: {len(all_packets[0])}")
    print(f"Target FPS: {args.fps if args.fps > 0 else 'unlimited'}")
    if args.fps > 0:
        print(f"Target throughput: {FRAME_SIZE * args.fps * 8 / 1_000_000:.1f} Mbps")
    print()

    # Create UDP socket with large buffer
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 50 * 1024 * 1024)

    target = (args.target, args.port)
    frame_interval = 1.0 / args.fps if args.fps > 0 else 0

    frame_num = 0
    start_time = time.time()
    last_print = start_time

    print(f"Sending to {args.target}:{args.port}...")
    print()

    while running:
        # Get pre-generated packets for this frame
        packets = all_packets[frame_num % num_frames]

        # Send all packets for one frame
        for packet in packets:
            sock.sendto(packet, target)

        frame_num += 1

        # Print stats every second
        now = time.time()
        if now - last_print >= 1.0:
            elapsed = now - start_time
            fps = frame_num / elapsed
            mbps = (frame_num * FRAME_SIZE * 8) / (elapsed * 1_000_000)
            print(f"Frames: {frame_num:,} | FPS: {fps:.0f} | Throughput: {mbps:.1f} Mbps")
            last_print = now

        # Rate limiting (skip if fps=0 for max speed)
        if frame_interval > 0:
            target_time = start_time + frame_num * frame_interval
            sleep_time = target_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)

    elapsed = time.time() - start_time
    print()
    print(f"Final: {frame_num:,} frames in {elapsed:.1f}s = {frame_num/elapsed:.0f} FPS")
    sock.close()

if __name__ == "__main__":
    main()
