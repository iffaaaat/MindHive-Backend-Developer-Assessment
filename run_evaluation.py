import subprocess
import sys


def run(module):
    subprocess.run(
        [sys.executable, "-m", module],
        check=True,
    )


def main():
    run("evaluation.evaluate")
    print()
    run("evaluation.noise_analysis")


if __name__ == "__main__":
    main()