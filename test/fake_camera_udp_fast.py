#!/usr/bin/env python3
"""
Fast UDP Camera Simulator - Pre-computes frames ONCE, sends at MAX SPEED.
For 9+ Gbps throughput testing.

Usage:
    python3 fake_camera_udp_fast.py --port 5000 --no-ratelimit --target 127.0.0.1

    # For sparse data (realistic camera, fast processing):
    python3 fake_camera_udp_fast.py --port 5000 --no-ratelimit --sparse

    # For random data (stress test, slow processing):
    python3 fake_camera_udp_fast.py --port 5000 --no-ratelimit --random
"""

import socket
import time
import argparse
import signal
import sys
import os

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

def create_sparse_frame(density=0.01):
    """Create sparse frame data like real camera output.

    Real event cameras have very sparse data - typically <5% of pixels
    have events in any given frame. This allows the unpacker to skip
    most bytes (zero bytes are skipped entirely).

    density: fraction of bits that are 1 (0.01 = 1% = ~10K events per frame)
    """
    import random
    data = bytearray(FRAME_SIZE)
    num_bytes_to_set = int(FRAME_SIZE * density * 8 / 8)  # Approximate

    # Randomly set some bytes to have a few bits set
    for _ in range(num_bytes_to_set):
        idx = random.randint(0, FRAME_SIZE - 1)
        # Set 1-3 random bits in this byte
        bits_to_set = random.randint(1, 3)
        for _ in range(bits_to_set):
            bit = random.randint(0, 7)
            data[idx] |= (1 << bit)

    return bytes(data)

def main():
    parser = argparse.ArgumentParser(description="Fast UDP camera - 9Gbps throughput test")
    parser.add_argument("--port", type=int, default=5000, help="UDP port")
    parser.add_argument("--target", type=str, default="127.0.0.1", help="Target IP address")
    parser.add_argument("--fps", type=int, default=5000, help="Target FPS (ignored if --no-ratelimit)")
    parser.add_argument("--no-ratelimit", action="store_true", help="Send as fast as possible (for max throughput)")
    parser.add_argument("--packet-size", type=int, default=65000, help="UDP packet size")
    parser.add_argument("--sparse", action="store_true", help="Use sparse data like real camera (fast processing)")
    parser.add_argument("--random", action="store_true", help="Use random data (slow processing, stress test)")
    parser.add_argument("--density", type=float, default=0.02, help="Event density for sparse mode (default 2%%)")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Pre-generate ONE frame
    print("Pre-generating frame data...")
    if args.random:
        print("  Mode: RANDOM (50% density - slow processing, stress test)")
        frame_data = os.urandom(FRAME_SIZE)
    elif args.sparse:
        print(f"  Mode: SPARSE ({args.density*100:.1f}% density - fast processing, realistic)")
        frame_data = create_sparse_frame(args.density)
    else:
        # Default: all zeros (fastest processing - 0 events)
        print("  Mode: ZEROS (0% density - fastest processing)")
        print("  Use --sparse for realistic data or --random for stress test")
        frame_data = bytes(FRAME_SIZE)

    # Pre-split into UDP packets (do this ONCE)
    packets = []
    offset = 0
    while offset < FRAME_SIZE:
        packets.append(frame_data[offset:offset + args.packet_size])
        offset += args.packet_size

    print(f"Frame size: {FRAME_SIZE:,} bytes ({WIDTH}x{HEIGHT})")
    print(f"Packets per frame: {len(packets)} (packet size: {args.packet_size})")
    print(f"Rate: {'MAX SPEED (no rate limit)' if args.no_ratelimit else f'{args.fps} FPS'}")

    # Count events in frame to show expected load
    event_count = sum(bin(b).count('1') for b in frame_data)
    print(f"Events per frame: ~{event_count:,} ({event_count*100/(WIDTH*HEIGHT*2):.1f}% density)")

    # Create UDP socket with LARGE buffer
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 50 * 1024 * 1024)  # 50MB buffer

    target = (args.target, args.port)
    frame_interval = 1.0 / args.fps if args.fps > 0 else 0

    print(f"\nSending to {args.target}:{args.port}...")
    print()

    frame_num = 0
    start_time = time.time()
    last_print = start_time

    while running:
        try:
            # Send all packets for one frame (pre-computed!)
            for packet in packets:
                sock.sendto(packet, target)

            frame_num += 1

            # Print stats every second
            now = time.time()
            if now - last_print >= 1.0:
                elapsed = now - start_time
                fps = frame_num / elapsed
                mbps = (frame_num * FRAME_SIZE * 8) / (elapsed * 1_000_000)
                gbps = mbps / 1000
                print(f"Frames: {frame_num:,} | FPS: {fps:.0f} | Throughput: {mbps:.0f} Mbps ({gbps:.2f} Gbps)")
                last_print = now

            # Rate limiting (skip if --no-ratelimit for MAX SPEED)
            if not args.no_ratelimit and frame_interval > 0:
                target_time = start_time + frame_num * frame_interval
                sleep_time = target_time - time.time()
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except OSError as e:
            if running:
                print(f"Send error: {e}")
            break

    elapsed = time.time() - start_time
    fps = frame_num / elapsed if elapsed > 0 else 0
    mbps = (frame_num * FRAME_SIZE * 8) / (elapsed * 1_000_000) if elapsed > 0 else 0
    gbps = mbps / 1000

    print()
    print(f"Final: {frame_num:,} frames in {elapsed:.1f}s")
    print(f"       {fps:.0f} FPS | {mbps:.0f} Mbps ({gbps:.2f} Gbps)")
    sock.close()

if __name__ == "__main__":
    main()
