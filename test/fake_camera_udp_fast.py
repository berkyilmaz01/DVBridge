#!/usr/bin/env python3
"""
Fast UDP Camera Simulator - Pre-generates frames for high FPS testing.
Uses numpy for FAST frame generation.

Usage:
    python3 fake_camera_udp_fast.py --port 5000 --fps 500 --target 127.0.0.1
"""

import socket
import time
import argparse
import signal
import sys
import numpy as np

# Frame configuration (must match config.hpp)
WIDTH = 1280
HEIGHT = 780
CHANNELS = 2
BYTES_PER_CHANNEL = (WIDTH * HEIGHT) // 8  # 124,800 bytes per channel
FRAME_SIZE = CHANNELS * BYTES_PER_CHANNEL   # 249,600 bytes

running = True

def signal_handler(sig, frame):
    global running
    print("\nShutting down...")
    running = False

def create_circle_frame_fast(cx: int, cy: int, radius: int) -> bytes:
    """Create a binary frame with a filled circle using numpy (FAST)."""
    y, x = np.ogrid[:HEIGHT, :WIDTH]
    mask = (x - cx)**2 + (y - cy)**2 <= radius**2
    # Pack bits into bytes
    bits = mask.flatten().astype(np.uint8)
    # Reshape to groups of 8 and pack
    bits_padded = np.pad(bits, (0, (8 - len(bits) % 8) % 8), constant_values=0)
    bytes_arr = np.packbits(bits_padded, bitorder='little')
    return bytes(bytes_arr[:BYTES_PER_CHANNEL])

def pregenerate_frames(num_frames: int) -> list:
    """Pre-generate all frames using numpy (FAST)."""
    print(f"Pre-generating {num_frames} frames with numpy...")
    frames = []
    radius = 50

    for frame_num in range(num_frames):
        # Positive circle: moves horizontally
        period_x = 200
        cx_pos = int(WIDTH/2 + (WIDTH/3) * np.sin(2 * np.pi * frame_num / period_x))
        cy_pos = HEIGHT // 2

        # Negative circle: moves vertically
        period_y = 150
        cx_neg = WIDTH // 2
        cy_neg = int(HEIGHT/2 + (HEIGHT/3) * np.sin(2 * np.pi * frame_num / period_y))

        pos_data = create_circle_frame_fast(cx_pos, cy_pos, radius)
        neg_data = create_circle_frame_fast(cx_neg, cy_neg, radius)

        frames.append(pos_data + neg_data)

        if (frame_num + 1) % 100 == 0:
            print(f"  Generated {frame_num + 1}/{num_frames} frames")

    print(f"Pre-generation complete. Frame size: {FRAME_SIZE} bytes")
    return frames

def main():
    parser = argparse.ArgumentParser(description="Fast UDP camera for high FPS testing")
    parser.add_argument("--port", type=int, default=5000, help="UDP port")
    parser.add_argument("--target", type=str, default="127.0.0.1", help="Target IP address")
    parser.add_argument("--fps", type=int, default=500, help="Target FPS")
    parser.add_argument("--pregenerate", type=int, default=500, help="Number of frames to pre-generate")
    parser.add_argument("--no-ratelimit", action="store_true", help="Send as fast as possible")
    parser.add_argument("--packet-size", type=int, default=65000, help="UDP packet size (use large for loopback)")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Pre-generate frames
    frames = pregenerate_frames(args.pregenerate)
    num_frames = len(frames)

    # Pre-split frames into UDP packets
    all_packets = []
    for frame_data in frames:
        packets = []
        offset = 0
        while offset < len(frame_data):
            packets.append(frame_data[offset:offset + args.packet_size])
            offset += args.packet_size
        all_packets.append(packets)

    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 50 * 1024 * 1024)  # 50MB buffer

    target = (args.target, args.port)

    print(f"\nFast UDP camera sending to {args.target}:{args.port}")
    print(f"Frame size: {FRAME_SIZE:,} bytes ({WIDTH}x{HEIGHT})")
    print(f"Packets per frame: {len(all_packets[0])} (packet size: {args.packet_size})")
    print(f"Target FPS: {args.fps} {'(no rate limit)' if args.no_ratelimit else ''}")
    print("Sending...")

    frame_interval = 1.0 / args.fps

    frame_idx = 0
    total_sent = 0
    start_time = time.time()

    while running:
        packets = all_packets[frame_idx % num_frames]

        try:
            # Send all packets for this frame
            for packet in packets:
                sock.sendto(packet, target)

            frame_idx += 1
            total_sent += 1

            if total_sent % 500 == 0:
                elapsed = time.time() - start_time
                actual_fps = total_sent / elapsed if elapsed > 0 else 0
                mbps = (total_sent * FRAME_SIZE * 8) / (elapsed * 1_000_000) if elapsed > 0 else 0
                print(f"Sent {total_sent} frames | FPS: {actual_fps:.1f} | Throughput: {mbps:.1f} Mbps")

            # Rate limiting
            if not args.no_ratelimit:
                target_time = start_time + total_sent * frame_interval
                sleep_time = target_time - time.time()
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except OSError as e:
            if running:
                print(f"Send error: {e}")
            break

    sock.close()
    elapsed = time.time() - start_time
    print(f"\nFinal: {total_sent} frames in {elapsed:.1f}s = {total_sent/elapsed:.1f} FPS")
    print("Fast UDP camera shutdown complete")

if __name__ == "__main__":
    main()
