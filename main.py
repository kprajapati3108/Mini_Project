# Convenience runner if you want a single entrypoint
import subprocess, sys

steps = [
    ["python", "create_infrastructure.py"],
    ["python", "setup_monitoring.py"]
]

for cmd in steps:
    print("\n>>> Running:", " ".join(cmd))
    rc = subprocess.call(cmd)
    if rc != 0:
        sys.exit(rc)

print("\nAll set. You can optionally run: python scale_infrastructure.py")
print("When finished, run: python destroy_infrastructure.py")
