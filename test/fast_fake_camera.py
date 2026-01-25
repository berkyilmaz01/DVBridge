#!/usr/bin/env python3
"""
Fast Fake Camera - Pre-generates frames for high FPS testing.
Can achieve 500+ FPS by eliminating per-frame computation.
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
CHANNELS = 2
BYTES_PER_CHANNEL = (WIDTH * HEIGHT) // 8
FRAME_SIZE = CHANNELS * BYTES_PER_CHANNEL

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
    """Pre-generate all frames for smooth playback."""
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

        if (frame_num + 1) % 100 == 0:
            print(f"  Generated {frame_num + 1}/{num_frames} frames")

    print(f"Pre-generation complete. Frame size: {FRAME_SIZE} bytes")
    return frames

def main():
    parser = argparse.ArgumentParser(description="Fast fake camera for high FPS testing")
    parser.add_argument("--port", type=int, default=5000, help="TCP port")
    parser.add_argument("--fps", type=int, default=500, help="Target FPS")
    parser.add_argument("--pregenerate", type=int, default=500, help="Number of frames to pre-generate")
    parser.add_argument("--no-header", action="store_true", help="Don't send frame size header")
    parser.add_argument("--no-ratelimit", action="store_true", help="Send as fast as possible")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Pre-generate frames
    frames = pregenerate_frames(args.pregenerate)
    num_frames = len(frames)

    # Pre-generate headers if needed
    if not args.no_header:
        header = struct.pack("<I", FRAME_SIZE)

    # Create server socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 50 * 1024 * 1024)  # 50MB buffer
    server_socket.bind(("0.0.0.0", args.port))
    server_socket.listen(1)
    server_socket.settimeout(1.0)

    print(f"\nFast camera listening on port {args.port}")
    print(f"Target FPS: {args.fps} {'(no rate limit)' if args.no_ratelimit else ''}")
    print("Waiting for connection...")

    frame_interval = 1.0 / args.fps

    while running:
        try:
            client_socket, addr = server_socket.accept()
            client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 50 * 1024 * 1024)
            print(f"Client connected from {addr}")

            frame_idx = 0
            total_sent = 0
            start_time = time.time()

            while running:
                frame_data = frames[frame_idx % num_frames]

                try:
                    if not args.no_header:
                        client_socket.sendall(header)
                    client_socket.sendall(frame_data)

                    frame_idx += 1
                    total_sent += 1

                    if total_sent % 500 == 0:
                        elapsed = time.time() - start_time
                        actual_fps = total_sent / elapsed if elapsed > 0 else 0
                        print(f"Sent {total_sent} frames, FPS: {actual_fps:.1f}")

                    # Rate limiting
                    if not args.no_ratelimit:
                        target_time = start_time + total_sent * frame_interval
                        sleep_time = target_time - time.time()
                        if sleep_time > 0:
                            time.sleep(sleep_time)

                except (BrokenPipeError, ConnectionResetError):
                    print("Client disconnected")
                    break

            client_socket.close()

        except socket.timeout:
            continue
        except Exception as e:
            if running:
                print(f"Error: {e}")
            break

    server_socket.close()
    print("Fast camera shutdown complete")

if __name__ == "__main__":
    main()
