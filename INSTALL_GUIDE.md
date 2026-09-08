# PicSort Installation Guide for Windows

This guide will help you set up and run the PicSort application on your Windows machine.

## Prerequisites

### 1. Install Python
1.  Download Python 3.10 or newer from [python.org](https://www.python.org/downloads/).
2.  Run the installer.
3.  **IMPORTANT:** Check the box **"Add Python to PATH"** at the bottom of the installer window before clicking "Install Now".

### 2. Install Visual Studio Build Tools (Required for Face Recognition)
The face recognition feature relies on `dlib`, which needs C++ compilers to install on Windows.
1.  Download the **Visual Studio Build Tools** from [https://visualstudio.microsoft.com/visual-cpp-build-tools/](https://visualstudio.microsoft.com/visual-cpp-build-tools/).
2.  Run the installer.
3.  Select **"Desktop development with C++"**.
4.  Ensure the "MSVC v143 - VS 2022 C++ x64/x86 build tools" and "Windows 10 SDK" (or 11) are checked on the right side.
5.  Click **Install**. This may take a while.

## Installation Steps

1.  **Open Command Prompt / PowerShell** in this folder.
    *   You can do this by typing `cmd` in the folder path bar at the top of File Explorer and hitting Enter.

## Installation Steps

1.  **Open Command Prompt / PowerShell** in this folder.

2.  **Option A: Basic Installation (Recommended for Quick Start)**
    This will install the core features (Sorting & Visual Cleaner) but skips the Face Recognition to avoid complex errors.
    ```bash
    pip install -r requirements.txt
    ```

3.  **Option B: Full Installation (Includes Face Recognition)**
    **CRITICAL:** You must run this from the **"Developer Command Prompt for VS 2022"** (search for this in the Windows Start Menu), *not* the regular PowerShell/CMD.
    
    In that special prompt, navigate to this folder:
    ```cmd
    cd "C:\Users\danie\Desktop\PicSort"
    ```
    Then run:
    ```bash
    pip install cmake
    pip install -r requirements_full.txt
    ```
    *If this still fails, please stick to Option A.*

## Running the Application

Double-click the `run_picsort.bat` file included in this folder.

OR

Run via command line:
```bash
python picsort.py
```

## Troubleshooting
*   **"dlib failed to install"**: This means your system is missing the C++ Build Tools.
    *   **Solution**: Use **Option A** above. The app will work fine, just without the "People" tab.
    *   **Fix**: Install Visual Studio Build Tools (Desktop development with C++), then try Option B.
*   **"No module named tkinter"**: Tkinter checks: re-run Python installer, choose "Modify", ensure "tcl/tk and IDLE" is checked.
