#!/usr/bin/env python3
"""
DVBridge Event Viewer (High-Performance)

Connects to DVBridge output (port 7777) and displays events in real-time.
Optimized for 10Gbps throughput and high event rates (10M+ events/sec).

Works with the full pipeline: Camera (10GbE) → DVBridge → This Viewer

Usage:
    pip install dv-processing opencv-python numpy
    python viewer.py
    python viewer.py --port 7777 --host 127.0.0.1

Controls:
    Q or ESC: Quit
    S: Save screenshot
    R: Toggle recording
    C: Clear accumulated frame
    +/-: Adjust decay rate
"""

import cv2
import numpy as np
import argparse
import time
import sys
from collections import deque

try:
    import dv_processing as dv
except ImportError:
    print("Error: dv-processing not installed")
    print("Install with: pip install dv-processing")
    sys.exit(1)


class EventVisualizer:
    def __init__(self, host="127.0.0.1", port=7777, width=1280, height=720):
        self.host = host
        self.port = port
        self.width = width
        self.height = height
        
        # Accumulator for visualization (use float for smooth decay)
        self.frame_pos = np.zeros((height, width), dtype=np.float32)  # Positive events
        self.frame_neg = np.zeros((height, width), dtype=np.float32)  # Negative events
        self.decay_factor = 0.92  # How fast events fade (adjustable)
        
        # Stats tracking with rolling window for accurate rates
        self.total_events = 0
        self.frame_count = 0
        self.start_time = time.time()
        self.events_window = deque(maxlen=30)  # Last 30 measurements
        self.last_stats_time = time.time()
        self.events_per_second = 0
        self.display_fps = 0
        self.last_display_time = time.time()
        self.throughput_mbps = 0
        
        # Recording
        self.recording = False
        self.video_writer = None
        
    def connect(self):
        """Connect to DVBridge"""
        print(f"Connecting to DVBridge at {self.host}:{self.port}...")
        try:
            self.reader = dv.io.NetworkReader(self.host, self.port)
            print("Connected!")
            return True
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False
    
    def process_events(self, events):
        """Draw events on frame using vectorized numpy operations (FAST)"""
        if events is None or len(events) == 0:
            return 0
        
        # Decay existing frames (vectorized - fast)
        self.frame_pos *= self.decay_factor
        self.frame_neg *= self.decay_factor
        
        # Extract event data as numpy arrays (vectorized - fast)
        num_events = len(events)
        
        # Get coordinates and polarities using numpy
        coords = events.coordinates()  # Returns Nx2 numpy array
        polarities = events.polarities()  # Returns N numpy array
        
        # Clip coordinates to valid range
        x = np.clip(coords[:, 0], 0, self.width - 1).astype(np.int32)
        y = np.clip(coords[:, 1], 0, self.height - 1).astype(np.int32)
        
        # Separate positive and negative events
        pos_mask = polarities == True
        neg_mask = ~pos_mask
        
        # Draw positive events (green) - vectorized
        if np.any(pos_mask):
            np.add.at(self.frame_pos, (y[pos_mask], x[pos_mask]), 1.0)
        
        # Draw negative events (red) - vectorized
        if np.any(neg_mask):
            np.add.at(self.frame_neg, (y[neg_mask], x[neg_mask]), 1.0)
        
        # Clamp values
        np.clip(self.frame_pos, 0, 1, out=self.frame_pos)
        np.clip(self.frame_neg, 0, 1, out=self.frame_neg)
        
        self.total_events += num_events
        self.frame_count += 1
        
        return num_events
    
    def get_display_frame(self):
        """Convert accumulated events to RGB display frame"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Green channel for positive events
        frame[:, :, 1] = (self.frame_pos * 255).astype(np.uint8)
        
        # Red channel for negative events  
        frame[:, :, 2] = (self.frame_neg * 255).astype(np.uint8)
        
        return frame
    
    def update_stats(self, events_this_batch):
        """Update statistics with rolling window for accurate measurement"""
        now = time.time()
        
        # Track events in rolling window
        self.events_window.append((now, events_this_batch))
        
        # Calculate events/sec from rolling window (more accurate)
        if len(self.events_window) >= 2:
            window_start = self.events_window[0][0]
            window_duration = now - window_start
            window_events = sum(e[1] for e in self.events_window)
            if window_duration > 0:
                self.events_per_second = window_events / window_duration
                # Estimate throughput (assuming ~8 bytes per event in AEDAT4)
                self.throughput_mbps = (window_events * 8 * 8) / (window_duration * 1_000_000)
        
        # Calculate display FPS
        display_elapsed = now - self.last_display_time
        if display_elapsed > 0:
            self.display_fps = 1.0 / display_elapsed
        self.last_display_time = now
    
    def draw_stats(self, display_frame):
        """Draw statistics overlay"""
        elapsed = time.time() - self.start_time
        
        # Draw background for text
        cv2.rectangle(display_frame, (5, 5), (320, 135), (0, 0, 0), -1)
        cv2.rectangle(display_frame, (5, 5), (320, 135), (100, 100, 100), 1)
        
        # Format large numbers
        def fmt_num(n):
            if n >= 1_000_000:
                return f"{n/1_000_000:.2f}M"
            elif n >= 1_000:
                return f"{n/1_000:.1f}K"
            return f"{n:.0f}"
        
        # Draw stats
        stats = [
            f"Events/sec: {fmt_num(self.events_per_second)}",
            f"Total events: {fmt_num(self.total_events)}",
            f"Display FPS: {self.display_fps:.1f}",
            f"Throughput: {self.throughput_mbps:.1f} Mbps",
            f"Decay: {self.decay_factor:.2f}",
            f"Recording: {'ON' if self.recording else 'OFF'}"
        ]
        
        for i, text in enumerate(stats):
            color = (0, 255, 0) if "Recording: ON" in text else (255, 255, 255)
            cv2.putText(display_frame, text, (10, 25 + i * 18),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        return display_frame
    
    def save_screenshot(self):
        """Save current frame as image"""
        filename = f"screenshot_{int(time.time())}.png"
        frame = self.get_display_frame()
        cv2.imwrite(filename, frame)
        print(f"Screenshot saved: {filename}")
    
    def toggle_recording(self):
        """Toggle video recording"""
        if self.recording:
            self.recording = False
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
            print("Recording stopped")
        else:
            filename = f"recording_{int(time.time())}.avi"
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            self.video_writer = cv2.VideoWriter(filename, fourcc, 30, 
                                                 (self.width, self.height))
            self.recording = True
            print(f"Recording started: {filename}")
    
    def run(self):
        """Main visualization loop - optimized for high throughput"""
        if not self.connect():
            return
        
        print("\nControls:")
        print("  Q/ESC: Quit")
        print("  S: Screenshot")
        print("  R: Toggle recording")
        print("  C: Clear frame")
        print("  +/-: Adjust decay rate")
        print()
        print("Performance tips:")
        print("  - Viewer runs on localhost, separate from 10GbE camera link")
        print("  - DVBridge handles the heavy lifting")
        print("  - Display FPS is independent of camera FPS")
        print()
        
        cv2.namedWindow("DVBridge Viewer", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("DVBridge Viewer", 1280, 720)
        
        batch_events = 0
        
        try:
            while True:
                # Get events from DVBridge (non-blocking batches)
                events = self.reader.getNextEventBatch()
                
                if events is not None:
                    batch_events = self.process_events(events)
                else:
                    batch_events = 0
                
                # Update statistics
                self.update_stats(batch_events)
                
                # Create display frame with stats
                display_frame = self.get_display_frame()
                display_frame = self.draw_stats(display_frame)
                
                # Show frame
                cv2.imshow("DVBridge Viewer", display_frame)
                
                # Record if enabled
                if self.recording and self.video_writer:
                    self.video_writer.write(display_frame)
                
                # Handle keyboard input (1ms wait - keeps loop fast)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:  # Q or ESC
                    break
                elif key == ord('s'):
                    self.save_screenshot()
                elif key == ord('r'):
                    self.toggle_recording()
                elif key == ord('c'):
                    self.frame_pos = np.zeros((self.height, self.width), dtype=np.float32)
                    self.frame_neg = np.zeros((self.height, self.width), dtype=np.float32)
                    print("Frame cleared")
                elif key == ord('+') or key == ord('='):
                    self.decay_factor = min(0.99, self.decay_factor + 0.01)
                    print(f"Decay: {self.decay_factor:.2f}")
                elif key == ord('-'):
                    self.decay_factor = max(0.80, self.decay_factor - 0.01)
                    print(f"Decay: {self.decay_factor:.2f}")
                    
        except KeyboardInterrupt:
            print("\nInterrupted")
        finally:
            if self.video_writer:
                self.video_writer.release()
            cv2.destroyAllWindows()
            
            # Print final stats
            elapsed = time.time() - self.start_time
            print(f"\n{'='*50}")
            print(f"Session Statistics")
            print(f"{'='*50}")
            print(f"  Duration: {elapsed:.1f} seconds")
            print(f"  Total events: {self.total_events:,}")
            if elapsed > 0:
                avg_rate = self.total_events / elapsed
                print(f"  Average events/sec: {avg_rate:,.0f}")
                print(f"  Average throughput: {(avg_rate * 8 * 8) / 1_000_000:.1f} Mbps")
            print(f"{'='*50}")


def main():
    parser = argparse.ArgumentParser(description="DVBridge Event Viewer")
    parser.add_argument("--host", type=str, default="127.0.0.1",
                        help="DVBridge host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=7777,
                        help="DVBridge port (default: 7777)")
    parser.add_argument("--width", type=int, default=1280,
                        help="Frame width (default: 1280)")
    parser.add_argument("--height", type=int, default=720,
                        help="Frame height (default: 720)")
    args = parser.parse_args()
    
    print("=" * 50)
    print("  DVBridge Event Viewer")
    print("=" * 50)
    
    visualizer = EventVisualizer(
        host=args.host,
        port=args.port,
        width=args.width,
        height=args.height
    )
    visualizer.run()


if __name__ == "__main__":
    main()
