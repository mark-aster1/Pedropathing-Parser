import json
import re
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

# ---------------- Conversion Logic ---------------- #

def f(v):
    """Formats floats like 85.7000 -> 85.7"""
    if isinstance(v, (int, float)):
        return f"{v:.3f}".rstrip("0").rstrip(".")
    return str(v)

def camel_case(s):
    """Converts names like 'Prep_Artifacts_1' -> 'prepArtifacts1'"""
    parts = re.split(r'[_\s]+', s)
    return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])

def convert(json_data, class_name="Auto"):
    start = json_data["startPoint"]
    lines = json_data["lines"]

    start_pose_name = "startPose"
    start_pose_line = f'private final Pose {start_pose_name} = new Pose({f(start["x"])}, {f(start["y"])}, Math.toRadians({f(start.get("startDeg", 0))})); // Start position'

    # Generate poses
    poses = []
    for line in lines:
        name = camel_case(line["name"])
        ep = line["endPoint"]
        deg = ep.get("degrees", ep.get("endDeg", 0))
        poses.append(f'private final Pose {name}Pose = new Pose({f(ep["x"])}, {f(ep["y"])}, Math.toRadians({f(deg)})); // {line["name"]}')

    # Declare all PathChains in one line
    path_names = [f'{camel_case(line["name"])}Path' for line in lines]
    path_vars = f'private PathChain {", ".join(path_names)};'


    # Build paths with multi-line formatting
    build_lines = []
    prev_pose = start_pose_name
    for line in lines:
        name = camel_case(line["name"])
        end_pose = f"{name}Pose"
        ep = line["endPoint"]
        heading = ep.get("heading", "linear")
        control_points = line["controlPoints"]

        build = f'{name}Path = follower.pathBuilder()\n'

        if len(control_points) == 0:
            # Simple line
            build += f'        .addPath(new BezierLine({prev_pose}, {end_pose}))\n'
        else:
            # Curve with control point
            cp = control_points[0]
            build += f'        .addPath(new BezierCurve(\n'
            build += f'                {prev_pose},\n'
            build += f'                new Pose({f(cp["x"])}, {f(cp["y"])}), // Control point\n'
            build += f'                {end_pose}\n'
            build += f'        ))\n'

        # Set heading interpolation
        if heading == "constant":
            build += f'        .setConstantHeadingInterpolation({end_pose}.getHeading())\n'
        else:
            build += f'        .setLinearHeadingInterpolation({prev_pose}.getHeading(), {end_pose}.getHeading())\n'

        build += '        .build();'
        build_lines.append(build)
        prev_pose = end_pose

            # ---------------- State Machine Generator ---------------- #

    update_lines = []
    for i, line in enumerate(lines):
        name = camel_case(line["name"]) + "Path"

        if i == 0:
            # First state — no isBusy check
            update_lines.append(
                f"case {i}:\n"
                f"              follower.followPath({name});\n"
                f"              setPathState({i+1});\n"
                f"              break;"
            )
        else:
            # States 1..N with isBusy()
            update_lines.append(
                f"case {i}:\n"
                f"              if (!follower.isBusy()) {{\n"
                f"                 follower.followPath({name});\n"
                f"                 setPathState({i+1});\n"
                f"              }}\n"
                f"              break;"
            )

    # Add final do-nothing state
    final_state = len(lines)
    update_lines.append(
        f"case {final_state}:\n"
        f"              // Done\n"
        f"              break;"
    )

    update_state_machine = "\n\n            ".join(update_lines)


    # Assemble the final Java code
    code = f"""package org.firstinspires.ftc.teamcode.opModes.autonomous;
import com.pedropathing.follower.Follower;
import com.pedropathing.geometry.BezierCurve;
import com.pedropathing.geometry.BezierLine;
import com.pedropathing.geometry.Pose;
import com.pedropathing.paths.PathChain;
import com.pedropathing.util.Timer;
import com.qualcomm.robotcore.eventloop.opmode.Autonomous;
import com.qualcomm.robotcore.eventloop.opmode.LinearOpMode;

import org.firstinspires.ftc.teamcode.pedroPathing.Constants;

@Autonomous
public class {class_name} extends LinearOpMode {{
    @Override
    public void runOpMode() throws InterruptedException {{
        initialize();
        waitForStart();
        play();
        if (isStopRequested()) return;
        while (opModeIsActive()) update();
    }}
    private void setPathState(int pState) {{
        pathState = pState;
        pathTimer.resetTimer();
    }}

    private Follower follower;
    private Timer pathTimer;
    private int pathState;

    // Start Pose
    {start_pose_line}

    // Trajectory Poses
    {"\n    ".join(poses)}

    {path_vars}

    public void buildPaths() {{
        {"\n\n        ".join(build_lines)}
    }}

    public void autonomousPathUpdate() {{
        switch (pathState) {{
            {update_state_machine}
        }}
    }}

    private void initialize() {{
        pathTimer = new Timer();
        follower = Constants.createFollower(hardwareMap);
        buildPaths();
        follower.setStartingPose(startPose);
    }}

    private void play() {{
        setPathState(0);
    }}

    private void update() {{
        follower.update();
        autonomousPathUpdate();

        telemetry.addData("path state", pathState);
        telemetry.addData("x", follower.getPose().getX());
        telemetry.addData("y", follower.getPose().getY());
        telemetry.addData("heading", follower.getPose().getHeading());
        telemetry.update();
    }}
}}
"""
    return code



# ---------------- Syntax Highlighting ---------------- #

def highlight_java(text_widget):
    text_widget.tag_remove("keyword", "1.0", tk.END)
    text_widget.tag_remove("class", "1.0", tk.END)
    text_widget.tag_remove("comment", "1.0", tk.END)
    text_widget.tag_remove("string", "1.0", tk.END)

    java_keywords = r"\b(class|public|private|void|if|else|while|for|return|switch|case|new|import|package|extends|implements|static|final)\b"
    classes = r"\b(Pose|Path|PathChain|BezierLine|BezierCurve|Follower|Timer|LinearOpMode)\b"

    code = text_widget.get("1.0", tk.END)

    for match in re.finditer(java_keywords, code):
        start, end = match.span()
        text_widget.tag_add("keyword", f"1.0+{start}c", f"1.0+{end}c")

    for match in re.finditer(classes, code):
        start, end = match.span()
        text_widget.tag_add("class", f"1.0+{start}c", f"1.0+{end}c")

    for match in re.finditer(r'"[^"]*"', code):
        start, end = match.span()
        text_widget.tag_add("string", f"1.0+{start}c", f"1.0+{end}c")

    for match in re.finditer(r"//[^\n]*", code):
        start, end = match.span()
        text_widget.tag_add("comment", f"1.0+{start}c", f"1.0+{end}c")

    text_widget.tag_config("keyword", foreground="#569CD6")
    text_widget.tag_config("class", foreground="#4EC9B0")
    text_widget.tag_config("string", foreground="#CE9178")
    text_widget.tag_config("comment", foreground="#6A9955", font=("Consolas", 10, "italic"))

# ---------------- GUI ---------------- #

def select_json():
    filename = filedialog.askopenfilename(filetypes=[(".pp Files", "*.pp")])
    if filename:
        entry_json_path.delete(0, tk.END)
        entry_json_path.insert(0, filename)

def generate_code():
    json_path = entry_json_path.get()
    class_name = entry_class_name.get() or "Autonomoous"
    if not json_path:
        messagebox.showerror("Error", "Please select a .pp file first.")
        return
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        java_code = convert(data, class_name)
        text_output.delete(1.0, tk.END)
        text_output.insert(tk.END, java_code)
        highlight_java(text_output)
        messagebox.showinfo("Success", f"Java code generated for class {class_name}!")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate code:\n{e}")

def save_file():
    code = text_output.get(1.0, tk.END).strip()
    if not code:
        messagebox.showerror("Error", "No code to save. Generate first!")
        return
    filename = filedialog.asksaveasfilename(defaultextension=".java", filetypes=[("Java Files", "*.java")])
    if filename:
        with open(filename, "w") as f:
            f.write(code)
        messagebox.showinfo("Saved", f"Java file saved as:\n{filename}")

# ---------------- Tkinter UI ---------------- #

root = tk.Tk()
root.title("FTC PP → Java Converter (Pedro Pathing)")
root.geometry("1000x750")
root.configure(bg="#1e1e1e")

style = ttk.Style()
style.theme_use("clam")
style.configure("Dark.TButton",
                background="#333333",
                foreground="white",
                font=("Segoe UI", 10, "bold"),
                borderwidth=1)
style.map("Dark.TButton",
          background=[("active", "#0078D7")],
          foreground=[("active", "white")])

tk.Label(root, text="FTC PedroPathing → Java Path Converter",
         font=("Segoe UI", 18, "bold"),
         fg="white", bg="#1e1e1e").pack(pady=10)

frame_input = tk.Frame(root, bg="#1e1e1e")
frame_input.pack(pady=5)

tk.Label(frame_input, text="PedroPathing (.pp) File:", fg="white", bg="#1e1e1e").grid(row=0, column=0, sticky="e", padx=5)
entry_json_path = tk.Entry(frame_input, width=60)
entry_json_path.grid(row=0, column=1, padx=5)
ttk.Button(frame_input, text="Browse", command=select_json, style="Dark.TButton").grid(row=0, column=2, padx=5)

tk.Label(frame_input, text="Java Class Name:", fg="white", bg="#1e1e1e").grid(row=1, column=0, sticky="e", padx=5)
entry_class_name = tk.Entry(frame_input, width=20)
entry_class_name.insert(0, "Auto")
entry_class_name.grid(row=1, column=1, sticky="w", padx=5)

ttk.Button(frame_input, text="Generate Java Code", command=generate_code, style="Dark.TButton").grid(row=2, column=1, pady=10)

text_output = scrolledtext.ScrolledText(root, width=120, height=30,
                                        bg="#252526", fg="white",
                                        insertbackground="white",
                                        font=("Consolas", 10))
text_output.pack(padx=10, pady=10)

ttk.Button(root, text="💾 Save as .java", command=save_file, style="Dark.TButton").pack(pady=5)

root.mainloop()
