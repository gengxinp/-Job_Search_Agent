import subprocess
import sys


def run():
    print("=== Starting Weekly Job Search ===")

    # Step 1: Run the existing job-search pipeline
    subprocess.run(
        [sys.executable, "src/main.py"],
        check=True
    )

    # Step 2: Send weekly email report
    print("\n=== Sending Weekly Job Report ===")

    subprocess.run(
        [
            sys.executable,
            "-c",
            "from src.email_notifier import send_weekly_report; send_weekly_report()"
        ],
        check=True
    )

    print("\n=== Weekly Job Search Complete ===")


if __name__ == "__main__":
    run()