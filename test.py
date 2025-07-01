import os
import subprocess
import sys


def generate_using_pip_freeze(output_file="requirements.txt"):
    """Generates requirements.txt using pip freeze."""
    try:
        with open(output_file, "w") as f:
            subprocess.check_call([sys.executable, "-m", "pip", "freeze"], stdout=f)
        print(f"[+] requirements.txt generated using pip freeze → {output_file}")
    except Exception as e:
        print(f"[!] Error using pip freeze: {e}")


def generate_using_pipreqs(project_path=".", output_file="requirements.txt"):
    """Generates requirements.txt using pipreqs based on used imports."""
    try:
        # Install pipreqs if not already installed
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pipreqs"])

        # Run pipreqs
        subprocess.check_call(["pipreqs", project_path, "--force", "--savepath", output_file])
        print(f"[+] requirements.txt generated using pipreqs → {output_file}")
    except Exception as e:
        print(f"[!] Error using pipreqs: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Auto-generate requirements.txt")
    parser.add_argument("--method", choices=["freeze", "pipreqs"], default="freeze", help="Generation method")
    parser.add_argument("--output", default="requirements.txt", help="Output file name")
    parser.add_argument("--path", default=".", help="Path to the project (for pipreqs only)")
    args = parser.parse_args()

    if args.method == "freeze":
        generate_using_pip_freeze(args.output)
    else:
        generate_using_pipreqs(args.path, args.output)
