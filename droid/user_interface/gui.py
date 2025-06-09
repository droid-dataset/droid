# Tkinter Imports #
import math
import random
import threading
import time
import tkinter as tk
import webbrowser

# Functionality Imports #
from collections import defaultdict
from tkinter import *
from tkinter.font import *
from tkinter.ttk import *

import numpy as np
from PIL import Image, ImageOps, ImageTk

# Internal Imports #
from droid.camera_utils.info import get_camera_name
from droid.misc.parameters import robot_ip
from droid.user_interface.gui_parameters import *
from droid.user_interface.misc import *
from droid.user_interface.text import *


class RobotGUI(tk.Tk):
    def __init__(self, robot=None, fullscreen=False, right_controller=True):
        # Initialize #
        super().__init__()
        self.geometry("1500x1200")
        self.attributes("-fullscreen", fullscreen)
        self.bind("<Escape>", lambda e: self.destroy())
        if right_controller:
            self.oculus_controller = "right"
            self.button_a = "A"
            self.button_b = "B"
        else:
            self.oculus_controller = "left"
            self.button_a = "X"
            self.button_b = "Y"

        # Prepare Relevent Items #
        self.num_traj_saved = 0
        self.cam_ids = list(robot.cam_ids)
        self.camera_order = np.arange(robot.num_cameras)
        self.time_index = None
        self.robot = robot
        self.info = {
            "user": "",
            "fixed_tasks": [],
            "new_tasks": [],
            "current_task": "",
        }

        # Create Resizable Container #
        container = tk.Frame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # Organize Frame Dict #
        self.frames = {}
        self.curr_frame = None
        for F in (
            LoginPage,
            RobotResetPage,
            CanRobotResetPage,
            ControllerOffPage,
            PreferredTasksPage,
            SceneConfigurationPage,
            CameraPage,
            EnlargedImagePage,
            RequestedBehaviorPage,
            SceneChangesPage,
            CalibrationPage,
            CalibrateCamera,
            IncompleteCalibration,
            OldCalibration,
            OldScene,
        ):
            self.frames[F] = F(container, self)
            self.frames[F].grid(row=0, column=0, sticky="nsew")

        # Listen For Robot Reset #
        self.enter_presses = 0
        self.bind("<KeyPress-Return>", self.robot_reset, add="+")
        self.refresh_enter_variable()

        # Listen For Robot Controls #
        info_thread = threading.Thread(target=self.listen_for_robot_info)
        info_thread.daemon = True
        info_thread.start()

        # Update Camera Feed #
        self.camera_feed = None
        camera_thread = threading.Thread(target=self.update_camera_feed)
        camera_thread.daemon = True
        camera_thread.start()

        # Start Program! #
        self.last_frame_change = 0
        self.show_frame(LoginPage)
        self.update_time_index()
        self.mainloop()

    def show_frame(self, frame_id, refresh_page=True, wait=False):
        if time.time() - self.last_frame_change < 0.1:
            return
        self.focus()

        self.last_frame_change = time.time()
        self.curr_frame, old_frame = self.frames[frame_id], self.curr_frame

        if hasattr(old_frame, "exit_page"):
            old_frame.exit_page()
        if hasattr(self.curr_frame, "initialize_page") and refresh_page:
            self.curr_frame.initialize_page()

        if wait:
            self.after(100, self.curr_frame.tkraise)
        else:
            self.curr_frame.tkraise()

        if hasattr(self.curr_frame, "launch_page"):
            self.after(100, self.curr_frame.launch_page)

    def swap_img_order(self, i, j):
        self.camera_order[i], self.camera_order[j] = self.camera_order[j], self.camera_order[i]

    def set_img(self, i, widget=None, width=None, height=None, use_camera_order=True):
        index = self.camera_order[i] if use_camera_order else i
        if self.camera_feed is None:
            return
        else:
            img = self.camera_feed[index]
        img = Image.fromarray(img)
        if width is not None:
            img = ImageOps.contain(img, (width, height), Image.Resampling.LANCZOS)
        img = ImageTk.PhotoImage(img)
        widget.configure(image=img)
        widget.image = img

    def update_time_index(self):
        if self.time_index is not None:
            self.time_index = (self.time_index + 1) % len(self.last_traj)
        self.after(50, self.update_time_index)

    def robot_reset(self, event):
        self.enter_presses += 1
        if self.enter_presses == 25:
            self.enter_presses = -50
            self.frames[RobotResetPage].set_home_frame(type(self.curr_frame))
            self.show_frame(RobotResetPage)

    def refresh_enter_variable(self):
        self.enter_presses = 0
        self.after(3000, self.refresh_enter_variable)

    def listen_for_robot_info(self):
        last_was_false = True
        controller_on = True
        while True:
            time.sleep(0.1)
            info = self.robot.get_user_feedback()
            trigger = info["success"] or info["failure"]
            if info["success"] and last_was_false:
                self.event_generate("<<KeyRelease-controllerA>>")
            if info["failure"] and last_was_false:
                self.event_generate("<<KeyRelease-controllerB>>")
            if trigger and last_was_false:
                self.event_generate("<<KeyRelease-controller>>")

            if info["controller_on"] < controller_on:
                self.show_frame(ControllerOffPage)

            last_was_false = not trigger
            controller_on = info["controller_on"]

    def update_camera_feed(self, sleep=0.05):
        while True:
            try:
                self.camera_feed, self.cam_ids = self.robot.get_camera_feed()
            except:
                pass
            time.sleep(sleep)


# Start up page
class LoginPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.curr_scene_id = None
        self.gui_info = load_gui_info()

        # load name, building, and scene ID

        # Title #
        title_lbl = Label(self, text="Login Page", font=Font(size=30, weight="bold"))
        title_lbl.place(relx=0.5, rely=0.05, anchor="n")

        # Warning #
        self.warning_text = StringVar()
        self.warning_text.set("Please use consistent spelling!")
        instr_lbl = Label(self, textvariable=self.warning_text, font=Font(size=20))
        instr_lbl.place(relx=0.5, rely=0.1, anchor="n")

        # Request Name #
        self.user = StringVar()
        if "user" in self.gui_info:
            self.user.set(self.gui_info["user"])
        name_lbl = Label(self, text="Full Name:", font=Font(size=15, underline=True))
        name_lbl.place(relx=0.5, rely=0.22, anchor="n")
        self.name_entry = tk.Entry(self, textvariable=self.user, width=35, font=Font(size=15))
        self.name_entry.place(relx=0.5, rely=0.25, anchor="n")

        # Request Building #
        self.building = StringVar()
        if "building" in self.gui_info:
            self.building.set(self.gui_info["building"])
        building_lbl = Label(self, text="Building:", font=Font(size=15, underline=True))
        building_lbl.place(relx=0.5, rely=0.32, anchor="n")
        self.building_entry = tk.Entry(self, textvariable=self.building, width=35, font=Font(size=15))
        self.building_entry.place(relx=0.5, rely=0.35, anchor="n")

        # New Scene Button #
        scene_change_lbl = Label(self, text="Has The Scene Changed?", font=Font(size=15, underline=True))
        scene_change_lbl.place(relx=0.5, rely=0.42, anchor="n")

        yes_btn = tk.Button(
            self,
            text="Yes",
            highlightbackground="Red",
            font=Font(size=15, weight="bold"),
            width=2,
            height=2,
            borderwidth=10,
            command=self.click_yes,
        )
        yes_btn.place(relx=0.47, rely=0.45, anchor="n")

        no_btn = tk.Button(
            self,
            text="No",
            highlightbackground="Blue",
            font=Font(size=15, weight="bold"),
            width=2,
            height=2,
            borderwidth=10,
            command=self.click_no,
        )
        no_btn.place(relx=0.53, rely=0.45, anchor="n")

        # Begin Button #
        begin_btn = tk.Button(
            self,
            text="BEGIN",
            highlightbackground="green",
            font=Font(size=30, weight="bold"),
            padx=3,
            pady=5,
            borderwidth=10,
            command=self.check_completeness,
        )
        begin_btn.place(relx=0.5, rely=0.8, anchor=CENTER)

    def click_yes(self):
        self.curr_scene_id = generate_scene_id()

    def click_no(self):
        self.curr_scene_id = self.gui_info["scene_id"]

    def check_completeness(self):
        name = self.user.get()
        building = self.building.get()
        name_num_words = len([x for x in name.split(" ") if x != ""])
        name_correct = (name_num_words >= 2) and (missing_name_text not in name)
        building_correct = len(building) >= 3
        if not name_correct:
            self.user.set(missing_name_text)
        elif not building_correct:
            self.building.set(missing_building_text)
        elif self.curr_scene_id is None:
            self.warning_text.set("Please mark the scene as new or old")
        else:
            self.controller.info["user"] = name
            self.controller.info["building"] = building
            self.controller.info["scene_id"] = self.curr_scene_id
            update_gui_info(user=name, building=building, scene_id=self.curr_scene_id)
            self.controller.show_frame(SceneConfigurationPage)


class RobotResetPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        title_lbl = Label(self, text="Resetting Robot...", font=Font(size=30, weight="bold"))
        title_lbl.pack(pady=15)

        description_lbl = Label(self, text="Please stand by :)", font=Font(size=18))
        description_lbl.pack(pady=5)

    def launch_page(self):
        self.controller.robot.reset_robot()
        self.controller.show_frame(self.home_frame)

    def set_home_frame(self, frame):
        self.home_frame = frame


class CanRobotResetPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.controller.bind("<<KeyRelease-controller>>", self.moniter_keys, add="+")

        self.title_str = StringVar()
        self.instr_str = StringVar()

        title_lbl = Label(self, text="Proceed With Robot Reset?", font=Font(size=30, weight="bold"))
        title_lbl.pack(pady=15)

        description_lbl = Label(self, text="Press '" + self.controller.button_a + "' when ready", font=Font(size=18))
        description_lbl.pack(pady=5)

    def set_next_page(self, page):
        self.next_page = page

    def moniter_keys(self, event):
        if self.controller.curr_frame != self:
            return
        self.controller.frames[RobotResetPage].set_home_frame(self.next_page)
        self.controller.show_frame(RobotResetPage)


class ControllerOffPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.controller.bind("<KeyRelease-space>", self.moniter_keys, add="+")

        title_lbl = Label(self, text="WARNING: Controller off", font=Font(size=30, weight="bold"))
        title_lbl.pack(pady=15)

        description_lbl = Label(self, text=controller_off_msg, font=Font(size=18))
        description_lbl.pack(pady=5)

    def moniter_keys(self, event):
        if self.controller.curr_frame != self:
            return
        self.controller.show_frame(LoginPage)


class CalibrationPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Title #
        how_to_title_lbl = Label(self, text="Calibration Hub", font=Font(size=30, weight="bold"))
        how_to_title_lbl.pack(pady=5)

        # Warning #
        instr_lbl = tk.Label(self, text=color_spectrum_explantion, font=Font(size=20, slant="italic"))
        instr_lbl.pack(pady=5)

        # How To Text #
        how_to_text_lbl = Label(self, text=how_to_calibrate_text, font=Font(size=18))
        how_to_text_lbl.pack(pady=20)

        longest_name = max([len(get_camera_name(cam_id)) for cam_id in controller.cam_ids])

        self.button_dict = {}
        for i in range(len(controller.cam_ids)):
            cam_id = controller.cam_ids[i]
            cam_name = get_camera_name(cam_id)

            camera_btn = tk.Button(
                self,
                text=cam_name,
                font=Font(size=30, weight="bold"),
                width=longest_name,
                command=lambda cam_idx=cam_id: self.calibrate_camera(cam_idx),
                borderwidth=10,
            )
            camera_btn.place(relx=0.5, rely=0.5 + i * 0.08, anchor="n")
            self.button_dict[cam_id] = camera_btn

        # Back Button #
        back_btn = tk.Button(
            self,
            text="BACK",
            highlightbackground="white",
            font=Font(size=30, weight="bold"),
            padx=3,
            pady=5,
            borderwidth=10,
            command=lambda: controller.show_frame(SceneConfigurationPage),
        )
        back_btn.place(relx=0.5, rely=0.9, anchor="n")

        # Calibration Mode Buttons #
        self.standard_btn = tk.Button(
            self,
            text="Standard Mode",
            highlightbackground="green",
            font=Font(size=30, weight="bold"),
            padx=3,
            pady=5,
            borderwidth=10,
            command=lambda: self.change_calibration_mode(False),
        )
        self.standard_btn.place(relx=0.15, rely=0.02, anchor="n")

        self.advanced_btn = tk.Button(
            self,
            text="Advanced Mode",
            highlightbackground="red",
            font=Font(size=30, weight="bold"),
            padx=3,
            pady=5,
            borderwidth=10,
            command=lambda: self.change_calibration_mode(True),
        )
        self.advanced_btn.place(relx=0.85, rely=0.02, anchor="n")

    def change_calibration_mode(self, advanced_on):
        if advanced_on:
            self.controller.robot.enable_advanced_calibration()
            self.standard_btn.configure(highlightbackground="red")
            self.advanced_btn.configure(highlightbackground="green")
        else:
            self.controller.robot.disable_advanced_calibration()
            self.standard_btn.configure(highlightbackground="green")
            self.advanced_btn.configure(highlightbackground="red")

    def calibrate_camera(self, cam_id):
        self.controller.robot.set_calibration_mode(cam_id)
        long_wait = self.controller.robot.advanced_calibration
        time.sleep(5.0 if long_wait else 0.1)

        self.controller.frames[CalibrateCamera].set_camera_id(cam_id)
        self.controller.show_frame(CalibrateCamera, wait=True)

    def initialize_page(self):
        info_dict = self.controller.robot.check_calibration_info()
        for cam_id in self.button_dict.keys():
            is_missing = any([cam_id in missing_id for missing_id in info_dict["missing"]])
            is_old = any([cam_id in old_id for old_id in info_dict["old"]])
            if is_missing:
                color = "red"
            elif is_old:
                color = "blue"
            else:
                color = "black"

            self.button_dict[cam_id].config(highlightbackground=color)

    def exit_page(self):
        if self.controller.curr_frame != self.controller.frames[CalibrateCamera]:
            self.controller.robot.set_trajectory_mode()


class IncompleteCalibration(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Title #
        how_to_title_lbl = Label(self, text="Calibration Incomplete", font=Font(size=30, weight="bold"))
        how_to_title_lbl.pack(pady=5)

        # Warning #
        instr_lbl = tk.Label(self, text=missing_calibration_text, font=Font(size=20, slant="italic"))
        instr_lbl.pack(pady=5)

        # Back Button #
        back_btn = tk.Button(
            self,
            text="CALIBRATE",
            highlightbackground="red",
            font=Font(size=30, weight="bold"),
            padx=3,
            pady=5,
            borderwidth=10,
            command=lambda: controller.show_frame(CalibrationPage),
        )
        back_btn.place(relx=0.5, rely=0.5, anchor="n")


class OldCalibration(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Title #
        how_to_title_lbl = Label(self, text="Calibration Warning", font=Font(size=30, weight="bold"))
        how_to_title_lbl.pack(pady=5)

        # Warning #
        instr_lbl = tk.Label(self, text=old_calibration_text, font=Font(size=20, slant="italic"))
        instr_lbl.pack(pady=5)

        # Back Button #
        back_btn = tk.Button(
            self,
            text="CALIBRATE",
            highlightbackground="blue",
            font=Font(size=30, weight="bold"),
            padx=3,
            pady=5,
            borderwidth=10,
            command=lambda: controller.show_frame(CalibrationPage),
        )
        back_btn.place(relx=0.4, rely=0.5, anchor="n")

        # Proceed Button #
        proceed_btn = tk.Button(
            self,
            text="PROCEED",
            highlightbackground="green",
            font=Font(size=30, weight="bold"),
            padx=3,
            pady=5,
            borderwidth=10,
            command=lambda: controller.show_frame(RequestedBehaviorPage),
        )
        proceed_btn.place(relx=0.6, rely=0.5, anchor="n")


class OldScene(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Title #
        how_to_title_lbl = Label(self, text="Scene Warning", font=Font(size=30, weight="bold"))
        how_to_title_lbl.pack(pady=5)

        # Warning #
        instr_lbl = tk.Label(self, text=old_scene_text, font=Font(size=20, slant="italic"))
        instr_lbl.pack(pady=5)

        # Back Button #
        back_btn = tk.Button(
            self,
            text="BACK",
            highlightbackground="blue",
            font=Font(size=30, weight="bold"),
            padx=3,
            pady=5,
            borderwidth=10,
            command=lambda: controller.show_frame(SceneConfigurationPage),
        )
        back_btn.place(relx=0.4, rely=0.5, anchor="n")

        # Proceed Button #
        proceed_btn = tk.Button(
            self,
            text="PROCEED",
            highlightbackground="green",
            font=Font(size=30, weight="bold"),
            padx=3,
            pady=5,
            borderwidth=10,
            command=lambda: controller.show_frame(RequestedBehaviorPage),
        )
        proceed_btn.place(relx=0.6, rely=0.5, anchor="n")


class PreferredTasksPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.controller.bind("<KeyRelease>", self.moniter_keys, add="+")

        # Title #
        title_lbl = Label(self, text="Preferred Tasks", font=Font(size=30, weight="bold"))
        title_lbl.place(relx=0.5, rely=0.05, anchor="n")

        # Shift Instructions #
        instr_lbl = tk.Label(self, text=preferred_task_text, font=Font(size=20, slant="italic"))
        instr_lbl.place(relx=0.5, rely=0.1, anchor="n")

        # Fixed Task Selection #
        pos_dict = {
            "Articulated Tasks": (0.05, 0.2),
            "Free Object Tasks": (0.05, 0.4),
            "Tool Usage Tasks": (0.55, 0.2),
            "Deformable Object Tasks": (0.55, 0.4),
        }

        for key in preferred_tasks.keys():
            x_pos, y_pos = pos_dict[key]
            group_lbl = tk.Label(self, text=key + ":", font=Font(size=20, underline=True))
            group_lbl.place(relx=x_pos, rely=y_pos)
            for i, task in enumerate(preferred_tasks[key]):
                task_ckbox = tk.Checkbutton(self, text=task, font=Font(size=15), variable=BooleanVar())
                task_ckbox.place(relx=x_pos + 0.01, rely=y_pos + (i + 1) * 0.04)

        # Free Response Tasks #
        notes_lbl = tk.Label(self, text="Personal Notes:", font=Font(size=20, underline=True))
        notes_lbl.place(relx=0.05, rely=0.6)

        self.notes_txt = tk.Text(self, height=15, width=65, font=Font(size=15))
        self.notes_txt.place(relx=0.05, rely=0.64)

        # Back Button #
        back_btn = tk.Button(
            self,
            text="BACK",
            highlightbackground="red",
            font=Font(size=30, weight="bold"),
            padx=3,
            pady=5,
            borderwidth=10,
            command=lambda: controller.show_frame(SceneConfigurationPage),
        )
        back_btn.place(relx=0.7, rely=0.75)

    def moniter_keys(self, event):
        if self.controller.curr_frame != self:
            return

        # Toggle Camera View
        if event.keysym in ["Shift_L", "Shift_R"]:
            self.controller.frames[CameraPage].set_home_frame(PreferredTasksPage)
            self.controller.show_frame(CameraPage, wait=True)

    def initialize_page(self):
        self.notes_txt.focus()


class SceneConfigurationPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Update Based Off Activity #
        self.controller.bind("<KeyRelease>", self.moniter_keys, add="+")
        self.controller.bind("<ButtonRelease-1>", self.moniter_keys, add="+")

        # Title #
        title_lbl = Label(self, text="Scene Configuration", font=Font(size=30, weight="bold"))
        title_lbl.place(relx=0.5, rely=0.05, anchor="n")

        # Button Box #
        bx, by = 0.12, 0.045
        box_lbl = tk.Button(
            self, text=" " * 25, highlightbackground="blue", font=Font(slant="italic", weight="bold"), padx=12, pady=40
        )
        box_lbl.place(relx=bx, rely=by, anchor="n")

        # Task Ideas Button #
        ideas_btn = tk.Button(self, text="Task Ideas", font=Font(weight="bold"), height=1, width=16)
        ideas_btn.bind("<Button-1>", lambda e: webbrowser.open_new(task_ideas_link))
        ideas_btn.place(relx=bx, rely=by + 0.005, anchor="n")

        # Preferred Tasks Button #
        preferred_tasks_btn = tk.Button(
            self,
            text="Preferred Tasks",
            font=Font(weight="bold"),
            height=1,
            width=16,
            command=lambda: controller.show_frame(PreferredTasksPage),
        )
        preferred_tasks_btn.place(relx=bx, rely=by + 0.035, anchor="n")

        # Franka Website Button #
        franka_btn = tk.Button(self, text="Franka Website", font=Font(weight="bold"), height=1, width=16)
        franka_btn.bind("<Button-1>", lambda e: webbrowser.open_new("https://{0}/desk/".format(robot_ip)))
        franka_btn.place(relx=bx, rely=by + 0.065, anchor="n")

        # Shift Instructions #
        instr_lbl = tk.Label(self, text=shift_text, font=Font(size=20, slant="italic"))
        instr_lbl.place(relx=0.5, rely=0.1, anchor="n")

        # Fixed Task Selection #
        self.task_dict = defaultdict(BooleanVar)
        pos_dict = {
            "Articulated Tasks": (0.005, 0.2),
            "Free Object Tasks": (0.005, 0.4),
            "Tool Usage Tasks": (0.51, 0.2),
            "Deformable Object Tasks": (0.51, 0.4),
        }

        for key in all_tasks.keys():
            x_pos, y_pos = pos_dict[key]
            group_lbl = tk.Label(self, text=key + ":", font=Font(size=20, underline=True))
            group_lbl.place(relx=x_pos, rely=y_pos)
            for i, task in enumerate(all_tasks[key]):
                task_ckbox = tk.Checkbutton(self, text=task, font=Font(size=15), variable=self.task_dict[task])
                task_ckbox.place(relx=x_pos + 0.01, rely=y_pos + (i + 1) * 0.04)

        # Free Response Tasks #
        group_lbl = tk.Label(self, text=freewrite_text, font=Font(size=20, underline=True))
        group_lbl.place(relx=0.01, rely=0.6)

        self.task_txt = tk.Text(self, height=15, width=65, font=Font(size=15))
        self.task_txt.place(relx=0.02, rely=0.64)

        # Ready Button #
        collect_btn = tk.Button(
            self,
            text="COLLECT",
            highlightbackground="green",
            font=Font(size=30, weight="bold"),
            height=1,
            width=8,
            borderwidth=10,
            command=self.finish_setup,
        )
        collect_btn.place(relx=0.75, rely=0.68)

        # Practice Button #
        practice_btn = tk.Button(
            self,
            text="PRACTICE",
            highlightbackground="red",
            font=Font(size=30, weight="bold"),
            height=1,
            width=8,
            borderwidth=10,
            command=self.practice_robot,
        )
        practice_btn.place(relx=0.75, rely=0.82)

        # New Scene Button #
        new_scene_btn = tk.Button(
            self,
            text="NEW SCENE",
            highlightbackground="black",
            font=Font(size=30, weight="bold"),
            height=1,
            width=8,
            borderwidth=10,
            command=self.mark_new_scene,
        )
        new_scene_btn.place(relx=0.55, rely=0.68)

        # Calibrate Button #
        calibrate_btn = tk.Button(
            self,
            text="CALIBRATE",
            highlightbackground="blue",
            font=Font(size=30, weight="bold"),
            height=1,
            width=8,
            borderwidth=10,
            command=lambda: self.controller.show_frame(CalibrationPage),
        )
        calibrate_btn.place(relx=0.55, rely=0.82)

    def moniter_keys(self, event):
        if self.controller.curr_frame != self:
            return

        # Toggle Camera View
        if event.keysym in ["Shift_L", "Shift_R"]:
            self.controller.frames[CameraPage].set_home_frame(SceneConfigurationPage)
            self.controller.show_frame(CameraPage, wait=True)

        # Update Fixed Tasks #
        self.controller.info["fixed_tasks"] = []
        for task, val in self.task_dict.items():
            if val.get():
                self.controller.info["fixed_tasks"].append(task)

        # Update New Tasks #
        self.controller.info["new_tasks"] = self.get_new_tasks()

    def finish_setup(self):
        # Check tasks are filled out #
        fixed_tasks = self.controller.info["fixed_tasks"]
        new_tasks = self.controller.info["new_tasks"]
        if len(fixed_tasks) + len(new_tasks) == 0:
            self.task_txt.delete("1.0", END)
            self.task_txt.insert(1.0, no_tasks_text)
            return

        # Check that cameras are calibrated #
        calib_info_dict = self.controller.robot.check_calibration_info(remove_hand_camera=True)
        if len(calib_info_dict["missing"]) > 0:
            self.controller.show_frame(IncompleteCalibration)
            return
        if len(calib_info_dict["old"]) > 0:
            self.controller.show_frame(OldCalibration)
            return

        # Check that scene isn't stale #
        last_scene_change = load_gui_info()["scene_id_timestamp"]
        stale_scene = (time.time() - last_scene_change) > 3600
        if stale_scene:
            self.controller.show_frame(OldScene)
            return

        # If everything is okay, proceed
        self.controller.show_frame(RequestedBehaviorPage)

    def mark_new_scene(self):
        new_scene_id = generate_scene_id()
        self.controller.info["scene_id"] = new_scene_id
        update_gui_info(scene_id=new_scene_id)

    def get_new_tasks(self):
        new_tasks = self.task_txt.get("1.0", END).replace("\n", "")
        new_tasks = new_tasks.replace(no_tasks_text, "").split(";")
        new_tasks = [t for t in new_tasks if (not t.isspace() and len(t))]
        return new_tasks

    def practice_robot(self):
        self.controller.frames[CameraPage].set_mode("practice_traj")
        self.controller.show_frame(CameraPage, wait=True)

    def initialize_page(self):
        self.controller.frames[CameraPage].set_mode("live")
        self.task_txt.focus()


class RequestedBehaviorPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.keep_task = False

        # Title #
        title_lbl = Label(self, text="Requested Behavior", font=Font(size=30, weight="bold"))
        title_lbl.place(relx=0.5, rely=0.05, anchor="n")

        # Task #
        self.task_text = StringVar()
        task_lbl = Label(self, textvariable=self.task_text, font=Font(size=30))
        task_lbl.place(relx=0.5, rely=0.4, anchor="center")

        # Instructions #
        instr_lbl = tk.Label(self, text="Press '" + self.controller.button_a + "' to begin, or '" +
                                        self.controller.button_b + "' to resample", font=Font(size=20, slant="italic"))
        instr_lbl.place(relx=0.5, rely=0.1, anchor="n")

        # Change Status Box #
        bx, by = 0.15, 0.045
        box_lbl = tk.Button(self, text=" " * 48, highlightbackground="black", pady=26)
        box_lbl.place(relx=bx, rely=by, anchor="n")

        success_btn = tk.Button(
            self,
            text="Relabel Last Trajectory As Success",
            font=Font(weight="bold"),
            highlightbackground="green",
            height=1,
            width=32,
        )
        success_btn.bind("<Button-1>", lambda e: self.change_trajectory_status(True))
        success_btn.place(relx=bx, rely=by + 0.005, anchor="n")

        failure_btn = tk.Button(
            self,
            text="Relabel Last Trajectory As Failure",
            font=Font(weight="bold"),
            highlightbackground="red",
            height=1,
            width=32,
        )
        failure_btn.bind("<Button-1>", lambda e: self.change_trajectory_status(False))
        failure_btn.place(relx=bx, rely=by + 0.035, anchor="n")

        # Resample Button #
        resample_btn = tk.Button(
            self,
            text="RESAMPLE",
            highlightbackground="blue",
            font=Font(size=30, weight="bold"),
            padx=3,
            pady=5,
            borderwidth=10,
            command=lambda: self.resample(None),
        )
        resample_btn.place(relx=0.5, rely=0.7)

        # Back Button #
        back_btn = tk.Button(
            self,
            text="BACK",
            highlightbackground="red",
            font=Font(size=30, weight="bold"),
            padx=3,
            pady=5,
            borderwidth=10,
            command=lambda: controller.show_frame(SceneConfigurationPage),
        )
        back_btn.place(relx=0.4, rely=0.7)

        # Update Based Off Activity #
        controller.bind("<<KeyRelease-controllerA>>", self.start_trajectory, add="+")
        controller.bind("<<KeyRelease-controllerB>>", self.resample, add="+")

    def change_trajectory_status(self, success):
        if self.controller.curr_frame != self:
            return
        self.controller.num_traj_saved += success - (1 - success)
        self.controller.robot.change_trajectory_status(success=success)

    def resample(self, e):
        if self.controller.curr_frame != self:
            return
        self.sample_new_task()

    def initialize_page(self):
        self.controller.frames[CameraPage].set_mode("traj")
        if not self.keep_task:
            self.sample_new_task()
        else:
            self.keep_task = False

    def sample_new_task(self):
        if np.random.uniform() < compositional_task_prob:
            task = self.sample_compositional_task()
        else:
            task = self.sample_single_task()

        self.controller.info["current_task"] = task
        self.task_text.set(task)
        self.controller.update_idletasks()

    def sample_compositional_task(self):
        comp_type = np.random.randint(4)
        tasks = [self.sample_single_task() for i in range(comp_type)]
        return compositional_tasks[comp_type](*tasks)

    def sample_single_task(self):
        fixed_tasks = self.controller.info["fixed_tasks"]
        ft_weight = np.array([self.get_task_weight(t) for t in fixed_tasks])
        ft_weight = (ft_weight / ft_weight.sum()) * (1 - new_task_prob)

        new_tasks = self.controller.info["new_tasks"]
        nt_weight = (np.ones(len(new_tasks)) / len(new_tasks)) * new_task_prob

        tasks = fixed_tasks + new_tasks
        weights = np.concatenate([ft_weight, nt_weight])

        return random.choices(tasks, weights=weights)[0]

    def get_task_weight(self, task):
        task_type = [t for t in task_weights.keys() if t in task]
        assert len(task_type) == 1
        return task_weights[task_type[0]]

    def start_trajectory(self, event):
        if self.controller.curr_frame != self:
            return
        self.controller.show_frame(CameraPage, wait=True)

    def keep_last_task(self):
        self.keep_task = True


class SceneChangesPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Title #
        title_lbl = Label(self, text="Requested Scene Changes", font=Font(size=30, weight="bold"))
        title_lbl.place(relx=0.5, rely=0.05, anchor="n")

        # Shift Instructions #
        instr_lbl = tk.Label(self, text=shift_text, font=Font(size=20, slant="italic"))
        instr_lbl.place(relx=0.5, rely=0.1, anchor="n")
        self.controller.bind("<KeyRelease>", self.show_camera_feed, add="+")

        # Changes #
        self.change_text = StringVar()
        change_lbl = Label(self, textvariable=self.change_text, font=Font(size=30))
        change_lbl.place(relx=0.5, rely=0.4, anchor="center")

        # Resample Button #
        resample_btn = tk.Button(
            self,
            text="RESAMPLE",
            highlightbackground="red",
            font=Font(size=30, weight="bold"),
            padx=3,
            pady=5,
            borderwidth=10,
            command=self.sample_change,
        )
        resample_btn.place(relx=0.34, rely=0.7)

        # Ready Button #
        ready_btn = tk.Button(
            self,
            text="DONE",
            highlightbackground="green",
            font=Font(size=30, weight="bold"),
            padx=3,
            pady=5,
            borderwidth=10,
            command=lambda: self.controller.show_frame(SceneConfigurationPage),
        )
        ready_btn.place(relx=0.54, rely=0.7)

    def show_camera_feed(self, event):
        if self.controller.curr_frame != self:
            return
        if event.keysym in ["Shift_L", "Shift_R"]:
            self.controller.frames[CameraPage].set_home_frame(SceneChangesPage)
            self.controller.show_frame(CameraPage, wait=True)

    def sample_change(self):
        num_traj = self.controller.num_traj_saved
        move_robot = (num_traj % move_robot_frequency == 0) and (num_traj > 0)

        if move_robot:
            curr_text = move_robot_text
        else:
            curr_text = random.choice(scene_changes)
        self.change_text.set(curr_text)
        self.controller.update_idletasks()

    def initialize_page(self):
        self.controller.frames[CameraPage].set_mode("live")
        self.sample_change()


class CameraPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        self.n_rows = 1 if len(self.controller.camera_order) <= 2 else 2
        self.n_cols = math.ceil(len(self.controller.camera_order) / self.n_rows)

        # Moniter Key Events #
        self.controller.bind("<KeyRelease>", self.moniter_keys, add="+")
        self.controller.bind("<<KeyRelease-controller>>", self.moniter_keys, add="+")

        # Page Variables #
        self.title_str = StringVar()
        self.instr_str = StringVar()
        self.mode = "live"

        # Title #
        title_lbl = Label(self, textvariable=self.title_str, font=Font(size=30, weight="bold"))
        title_lbl.place(relx=0.5, rely=0.02, anchor="n")

        # Instructions #
        instr_lbl = tk.Label(self, textvariable=self.instr_str, font=Font(size=24, slant="italic"))
        instr_lbl.place(relx=0.5, rely=0.06, anchor="n")

        # Save / Delete Buttons #
        self.save_btn = tk.Button(
            self,
            text="SAVE",
            highlightbackground="green",
            font=Font(size=30, weight="bold"),
            padx=3,
            pady=5,
            borderwidth=10,
            command=lambda save=True: self.edit_trajectory(save),
        )
        self.delete_btn = tk.Button(
            self,
            text="DELETE",
            highlightbackground="red",
            font=Font(size=30, weight="bold"),
            padx=3,
            pady=5,
            borderwidth=10,
            command=lambda save=False: self.edit_trajectory(save),
        )

        # Timer #
        self.timer_on = False
        self.time_str = StringVar()
        self.timer = tk.Button(
            self,
            textvariable=self.time_str,
            highlightbackground="black",
            font=Font(size=40, weight="bold"),
            padx=3,
            pady=5,
            borderwidth=10,
        )

        # Image Variables #
        self.clicked_id = None
        self.image_boxes = []

        # Create Image Grid #
        for i in range(self.n_rows):
            self.rowconfigure(i, weight=1)
            for j in range(self.n_cols):
                if (i * self.n_cols + j) >= len(self.controller.camera_order):
                    continue
                self.columnconfigure(j, weight=1)

                # Add Image Box #
                button = tk.Button(
                    self, height=0, width=0, command=lambda idx=(i * self.n_cols + j): self.update_image_grid(idx)
                )
                button.grid(row=i, column=j, sticky="s" if self.n_rows > 1 else "")
                self.image_boxes.append(button)

                # Start Image Thread #
                camera_thread = threading.Thread(target=lambda idx=(i * self.n_cols + j): self.update_camera_feed(idx))
                camera_thread.daemon = True
                camera_thread.start()

    def update_image_grid(self, i):
        if self.clicked_id is None:
            # Get Image Of Interest
            self.clicked_id = i
        elif self.clicked_id == i:
            # If Double Clicked, Enlarge It
            self.controller.frames[EnlargedImagePage].set_image_index(i)
            self.controller.show_frame(EnlargedImagePage, wait=True)
            self.clicked_id = None
        else:
            # If Alternate Image Clicked, Swap Them
            self.controller.swap_img_order(self.clicked_id, i)
            self.clicked_id = None

    def update_camera_feed(self, i, w_coeff=1.0, h_coeff=1.0):
        while True:
            not_active = self.controller.curr_frame != self
            not_ready = len(self.controller.camera_order) != len(self.controller.cam_ids)
            if not_active or not_ready:
                time.sleep(0.05)
                continue

            w, h = max(self.winfo_width(), 100), max(self.winfo_height(), 100)
            img_w = int(w / self.n_cols * w_coeff)
            img_h = int(h / self.n_rows * h_coeff)

            self.controller.set_img(i, widget=self.image_boxes[i], width=img_w, height=img_h)

    def moniter_keys(self, event):
        zoom = self.controller.frames[EnlargedImagePage]
        page_inactive = self.controller.curr_frame not in [self, zoom]
        if page_inactive:
            return

        shift = event.keysym in ["Shift_L", "Shift_R"]

        if self.mode == "live" and shift:
            self.controller.show_frame(self.home_frame, refresh_page=False)

    def initialize_page(self):
        # Clear Widges #
        self.save_btn.place_forget()
        self.delete_btn.place_forget()
        self.timer.place_forget()

        # Update Text #
        title = camera_page_title[self.mode]

        instr = camera_page_instr[self.mode]
        if self.controller.oculus_controller == "left":
            if self.mode == 'traj' or self.mode == 'practice_traj':
                instr = instr.replace("A", "X")
                instr = instr.replace("B", "Y")

        self.title_str.set(title)
        self.instr_str.set(instr)

        # Add Mode Specific Stuff #
        if "traj" in self.mode:
            self.controller.robot.reset_robot(randomize=True)

            self.timer.place(relx=0.79, rely=0.01)
            self.update_timer(time.time())

            traj_thread = threading.Thread(target=self.collect_trajectory)
            traj_thread.daemon = True
            traj_thread.start()

    def collect_trajectory(self):
        info = self.controller.info.copy()
        practice = self.mode == "practice_traj"
        self.controller.robot.collect_trajectory(info=info, practice=practice, reset_robot=False)
        self.end_trajectory()

    def update_timer(self, start_time):
        time_passed = time.time() - start_time
        zoom = self.controller.frames[EnlargedImagePage]
        page_inactive = self.controller.curr_frame not in [self, zoom]
        hide_timer = "traj" not in self.mode
        if page_inactive or hide_timer:
            return

        minutes_str = str(int(time_passed / 60))
        curr_seconds = int(time_passed) % 60

        if curr_seconds < 10:
            seconds_str = "0{0}".format(curr_seconds)
        else:
            seconds_str = str(curr_seconds)

        if not self.controller.robot.traj_running:
            start_time = time.time()

        self.time_str.set("{0}:{1}".format(minutes_str, seconds_str))
        self.controller.after(100, lambda: self.update_timer(start_time))

    def end_trajectory(self):
        save = self.controller.robot.traj_saved
        practice = self.mode == "practice_traj"

        # Update Based Off Success / Failure #
        if practice:
            pass
        elif save:
            self.controller.num_traj_saved += 1
        else:
            self.controller.frames[RequestedBehaviorPage].keep_last_task()

        # Check For Scene Changes #
        num_traj = self.controller.num_traj_saved
        move_robot = (num_traj % move_robot_frequency == 0) and (num_traj > 0)
        scene_change = (np.random.uniform() < scene_change_prob) or move_robot

        # Move To Next Page
        time.sleep(0.1)  # Prevents bug where robot doesnt wait to reset
        if practice:
            post_reset_page = SceneConfigurationPage
        elif scene_change:
            post_reset_page = SceneChangesPage
        else:
            post_reset_page = RequestedBehaviorPage
        self.controller.frames[CanRobotResetPage].set_next_page(post_reset_page)
        self.controller.show_frame(CanRobotResetPage)

    def set_home_frame(self, frame):
        self.home_frame = frame

    def set_mode(self, mode):
        self.mode = mode

    def edit_trajectory(self, save):
        if save:
            self.controller.robot.save_trajectory()
        else:
            self.controller.robot.delete_trajectory()
        self.controller.show_frame(RequestedBehaviorPage)


class EnlargedImagePage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Return When Double Clicked #
        controller.bind("<Button-1>", self.return_to_camera_grid, add="+")

        # Image Variables #
        self.image_box = Label(self)
        self.image_box.pack(fill=BOTH, expand=YES, anchor=CENTER)
        self.img_index = 0

        # Camera Feed Thread #
        camera_thread = threading.Thread(target=self.update_camera_feed)
        camera_thread.daemon = True
        camera_thread.start()

    def set_image_index(self, img_index):
        self.img_index = img_index

    def return_to_camera_grid(self, e):
        if self.controller.curr_frame != self:
            return
        self.controller.show_frame(CameraPage, refresh_page=False, wait=True)

    def update_camera_feed(self):
        while True:
            not_active = self.controller.curr_frame != self
            not_ready = len(self.controller.camera_order) != len(self.controller.cam_ids)
            if not_active or not_ready:
                time.sleep(0.05)
                continue
            w, h = max(self.winfo_width(), 250), max(self.winfo_height(), 250)
            self.controller.set_img(self.img_index, widget=self.image_box, width=w, height=h)


class CalibrateCamera(tk.Frame):
    def __init__(self, parent, controller, num_views=2):
        super().__init__(parent)
        self.controller = controller
        self.relevant_indices = []
        self.num_views = num_views
        self.live = False

        # Moniter Key Events #
        self.controller.bind("<<KeyRelease-controllerA>>", self.press_A, add="+")
        self.controller.bind("<<KeyRelease-controllerB>>", self.press_B, add="+")

        # Page Variables #
        self.title_str = StringVar()
        self.instr_str = StringVar()
        self.mode = "live"

        # Title #
        title_lbl = Label(self, textvariable=self.title_str, font=Font(size=30, weight="bold"))
        title_lbl.place(relx=0.5, rely=0.02, anchor="n")

        # Instructions #
        instr_lbl = tk.Label(self, textvariable=self.instr_str, font=Font(size=24, slant="italic"))
        instr_lbl.place(relx=0.5, rely=0.06, anchor="n")

        # Create Image Grid #
        self.image_boxes = []
        self.rowconfigure(0, weight=1)

        for i in range(self.num_views):
            self.columnconfigure(i, weight=1)
            button = tk.Button(self, height=0, width=0)
            button.grid(row=0, column=i, sticky="")
            self.image_boxes.append(button)

            camera_thread = threading.Thread(target=lambda idx=i: self.update_camera_feed(idx))
            camera_thread.daemon = True
            camera_thread.start()

        # Back Button #
        self.back_btn = tk.Button(
            self,
            text="BACK",
            highlightbackground="white",
            font=Font(size=30, weight="bold"),
            padx=3,
            pady=5,
            borderwidth=10,
            command=lambda: controller.show_frame(CalibrationPage),
        )

    def press_A(self, event):
        if self.controller.curr_frame != self:
            return
        if self.live:
            return

        self.back_btn.place_forget()
        traj_thread = threading.Thread(target=self.collect_trajectory)
        traj_thread.daemon = True
        traj_thread.start()

    def press_B(self, event):
        if self.controller.curr_frame != self:
            return
        if self.live:
            return

        self.controller.show_frame(CalibrationPage)

    def collect_trajectory(self):
        self.controller.robot.reset_robot()
        self.live = True

        cam_name = get_camera_name(self.cam_id)
        self.title_str.set("Calibrating Camera: " + cam_name)
        self.instr_str.set("Press '" + self.controller.button_a + "' to begin camera calibration, and '" +
                           self.controller.button_b + "' to terminate early")
        success = self.controller.robot.calibrate_camera(self.cam_id, reset_robot=False)

        self.end_trajectory(success)

    def end_trajectory(self, success):
        self.live = False

        if success:
            time.sleep(0.1)  # Prevents bug where robot doesnt wait to reset
            self.controller.frames[CanRobotResetPage].set_next_page(CalibrationPage)
            self.controller.show_frame(CanRobotResetPage)
        else:
            time.sleep(0.1)  # Prevents bug where robot doesnt wait to reset
            self.controller.frames[CanRobotResetPage].set_next_page(CalibrateCamera)
            self.controller.show_frame(CanRobotResetPage)
            self.title_str.set("CALIBRATION FAILED")
            self.instr_str.set("Press '" + self.controller.button_a + "' to retry, or '" + self.controller.button_b +
                               "' to go back to the calibration hub")
            self.back_btn.place(relx=0.5, rely=0.85, anchor="n")

    def set_camera_id(self, cam_id):
        cam_name = get_camera_name(cam_id)
        self.title_str.set("Camera View: " + cam_name)
        self.instr_str.set("Press '" + self.controller.button_a + "' to begin, or '" + self.controller.button_b +
                           "' to go back to the calibration hub")
        self.back_btn.place(relx=0.5, rely=0.85, anchor="n")
        self.relevant_indices = []
        self.cam_id = cam_id

        curr_cam_ids = self.controller.cam_ids.copy()
        for i in range(len(curr_cam_ids)):
            full_id = curr_cam_ids[i]
            if cam_id in full_id:
                self.relevant_indices.append(i)

    def update_camera_feed(self, i, w_coeff=1.0, h_coeff=1.0):
        while True:
            not_active = self.controller.curr_frame != self
            not_ready = len(self.relevant_indices) != self.num_views
            if not_active or not_ready:
                time.sleep(0.05)
                continue

            w, h = max(self.winfo_width(), 100), max(self.winfo_height(), 100)
            img_w = int(w / self.num_views * w_coeff)
            img_h = int(h / self.num_views * h_coeff)
            index = self.relevant_indices[i]

            self.controller.set_img(index, widget=self.image_boxes[i], width=img_w, height=img_h, use_camera_order=False)

    # def set_camera_id(self, cam_id):
    #     cam_name = get_camera_name(cam_id)
    #     self.title_str.set('Camera View: ' + cam_name)
    #     self.instr_str.set("Press 'A' to begin, or 'B' to go back to the calibration hub")
    #     self.back_btn.place(relx=0.5, rely=0.85, anchor='n')
    #     self.relevant_indices = []
    #     self.cam_id = cam_id

    #     while True:
    #         new_relevant_indices = []
    #         curr_cam_ids = self.controller.cam_ids.copy()

    #         for i in range(len(curr_cam_ids)):
    #             full_id = curr_cam_ids[i]
    #             if cam_id in full_id: new_relevant_indices.append(i)

    #         enough = len(new_relevant_indices) == self.num_views
    #         done = len(curr_cam_ids) == self.num_views
    #         if enough and done: break
    #         time.sleep(0.05)

    #     self.relevant_indices = new_relevant_indices
