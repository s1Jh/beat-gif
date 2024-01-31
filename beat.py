from pvrecorder import *
import pygame
import sys
import os
import time
import threading
from math import *

BPM=0
VARIANCE = 0
SENSITIVITY = 1.3
RESET = False
BEAT = False

def window_thread(folder, speed):
    global BPM, BEAT

    
    frames = []
    i = 1
    files = os.path.join(os.getcwd(), folder)

    if not os.path.exists(files):
        raise FileNotFoundError
    
    print(f"Loading from {files}")
    while os.path.exists(os.path.join(files, f"{i}.png")):
        path = os.path.join(files, f"{i}.png")
        print(f"Loading {path}")
        frames.append(pygame.image.load(path))
        i = i + 1
    
    pygame.display.set_icon(frames[0])

    pygame.font.init()
    font = pygame.font.SysFont("JetBrainsMono", 40)

    window = pygame.display.set_mode(size=frames[0].get_size())
    pygame.display.set_caption(f"live {folder} reaction")

    print(f"Loaded {len(frames)} frames")

    last_update = time.time()
    index = 0
    change_delta = 99999999

    last_frame = time.time()

    stat_update = 0
    stats = None

    reset = font.render("RESET", False, pygame.Color("red"))
    beat_text = font.render("BEAT", False, pygame.Color("green"))
    beat_text_time = 0

    while True:
        fps_delta = time.time() - last_frame
        last_frame = time.time()

        if BPM != 0:
            change_delta = 1 / (BPM / 60) * (speed / len(frames))

        time_now = time.time()
        if time_now - last_update > change_delta:
            last_update = time_now
            index = (index + 1) % len(frames)

        if time.time() - stat_update > 1:
            stats = font.render(f"BPM: {int(BPM)} (v: {int(VARIANCE*100000)/100000} c: {int(SENSITIVITY*100000)/100000})", False, pygame.Color("black"))
            stat_update = time.time()

        window.blit(frames[index], (0, 0))
        window.blit(stats, (0, 0))
        if RESET:  
            window.blit(reset, (0, 30))

        if BEAT:
            BEAT=False
            beat_text_time = time.time() + min(change_delta * 0.5, 0.3)

        if time.time() < beat_text_time:
            window.blit(beat_text, (0, 30))

        pygame.display.update()


def bpm_thread(device):
    global BPM, VARIANCE, SENSITIVITY, RESET, BEAT

    history = []
    recorder = PvRecorder(device_index=dev, frame_length=1024)

    this_avg = 0
    local_avg = 0
    avg_delta = 0

    last_time = time.time()

    delta_buffer = []

    log_time = time.time()

    next_expected_beat = 0

    try:
        recorder.start()

        while True:
            frame = [sample/0xffff for sample in recorder.read()]
            this_avg = sum([pow(sample, 2) for sample in frame]) / len(frame)

            history = [*frame, *history]
            history = history[0:min(len(history), 44100)]
            local_avg = sum([pow(sample, 2) for sample in history]) / len(history)
            VARIANCE = sum([pow(sample - local_avg, 2) for sample in history]) / len(history)


            if len(history) >= 44100:
                SENSITIVITY = min(max(-257.14 * VARIANCE + 1.5142857, 1.0), 2.0) 

            if time.time() - last_time > 10:
                print(f"RESET: {SENSITIVITY}")
                # SENSITIVITY = 1.3
                BPM = 0
                delta_buffer = []
                SENSITIVITY = 1.3
                RESET=True
            
            # print(f"history: {local_avg} (from {len(history)} samples) instant: {this_avg}")
            if (local_avg * SENSITIVITY < this_avg):
                new_time = time.time()
                delta = new_time - last_time

                if delta < (1/(250 / 60)):
                    print("discarding >250bpm")
                    continue

                if delta > (1/(50/60)):
                    print("discarding <10bpm")
                    last_time = new_time
                    continue
                
                # if len(delta_buffer) == 10:
                #     if delta < avg_delta * 0.8 or delta > avg_delta * 2:
                #         print("discard double hit")
                #         continue
                #     # runaway_diff = new_time - next_expected_beat 
                #     # runaway_ratio = runaway_diff / avg_delta
                #     # print(f"{runaway_diff} x {runaway_ratio}")
                    
                #     beat_ratio = delta / avg_delta
                #     missed_beats = max(round(beat_ratio), 0)
                #     beat_ratio_remainder = beat_ratio - missed_beats

                #     if beat_ratio_remainder > 0.2:
                #         print(f"discard ratio {beat_ratio_remainder} {beat_ratio} {missed_beats}")
                #         continue

                #     if missed_beats != 0:
                #         print(f"missed {int(missed_beats)} {avg_delta}/{delta} dev {beat_ratio_remainder}")
                #         delta = delta / (missed_beats)
                #         if abs(delta - avg_delta) > 0.05:
                #             print(f"Discard runaway {delta - avg_delta}")
                #             continue
                #         print(f"corrected: {delta}")
                # # if beat_ratio_remainder < 0.1:
                # #     print(f"Correcting {beat_ratio_remainder}")
                # #     delta = delta / (missed_beats_whole+1)

                last_time = new_time

                delta_buffer = [delta, *delta_buffer]
                delta_buffer = delta_buffer[0:min(len(delta_buffer), 100)]
                span = max(delta_buffer) - min(delta_buffer)
                
                avg_delta = sum(delta_buffer) / len(delta_buffer)

                RESET=False
                BEAT=True
                BPM = 60/avg_delta
                
                next_expected_beat = new_time + avg_delta

                print(f"delta={avg_delta} bpm={60/avg_delta} c={SENSITIVITY} v={VARIANCE} ƍ={60/span if span != 0 else 'inf.'} ({len(delta_buffer)} samples)")



            # Do something ...
    except KeyboardInterrupt:
        recorder.stop()
    finally:
        recorder.delete()

def start(dev, files, speed):
    bpm = threading.Thread(target=bpm_thread, args=(dev,))
    window = threading.Thread(target=window_thread, args=(files, speed,))

    bpm.start()
    window.start()

    bpm.join()
    window.join()

if __name__ == "__main__":
    if len(sys.argv) == 2:
        if sys.argv[1] == "list":
            for index, device in enumerate(PvRecorder.get_available_devices()):
                print(f"[{index}] {device}")
    elif len(sys.argv) == 4:
        files = sys.argv[2]
        speed = float(sys.argv[3])
        dev = int(sys.argv[1])
        start(dev, files, speed)
    else:
        print("kys")
