import os
import random
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox

CHIP8_MEMORY_SIZE = 4096
CHIP8_START = 0x200
MAX_ROM = CHIP8_MEMORY_SIZE - CHIP8_START
MAX_STACK = 16
SCREEN_WIDTH = 64
SCREEN_HEIGHT = 32
CPU_HZ = 500
TIMER_HZ = 60

FONTSET = [
    0xF0, 0x90, 0x90, 0x90, 0xF0,
    0x20, 0x60, 0x20, 0x20, 0x70,
    0xF0, 0x10, 0xF0, 0x80, 0xF0,
    0xF0, 0x10, 0xF0, 0x10, 0xF0,
    0x90, 0x90, 0xF0, 0x10, 0x10,
    0xF0, 0x80, 0xF0, 0x10, 0xF0,
    0xF0, 0x80, 0xF0, 0x90, 0xF0,
    0xF0, 0x10, 0x20, 0x40, 0x40,
    0xF0, 0x90, 0xF0, 0x90, 0xF0,
    0xF0, 0x90, 0xF0, 0x10, 0xF0,
    0xF0, 0x90, 0xF0, 0x90, 0x90,
    0xE0, 0x90, 0xE0, 0x90, 0xE0,
    0xF0, 0x80, 0x80, 0x80, 0xF0,
    0xE0, 0x90, 0x90, 0x90, 0xE0,
    0xF0, 0x80, 0xF0, 0x80, 0xF0,
    0xF0, 0x80, 0xF0, 0x80, 0x80,
]

# Built-in demo ROM (no external files needed)
DEFAULT_ROM = bytes.fromhex("00e0621c630ca20ad235ffffffffff1210")

KEY_MAP = {
    "1": 0x1, "2": 0x2, "3": 0x3, "4": 0xC,
    "q": 0x4, "w": 0x5, "e": 0x6, "r": 0xD,
    "a": 0x7, "s": 0x8, "d": 0x9, "f": 0xE,
    "z": 0xA, "x": 0x0, "c": 0xB, "v": 0xF,
}


class Chip8:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.memory = bytearray(CHIP8_MEMORY_SIZE)
        self.V = bytearray(16)
        self.I = 0
        self.pc = CHIP8_START
        self.stack: list[int] = []
        self.delay_timer = 0
        self.sound_timer = 0
        self.display = [0] * (SCREEN_WIDTH * SCREEN_HEIGHT)
        self.draw_flag = False
        self.keys = [0] * 16
        self.waiting_for_key = False
        self.wait_key_reg = 0
        for i, byte in enumerate(FONTSET):
            self.memory[i] = byte

    def load_rom_bytes(self, rom: bytes) -> bool:
        if not rom:
            return False
        if len(rom) > MAX_ROM:
            return False
        self.reset()
        for i, byte in enumerate(rom):
            self.memory[CHIP8_START + i] = byte
        return True

    def cycle(self) -> None:
        if self.waiting_for_key:
            for k in range(16):
                if self.keys[k]:
                    self.V[self.wait_key_reg] = k
                    self.waiting_for_key = False
                    return
            return

        if self.pc + 1 >= CHIP8_MEMORY_SIZE:
            return

        opcode = (self.memory[self.pc] << 8) | self.memory[self.pc + 1]
        self.pc += 2

        x = (opcode & 0x0F00) >> 8
        y = (opcode & 0x00F0) >> 4
        n = opcode & 0x000F
        nn = opcode & 0x00FF
        nnn = opcode & 0x0FFF

        if opcode == 0x00E0:
            self.display = [0] * (SCREEN_WIDTH * SCREEN_HEIGHT)
            self.draw_flag = True
        elif opcode == 0x00EE:
            if self.stack:
                self.pc = self.stack.pop()
        elif (opcode & 0xF000) == 0x1000:
            self.pc = nnn
        elif (opcode & 0xF000) == 0x2000:
            if len(self.stack) < MAX_STACK:
                self.stack.append(self.pc)
                self.pc = nnn
        elif (opcode & 0xF000) == 0x3000:
            if self.V[x] == nn:
                self.pc += 2
        elif (opcode & 0xF000) == 0x4000:
            if self.V[x] != nn:
                self.pc += 2
        elif (opcode & 0xF000) == 0x5000 and n == 0:
            if self.V[x] == self.V[y]:
                self.pc += 2
        elif (opcode & 0xF000) == 0x6000:
            self.V[x] = nn
        elif (opcode & 0xF000) == 0x7000:
            self.V[x] = (self.V[x] + nn) & 0xFF
        elif (opcode & 0xF000) == 0x8000:
            if n == 0:
                self.V[x] = self.V[y]
            elif n == 1:
                self.V[x] |= self.V[y]
            elif n == 2:
                self.V[x] &= self.V[y]
            elif n == 3:
                self.V[x] ^= self.V[y]
            elif n == 4:
                total = self.V[x] + self.V[y]
                self.V[0xF] = 1 if total > 0xFF else 0
                self.V[x] = total & 0xFF
            elif n == 5:
                self.V[0xF] = 1 if self.V[x] >= self.V[y] else 0
                self.V[x] = (self.V[x] - self.V[y]) & 0xFF
            elif n == 6:
                self.V[0xF] = self.V[x] & 1
                self.V[x] >>= 1
            elif n == 7:
                self.V[0xF] = 1 if self.V[y] >= self.V[x] else 0
                self.V[x] = (self.V[y] - self.V[x]) & 0xFF
            elif n == 0xE:
                self.V[0xF] = (self.V[x] >> 7) & 1
                self.V[x] = (self.V[x] << 1) & 0xFF
        elif (opcode & 0xF000) == 0x9000 and n == 0:
            if self.V[x] != self.V[y]:
                self.pc += 2
        elif (opcode & 0xF000) == 0xA000:
            self.I = nnn
        elif (opcode & 0xF000) == 0xB000:
            self.pc = nnn + self.V[0]
        elif (opcode & 0xF000) == 0xC000:
            self.V[x] = random.randint(0, 255) & nn
        elif (opcode & 0xF000) == 0xD000:
            self.V[0xF] = 0
            px = self.V[x] % SCREEN_WIDTH
            py = self.V[y] % SCREEN_HEIGHT
            for row in range(n):
                sprite_byte = self.memory[self.I + row]
                for col in range(8):
                    if sprite_byte & (0x80 >> col):
                        cx = px + col
                        cy = py + row
                        if cx >= SCREEN_WIDTH or cy >= SCREEN_HEIGHT:
                            continue
                        idx = cy * SCREEN_WIDTH + cx
                        if self.display[idx]:
                            self.V[0xF] = 1
                        self.display[idx] ^= 1
            self.draw_flag = True
        elif (opcode & 0xF000) == 0xE000:
            key = self.V[x] & 0xF
            if nn == 0x9E:
                if self.keys[key]:
                    self.pc += 2
            elif nn == 0xA1:
                if not self.keys[key]:
                    self.pc += 2
        elif (opcode & 0xF000) == 0xF000:
            if nn == 0x07:
                self.V[x] = self.delay_timer
            elif nn == 0x0A:
                for k in range(16):
                    if self.keys[k]:
                        self.V[x] = k
                        break
                else:
                    self.waiting_for_key = True
                    self.wait_key_reg = x
                    self.pc -= 2
            elif nn == 0x15:
                self.delay_timer = self.V[x]
            elif nn == 0x18:
                self.sound_timer = self.V[x]
            elif nn == 0x1E:
                self.I = (self.I + self.V[x]) & 0xFFF
            elif nn == 0x29:
                self.I = (self.V[x] & 0xF) * 5
            elif nn == 0x33:
                val = self.V[x]
                self.memory[self.I] = val // 100
                self.memory[self.I + 1] = (val // 10) % 10
                self.memory[self.I + 2] = val % 10
            elif nn == 0x55:
                for i in range(x + 1):
                    self.memory[self.I + i] = self.V[i]
            elif nn == 0x65:
                for i in range(x + 1):
                    self.V[i] = self.memory[self.I + i]

    def update_timers(self) -> None:
        if self.delay_timer > 0:
            self.delay_timer -= 1
        if self.sound_timer > 0:
            self.sound_timer -= 1

    def key_pressed(self, key: str) -> None:
        k = KEY_MAP.get(key.lower())
        if k is None:
            return
        self.keys[k] = 1
        if self.waiting_for_key:
            self.V[self.wait_key_reg] = k
            self.waiting_for_key = False

    def key_released(self, key: str) -> None:
        k = KEY_MAP.get(key.lower())
        if k is not None:
            self.keys[k] = 0


class Chip8Emulator:
    def __init__(self, root: tk.Tk, rom_bytes: bytes | None = None, rom_label: str = "Demo (built-in)") -> None:
        self.root = root
        self.root.title("ac's chip 8 emu 0.1")
        self.root.geometry("600x400")
        self.root.resizable(False, False)

        self.bg_color = "#0a192f"
        self.text_color = "#00b4d8"
        self.button_bg = "#000000"
        self.button_fg = "#00b4d8"
        self.screen_bg = "#020c1b"

        self.root.configure(bg=self.bg_color)

        self.emu = Chip8()
        self.rom_bytes = rom_bytes if rom_bytes is not None else DEFAULT_ROM
        self.rom_label = rom_label
        self.emu.load_rom_bytes(self.rom_bytes)
        self.rom_loaded = True

        self.is_running = False
        self.cpu_accum = 0.0
        self.timer_accum = 0.0
        self.last_tick = time.perf_counter()

        self.setup_menu()
        self.create_widgets()
        self._bind_keys()
        self.draw_screen()

    def setup_menu(self) -> None:
        menu_bar = tk.Menu(
            self.root,
            bg=self.button_bg,
            fg=self.text_color,
            activebackground=self.text_color,
            activeforeground=self.button_bg,
        )

        file_menu = tk.Menu(menu_bar, tearoff=0, bg=self.button_bg, fg=self.text_color)
        file_menu.add_command(label="Load ROM...", command=self.load_rom)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menu_bar.add_cascade(label="File", menu=file_menu)

        emu_menu = tk.Menu(menu_bar, tearoff=0, bg=self.button_bg, fg=self.text_color)
        emu_menu.add_command(label="Run / Pause", command=self.toggle_emulation)
        emu_menu.add_command(label="Reset", command=self.reset_emulator)
        menu_bar.add_cascade(label="Emulation", menu=emu_menu)

        self.root.config(menu=menu_bar)

    def create_widgets(self) -> None:
        toolbar = tk.Frame(self.root, bg=self.bg_color)
        toolbar.pack(fill=tk.X, padx=10, pady=5)

        btn_style = {
            "bg": self.button_bg,
            "fg": self.button_fg,
            "activebackground": self.text_color,
            "activeforeground": self.button_bg,
            "font": ("Arial", 9, "bold"),
            "bd": 1,
            "relief": "solid",
        }

        tk.Button(toolbar, text=" Load ROM ", command=self.load_rom, **btn_style).pack(side=tk.LEFT, padx=2)
        self.run_btn = tk.Button(toolbar, text=" Run ", command=self.toggle_emulation, **btn_style)
        self.run_btn.pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text=" Reset ", command=self.reset_emulator, **btn_style).pack(side=tk.LEFT, padx=2)

        self.canvas = tk.Canvas(
            self.root,
            width=560,
            height=280,
            bg=self.screen_bg,
            highlightthickness=1,
            highlightbackground=self.text_color,
        )
        self.canvas.pack(padx=10, pady=5)

        self.status_var = tk.StringVar(value=f"Loaded: {self.rom_label} (paused)")
        tk.Label(
            self.root,
            textvariable=self.status_var,
            bg=self.button_bg,
            fg=self.text_color,
            anchor=tk.W,
            font=("Arial", 9),
            padx=10,
            pady=3,
        ).pack(side=tk.BOTTOM, fill=tk.X)

        key_help = tk.Label(
            self.root,
            text="Keys: 1-4  QWER  ASDF  ZXCV  (CHIP-8 keypad layout)",
            bg=self.bg_color,
            fg=self.text_color,
            font=("Arial", 8),
        )
        key_help.pack(side=tk.BOTTOM, pady=(0, 4))

    def _bind_keys(self) -> None:
        for key in KEY_MAP:
            self.root.bind(f"<KeyPress-{key}>", self._on_key_down)
            self.root.bind(f"<KeyRelease-{key}>", self._on_key_up)
            if key.isalpha():
                self.root.bind(f"<KeyPress-{key.upper()}>", self._on_key_down)
                self.root.bind(f"<KeyRelease-{key.upper()}>", self._on_key_up)
        self.root.focus_set()

    def _on_key_down(self, event: tk.Event) -> None:
        self.emu.key_pressed(event.keysym)

    def _on_key_up(self, event: tk.Event) -> None:
        self.emu.key_released(event.keysym)

    def load_rom(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Open CHIP-8 ROM",
            filetypes=[("CHIP-8 ROMs", "*.ch8 *.rom"), ("All Files", "*.*")],
        )
        if not file_path:
            return

        try:
            with open(file_path, "rb") as f:
                rom_data = f.read(MAX_ROM)
        except OSError as exc:
            messagebox.showerror("Error", f"Failed to load ROM:\n{exc}")
            return

        if len(rom_data) > MAX_ROM:
            messagebox.showerror("Error", f"ROM too large (max {MAX_ROM} bytes).")
            return

        if not self.emu.load_rom_bytes(rom_data):
            messagebox.showerror("Error", "ROM is empty or invalid.")
            return

        self.rom_bytes = rom_data
        self.rom_label = os.path.basename(file_path)
        self.rom_loaded = True
        self.is_running = False
        self.run_btn.config(text=" Run ")
        self.cpu_accum = 0.0
        self.timer_accum = 0.0
        self.status_var.set(f"Loaded: {self.rom_label} (paused)")
        self.draw_screen()

    def toggle_emulation(self) -> None:
        if not self.rom_loaded:
            messagebox.showwarning("Warning", "Please load a CHIP-8 ROM first.")
            return

        self.is_running = not self.is_running
        if self.is_running:
            self.run_btn.config(text=" Pause ")
            self.status_var.set(f"Running: {self.rom_label}")
            self.last_tick = time.perf_counter()
            self.emulation_loop()
        else:
            self.run_btn.config(text=" Run ")
            self.status_var.set(f"Paused: {self.rom_label}")

    def reset_emulator(self) -> None:
        self.is_running = False
        self.run_btn.config(text=" Run ")
        self.emu.load_rom_bytes(self.rom_bytes)
        self.cpu_accum = 0.0
        self.timer_accum = 0.0
        self.status_var.set(f"Reset: {self.rom_label} (paused)")
        self.draw_screen()

    def draw_screen(self) -> None:
        self.canvas.delete("all")
        pixel_w = 560 / SCREEN_WIDTH
        pixel_h = 280 / SCREEN_HEIGHT

        for y in range(SCREEN_HEIGHT):
            for x in range(SCREEN_WIDTH):
                if self.emu.display[x + (y * SCREEN_WIDTH)]:
                    x1 = x * pixel_w
                    y1 = y * pixel_h
                    self.canvas.create_rectangle(
                        x1, y1, x1 + pixel_w, y1 + pixel_h,
                        fill=self.text_color,
                        outline="",
                    )

    def emulation_loop(self) -> None:
        if not self.is_running:
            return

        now = time.perf_counter()
        dt = min(now - self.last_tick, 0.05)
        self.last_tick = now

        cpu_step = 1.0 / CPU_HZ
        self.cpu_accum += dt
        while self.cpu_accum >= cpu_step:
            self.emu.cycle()
            self.cpu_accum -= cpu_step

        timer_step = 1.0 / TIMER_HZ
        self.timer_accum += dt
        while self.timer_accum >= timer_step:
            self.emu.update_timers()
            self.timer_accum -= timer_step

        if self.emu.draw_flag:
            self.draw_screen()
            self.emu.draw_flag = False

        self.root.after(16, self.emulation_loop)


def _load_startup_rom() -> tuple[bytes, str]:
    if len(sys.argv) >= 2:
        path = os.path.abspath(sys.argv[1])
        try:
            with open(path, "rb") as f:
                data = f.read(MAX_ROM)
            if data:
                return data, os.path.basename(path)
        except OSError as exc:
            messagebox.showerror("ROM Error", f"Could not load ROM:\n{exc}\nUsing built-in demo.")
    return DEFAULT_ROM, "Demo (built-in)"


if __name__ == "__main__":
    root = tk.Tk()
    rom, label = _load_startup_rom()
    Chip8Emulator(root, rom, label)
    root.mainloop()
