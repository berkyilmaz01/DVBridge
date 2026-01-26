#!/usr/bin/env python3
"""
Fake Camera Simulator for TCP-to-AEDAT4 Converter Testing

Generates binary frames with a moving circle pattern and sends via TCP.
This simulates the FPGA/chip output that the converter expects.

Usage:
    python3 fake_camera.py [--port 5000] [--fps 500] [--no-header]
"""

import socket
import struct
import time
import argparse
import signal
import sys
import math

# Frame configuration (must match config.hpp)
# 2048x2048 = 1MB frames for high-volume testing
WIDTH = 2048
HEIGHT = 2048
CHANNELS = 2  # positive and negative
BYTES_PER_CHANNEL = (WIDTH * HEIGHT) // 8  # 524,288 bytes per channel
FRAME_SIZE = CHANNELS * BYTES_PER_CHANNEL   # 1,048,576 bytes (1 MB)

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


def main():
    parser = argparse.ArgumentParser(description="Fake camera simulator for testing")
    parser.add_argument("--port", type=int, default=5000, help="TCP port to listen on")
    parser.add_argument("--fps", type=int, default=500, help="Frames per second (must be > 0)")
    parser.add_argument("--no-header", action="store_true", help="Don't send frame size header")
    args = parser.parse_args()

    # Validate FPS argument
    if args.fps <= 0:
        print(f"Error: --fps must be a positive integer, got {args.fps}", file=sys.stderr)
        sys.exit(1)

    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create TCP server socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("0.0.0.0", args.port))
    server_socket.listen(1)
    server_socket.settimeout(1.0)  # Allow checking running flag

    print(f"Fake camera listening on port {args.port}")
    print(f"Frame size: {FRAME_SIZE} bytes ({WIDTH}x{HEIGHT}, {CHANNELS} channels)")
    print(f"Target FPS: {args.fps}")
    print(f"Header: {'disabled' if args.no_header else 'enabled (4 bytes)'}")
    print("Waiting for connection...")

    frame_interval = 1.0 / args.fps

    while running:
        try:
            client_socket, addr = server_socket.accept()
            print(f"Client connected from {addr}")

            frame_num = 0
            start_time = time.time()

            while running:
                # Generate frame
                frame_data = create_moving_pattern_frame(frame_num)

                try:
                    # Send header if enabled
                    if not args.no_header:
                        header = struct.pack("<I", len(frame_data))
                        client_socket.sendall(header)

                    # Send frame data
                    client_socket.sendall(frame_data)

                    frame_num += 1

                    # Print stats every 100 frames
                    if frame_num % 100 == 0:
                        elapsed = time.time() - start_time
                        actual_fps = frame_num / elapsed if elapsed > 0 else 0
                        print(f"Sent {frame_num} frames, FPS: {actual_fps:.1f}")

                    # Rate limiting
                    target_time = start_time + frame_num * frame_interval
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
    print("Fake camera shutdown complete")


if __name__ == "__main__":
    main()
