#!/usr/bin/env python3

import argparse
import subprocess
import os
import sys
import shutil
from typing import List, Tuple, Optional, Set, Dict

# 2. External Execution Program Dependencies (Tools)
#    These are executable programs that must be installed on the system's PATH.
#    - clang-format
#    - autopep8 (Replaces yapf for Python formatting)
#    - shfmt
#    - prettier
#    - buildifier

# Mapping file types to external formatter tools
TOOL_MAP: Dict[str, str] = {
    "cpp":       "clang-format",
    "python":    "autopep8",
    "shell":     "shfmt",
    "markdown":  "prettier",
    "bazel":     "buildifier"
}

# Mapping file extensions/basenames to internal format types
EXT_MAP: Dict[str, str] = {
    ".cc": "cpp", ".cpp": "cpp", ".c": "cpp", ".h": "cpp", ".hpp": "cpp", ".proto": "cpp",
    ".py": "python",
    ".sh": "shell",
    ".md": "markdown",
    ".bazel": "bazel", "BUILD": "bazel", "WORKSPACE": "bazel"
}

DEBIAN_INSTALL_COMMANDS: Dict[str, str] = {
    "clang-format": "sudo apt update && sudo apt install clang-format",
    "autopep8": (
        "# Install Python and pip if not already present:\n"
        "sudo apt update && sudo apt install python3 python3-pip\n"
        "# Then install autopep8 using pip:\n"
        "pip install autopep8\n"
        "# Or using python -m pip to ensure it's installed for the correct Python version:\n"
        "# python3 -m pip install autopep8"
    ),
    "shfmt": "sudo apt update && sudo apt install shfmt",
    "prettier": (
        "# Install Node.js and npm if not already present:\n"
        "sudo apt update && sudo apt install nodejs npm\n"
        "# Then install prettier globally using npm:\n"
        "sudo npm install -g prettier"
    ),
    "buildifier": (
        "# buildifier usually requires manual download or a specific repository.\n"
        "# Please download the appropriate binary for your system (e.g., buildifier-linux-amd64) from the releases page:\n"
        "https://github.com/bazelbuild/buildtools/releases\n"
        "# Then make the downloaded binary executable and move it to a directory that is in your system's PATH (e.g., /usr/local/bin):\n"
        "# chmod +x /path/to/downloaded/buildifier-binary\n"
        "# sudo mv /path/to/downloaded/buildifier-binary /usr/local/bin/buildifier"
    ),
}

def is_debian_ubuntu() -> bool:
    """
    Checks if the operating system is Debian or Ubuntu by reading /etc/os-release.
    Returns True if it's Debian, Ubuntu, or an OS based on them.
    """
    if sys.platform != 'linux':
        return False
    try:
        with open('/etc/os-release', 'r') as f:
            content = f.read()
        ids = {}
        for line in content.splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                ids[key] = value.strip('"')
        # Check ID itself or ID_LIKE (for derivatives like Mint, Pop!_OS, etc.)
        if 'ID' in ids and (ids['ID'] == 'debian' or ids['ID'] == 'ubuntu'):
            return True
        if 'ID_LIKE' in ids and ('debian' in ids['ID_LIKE'].split() or 'ubuntu' in ids['ID_LIKE'].split()):
             return True
    except FileNotFoundError:
        # This file is standard on most modern Linux, but absence means it's not standard Linux or very old
        pass
    except Exception as e:
        print(f"[WARN] Could not read /etc/os-release: {e}", file=sys.stderr)

    return False

def check_tools() -> None:
    """
    Checks if all required external formatting tools are installed.
    Provides specific installation commands for Debian/Ubuntu if missing tools are detected.
    """
    missing: List[str] = []
    # Use a set to store missing *tool names* to avoid printing duplicate instructions
    missing_tool_names: Set[str] = set()

    for fmt_type, tool in TOOL_MAP.items():
        if not shutil.which(tool):
            missing.append(f"{fmt_type} ({tool})")
            missing_tool_names.add(tool) # Add the tool name itself

    if missing:
        print("[ERROR] Missing required tools:")
        for m in missing:
            print(f"  - {m}") # Print the original "type (tool)" format

        # Check if we can provide specific instructions
        if is_debian_ubuntu():
            print("\nInstructions for Debian/Ubuntu:")
            # Iterate through the unique missing tool names and print their installation commands
            for tool_name in missing_tool_names:
                 if tool_name in DEBIAN_INSTALL_COMMANDS:
                     print(f"\nTo install '{tool_name}':")
                     print("```bash") # Use markdown code block for clarity
                     print(DEBIAN_INSTALL_COMMANDS[tool_name])
                     print("```")
                 else:
                     # Fallback for tools that might not be in our specific map
                     print(f"\nInstallation command for '{tool_name}' is not explicitly listed for Debian/Ubuntu. Please search online.")
        else:
            # Generic message for other operating systems or if detection failed
            print("\nPlease install them before running this script.")
            print("Refer to the tools' official documentation for installation instructions specific to your operating system:")
            # List the missing tool names again for clarity
            for tool_name in missing_tool_names:
                 print(f"  - {tool_name}")

        sys.exit(1)

def detect_format_type(filepath: str) -> Optional[str]:
    """
    Detects the format type (e.g., 'cpp', 'python') based on the file extension or basename.

    Args:
        filepath: The path to the file.

    Returns:
        The detected format type string, or None if unknown.
    """
    base: str = os.path.basename(filepath)
    _, ext = os.path.splitext(base)
    # Check for exact basename matches first (like 'BUILD', 'WORKSPACE')
    if base in EXT_MAP:
        return EXT_MAP[base]
    # Then check for extension matches
    return EXT_MAP.get(ext)

def build_command(fmt_type: str, target: str, dry_run: bool, check: bool) -> List[str]:
    """
    Builds the command line arguments for the specific formatter tool.

    Args:
        fmt_type: The internal format type string.
        target: The path to the file to format.
        dry_run: If True, build command for dry run.
        check: If True, build command for check mode (implies dry_run behavior for some tools).

    Returns:
        A list of strings representing the command and its arguments.
    """
    tool: str = TOOL_MAP[fmt_type]
    cmd: List[str] = [tool]

    # Industry practice often makes 'check' mode behave like a dry run + status check
    is_test_mode = dry_run or check

    if fmt_type == "cpp":
        cmd.append("--dry-run" if is_test_mode else "-i")
        cmd.append(target)
    elif fmt_type == "python":
        # autopep8 options: --in-place for write, --diff for dry-run, --exit-code for check
        if check:
            cmd.append("--exit-code") # Use --exit-code for check mode (0=ok, 1=needs changes, 2=error)
        elif dry_run:
            cmd.append("--diff") # Use --diff for dry-run (shows changes)
        else:
            cmd.append("--in-place") # Use --in-place for write mode (modifies file)
        cmd.append(target) # File path goes after options
    elif fmt_type == "shell":
        cmd.append("--diff" if is_test_mode else "-w")
        cmd.append(target)
    elif fmt_type == "markdown":
        # prettier --check also performs a dry-run like check
        cmd.append("--check" if is_test_mode else "--write")
        cmd.append(target)
    elif fmt_type == "bazel":
        # buildifier uses -mode=check for checking
        cmd.append("-mode=check" if is_test_mode else "-mode=fix")
        cmd.append(target)
    else:
        # Should not happen given TOOL_MAP, but as a safeguard
        print(f"[WARN] Unknown format type '{fmt_type}'. Cannot build command for {target}.")
        return []

    return cmd

def run_tool(fmt_type: str, target: str, dry_run: bool, check: bool) -> Tuple[bool, str]:
    """
    Runs the specific formatter tool on the target file.

    Args:
        fmt_type: The internal format type string.
        target: The path to the file to format.
        dry_run: If True, run in dry-run mode.
        check: If True, run in check mode.

    Returns:
        A tuple: (success: bool, message: str). Success is False if the tool exited with a non-zero
        status in check mode (meaning formatting needed), or if any subprocess error occurred.
    """
    cmd = build_command(fmt_type, target, dry_run, check)
    if not cmd: # Command building failed
        return False, f"[ERROR] Failed to build command for {target}"

    # print(f"Running: {' '.join(cmd)}") # Uncomment for debugging commands

    try:
        # Using capture_output=True to get stdout/stderr for better error messages
        # text=True decodes stdout/stderr as text
        # For autopep8 --exit-code, a non-zero exit code means changes are needed or error occurred.
        # check=True handles non-zero exit codes by raising CalledProcessError.
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # If check=True and subprocess.run with check=True did NOT raise an exception,
        # it means the tool exited with status 0.
        # For autopep8 --exit-code, status 0 means "no changes needed".
        if check:
            return True, f"[OK] {target}" # autopep8 --exit-code 0 means already formatted
        elif dry_run:
             return True, f"[OK] {target} (dry-run)"
        else: # write mode (--in-place)
            return True, f"[OK] {target}"

    except FileNotFoundError:
         tool = TOOL_MAP.get(fmt_type, 'unknown_tool')
         return False, f"[ERROR] Tool not found for {fmt_type} ({tool}): {target}"
    except subprocess.CalledProcessError as e:
        # The tool exited with a non-zero code.
        # In check mode (--exit-code), this means changes are needed (exit 1) or error (exit 2).
        # In other modes, this means a general tool error.
        error_output = (e.stdout + e.stderr).strip() or f"Exit code {e.returncode}"

        if check:
             # In check mode, non-zero exit means file needs formatting (exit 1) or error (exit 2).
             # Treat both as failure for the purpose of the check.
             status_msg = "Needs formatting" if e.returncode == 1 else "Check failed"
             return False, f"[FAIL] {status_msg}: {target}\n{error_output}"
        else:
             # In write/dry-run mode, non-zero exit indicates an error during formatting.
             return False, f"[FAIL] Formatting error: {target}\n{error_output}"
    except Exception as e:
        # Catch any other unexpected exceptions
        return False, f"[FAIL] Unexpected error processing {target}: {type(e).__name__}: {e}"


def find_files_to_process(paths: List[str], selected_types: Set[str]) -> List[Tuple[str, str]]:
    """
    Finds all supported files within the given paths that match selected types.

    Args:
        paths: A list of file and/or directory paths.
        selected_types: A set of format types to include.

    Returns:
        A list of tuples, where each tuple is (fmt_type, filepath).
    """
    files_to_process: List[Tuple[str, str]] = []
    for path in paths:
        if not os.path.exists(path):
            print(f"[WARN] Ignored: {path} does not exist.")
            continue

        if os.path.isfile(path):
            fmt_type = detect_format_type(path)
            if fmt_type and (not selected_types or fmt_type in selected_types):
                files_to_process.append((fmt_type, path))
        elif os.path.isdir(path):
            # Walk through the directory
            for root, _, files in os.walk(path):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    fmt_type = detect_format_type(fpath)
                    # Check if type is detected and is in selected types (or all selected)
                    if fmt_type and (not selected_types or fmt_type in selected_types):
                         # Add the file path to the list
                        files_to_process.append((fmt_type, fpath))
        else:
             print(f"[WARN] Ignored: {path} is not a file or directory.")

    return files_to_process

def parse_args() -> argparse.Namespace:
    """Parses command line arguments."""
    parser = argparse.ArgumentParser(
        description="Apollo code formatter CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    group = parser.add_argument_group("Format options")
    group.add_argument("-p", "--python", action="store_true", help="Format Python files using autopep8.") # Updated help text
    group.add_argument("-c", "--cpp", action="store_true", help="Format C/C++ files.")
    group.add_argument("-b", "--bazel", action="store_true", help="Format Bazel files.")
    group.add_argument("-s", "--shell", action="store_true", help="Format Shell scripts.")
    group.add_argument("-m", "--markdown", action="store_true", help="Format Markdown files.")
    group.add_argument("-a", "--all", action="store_true", help="Format all supported file types.")

    parser.add_argument("--dry-run", action="store_true", help="List files that would be formatted (shows diff for Python, Markdown, Shell).") # Updated help text slightly
    parser.add_argument("--check", action="store_true", help="Check if files are formatted correctly. Exits with non-zero status if any file needs formatting.")
    parser.add_argument(
        "paths",
        metavar="PATH",
        nargs="+",
        help="One or more files or directories to format."
    )

    args = parser.parse_args()

    # Ensure --check and --dry-run are not used together
    if args.check and args.dry_run:
         parser.error("--check and --dry-run cannot be used together.")

    return args

def main() -> None:
    """Main entry point of the formatter script."""
    args = parse_args()

    # Check for required tools first
    check_tools()

    # Determine selected types
    selected: Set[str] = set()
    if args.all or not any([args.python, args.cpp, args.bazel, args.shell, args.markdown]):
        selected = set(TOOL_MAP.keys()) # Select all supported types if no specific flag is given or --all is used
    else:
        if args.python: selected.add("python")
        if args.cpp: selected.add("cpp")
        if args.bazel: selected.add("bazel")
        if args.shell: selected.add("shell")
        if args.markdown: selected.add("markdown")

    # Find files to process
    files_to_process: List[Tuple[str, str]] = find_files_to_process(args.paths, selected)

    if not files_to_process:
        print("No supported files found for formatting or check in the provided paths.")
        sys.exit(0)

    print(f"Processing {len(files_to_process)} file(s)...")

    failed_files: List[str] = []
    # Process each file
    for fmt_type, filepath in files_to_process:
        success, message = run_tool(fmt_type, filepath, args.dry_run, args.check)
        print(message) # Print the status message for each file

        # In check mode, collect failures to report all at the end
        if args.check and not success:
            failed_files.append(filepath)

    # Final reporting for --check mode
    if args.check:
        if failed_files:
            print("\n[SUMMARY] The following files need formatting:")
            for fail in failed_files:
                print(f"  - {fail}")
            sys.exit(1) # Exit with non-zero code to indicate failure
        else:
            print("\n[SUMMARY] All checked files are correctly formatted.")
            sys.exit(0) # Exit with zero code to indicate success
    else:
         # For dry-run or write mode, just confirm completion
         print("\n[SUMMARY] Formatting process completed.")
         sys.exit(0) # Always exit with 0 unless check mode failed


if __name__ == "__main__":
    main()
