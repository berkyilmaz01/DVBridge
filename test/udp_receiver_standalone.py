#!/usr/bin/env python3
"""
Standalone UDP Receiver for FPGA Event Camera Testing

This script receives UDP frames from the FPGA and displays statistics.
No external dependencies required - works with standard Python 3.

Usage:
    python3 udp_receiver_standalone.py [--port 5000] [--width 1280] [--height 780]
"""

import socket
import time
import argparse
import signal
import sys

# Running flag for graceful shutdown
running = True

def signal_handler(sig, frame):
    global running
    print("\nShutting down...")
    running = False

def main():
    parser = argparse.ArgumentParser(description="Standalone UDP receiver for FPGA testing")
    parser.add_argument("--port", type=int, default=5000, help="UDP port to listen on")
    parser.add_argument("--width", type=int, default=1280, help="Frame width in pixels")
    parser.add_argument("--height", type=int, default=780, help="Frame height in pixels")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print each packet")
    args = parser.parse_args()

    # Calculate frame size (2 channels, 1 bit per pixel)
    bytes_per_channel = (args.width * args.height) // 8
    frame_size = 2 * bytes_per_channel

    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Set large receive buffer
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 50 * 1024 * 1024)
    except OSError:
        print("Warning: Could not set large receive buffer")

    sock.bind(("0.0.0.0", args.port))
    sock.settimeout(1.0)  # 1 second timeout for checking running flag

    print("=" * 50)
    print("  Standalone UDP Receiver for FPGA Testing")
    print("=" * 50)
    print(f"  Listening on port: {args.port}")
    print(f"  Frame size: {args.width} x {args.height}")
    print(f"  Expected frame bytes: {frame_size:,}")
    print(f"  Bytes per channel: {bytes_per_channel:,}")
    print("=" * 50)
    print("Waiting for UDP data...")
    print()

    # Statistics
    total_bytes = 0
    total_packets = 0
    total_frames = 0
    accumulated_bytes = 0
    leftover_bytes = b""
    start_time = None
    last_print_time = time.time()

    while running:
        try:
            data, addr = sock.recvfrom(65535)

            if start_time is None:
                start_time = time.time()
                print(f"First packet received from {addr[0]}:{addr[1]}")

            total_bytes += len(data)
            total_packets += 1

            # Accumulate bytes to form complete frames
            accumulated_bytes += len(data)

            # Count complete frames
            while accumulated_bytes >= frame_size:
                total_frames += 1
                accumulated_bytes -= frame_size

            if args.verbose:
                print(f"Packet: {len(data)} bytes from {addr[0]}:{addr[1]} | "
                      f"Accumulated: {accumulated_bytes}/{frame_size}")

            # Print stats every second
            now = time.time()
            if now - last_print_time >= 1.0 and start_time:
                elapsed = now - start_time
                fps = total_frames / elapsed if elapsed > 0 else 0
                mbps = (total_bytes * 8) / (elapsed * 1_000_000) if elapsed > 0 else 0
                pps = total_packets / elapsed if elapsed > 0 else 0

                print(f"Frames: {total_frames:,} | FPS: {fps:.1f} | "
                      f"Packets: {total_packets:,} | PPS: {pps:.0f} | "
                      f"Throughput: {mbps:.1f} Mbps | "
                      f"Pending: {accumulated_bytes}/{frame_size}")

                last_print_time = now

        except socket.timeout:
            continue
        except OSError as e:
            if running:
                print(f"Socket error: {e}")
            break

    # Final stats
    if start_time:
        elapsed = time.time() - start_time
        print()
        print("=" * 50)
        print("Final Statistics:")
        print(f"  Total frames: {total_frames:,}")
        print(f"  Total packets: {total_packets:,}")
        print(f"  Total bytes: {total_bytes:,}")
        print(f"  Duration: {elapsed:.2f} seconds")
        if elapsed > 0:
            print(f"  Average FPS: {total_frames / elapsed:.1f}")
            print(f"  Average throughput: {(total_bytes * 8) / (elapsed * 1_000_000):.1f} Mbps")
        print("=" * 50)

    sock.close()
    print("Receiver shutdown complete")


if __name__ == "__main__":
    main()
