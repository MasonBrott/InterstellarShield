#!/usr/bin/env python3
import subprocess
import json
from typing import List, Dict
import time
import os
from pathlib import Path
from reportgen import convert_markdown_to_pdf

# Projects and Instance names to scan
# REPLACE THESE VALUES WITH YOUR PROJECT NAMES AND INSTANCE FILTER PATTERNS
PROJECTS = ['<PROJECT_NAME_1>', '<PROJECT_NAME_2>', '<PROJECT_NAME_3>'] # Replace me!
INSTANCE_FILTERS = ['<INSTANCE_FILTER_PATTERN_1>','<INSTANCE_FILTER_PATTERN_2>'] # Replace me!

# Use the current working directory for script and results
SCRIPT_DIR = Path(os.getcwd()) / "clamav-scripts"
SCRIPT_DIR.mkdir(exist_ok=True)

# Create the scan script content
SCAN_SCRIPT_CONTENT = '''#!/bin/bash
TARGET_HOME="$1"

# Create logs directory with proper ownership
sudo mkdir -p "$TARGET_HOME/clamav-logs"
sudo docker run --rm \\
    --name clamav-manual \\
    -v /:/host:ro \\
    -v "$TARGET_HOME/clamav-logs":/logs \\
    clamav/clamav:latest \\
    clamscan --stdout -r /host \\
        --max-filesize=100M \\
        --max-scansize=100M \\
        --exclude-dir="^/host/proc" \\
        --exclude-dir="^/host/sys" \\
        --exclude-dir="^/host/dev" \\
        --exclude-dir="^/host/usr/src/linux-gcp-fips-headers-5.15.0-1071" \\
        --exclude-dir="^/host/var/cache" \\
        --exclude-dir="^/host/var/lib/docker" \\
        --exclude-dir="^/host/var/lib/containerd" \\
        --exclude-dir="^/host/run" \\
        --exclude-dir="^/host/tmp" \\
        --exclude-dir="^/host/var/tmp" \\
        --exclude-dir="^/host/boot" \\
        --exclude="\\.log$" \\
        --exclude="\\.gz$" \\
        > "$TARGET_HOME/clamav-logs/scan.log" 2>&1

# Extract important findings and fix permissions
sudo grep -E "FOUND|Infected files" "$TARGET_HOME/clamav-logs/scan.log" > "$TARGET_HOME/clamav-logs/findings.log"
sudo chown -R $(stat -c '%U:%G' "$TARGET_HOME") "$TARGET_HOME/clamav-logs/"
'''

# Write the script locally
SCAN_SCRIPT_PATH = SCRIPT_DIR / "run_clamav_scan.sh"
with open(SCAN_SCRIPT_PATH, "w") as f:
    f.write(SCAN_SCRIPT_CONTENT)
os.chmod(SCAN_SCRIPT_PATH, 0o755)  # Make executable

def get_projects() -> List[str]:
    """Get list of hardcoded GCP projects."""
    return PROJECTS

def get_instances(project_id: str) -> List[Dict]:
    """Get list of compute instances in a project."""
    try:
        result = subprocess.run(
            ['gcloud', 'compute', 'instances', 'list',
             f'--project={project_id}',
             '--format=json'],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error getting instances for project {project_id}: {e}")
        return []

def deploy_and_start_scan(project_id: str, zone: str, instance: str) -> None:
    print(f"\nDeploying ClamAV scan to {instance} (Project: {project_id}, Zone: {zone})")
    try:
        # Copy script to instance
        scp_command = [
            'gcloud', 'compute', 'scp',
            f'--project={project_id}',
            f'--zone={zone}',
            '--quiet',
            '--tunnel-through-iap',
            str(SCAN_SCRIPT_PATH),
            f'{instance}:~/run_clamav_scan.sh'
        ]
        subprocess.run(scp_command, check=True)

        # First SSH command: Make script executable
        chmod_command = [
            'gcloud', 'compute', 'ssh',
            f'--project={project_id}',
            f'--zone={zone}',
            instance,
            '--command', 'chmod +x ~/run_clamav_scan.sh',
            '--quiet',
            '--tunnel-through-iap'
        ]
        subprocess.run(chmod_command, check=True)

        # Second SSH command: Start the scan in background
        start_scan_command = [
            'gcloud', 'compute', 'ssh',
            f'--project={project_id}',
            f'--zone={zone}',
            instance,
            '--command', 'export TARGET_HOME=$HOME && nohup sudo -E bash ~/run_clamav_scan.sh "$TARGET_HOME" </dev/null >/dev/null 2>&1',
            '--quiet',
            '--tunnel-through-iap'
        ]
        process = subprocess.Popen(
            start_scan_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Wait a short time for immediate errors
        try:
            stdout, stderr = process.communicate(timeout=10)
            if process.returncode == 0:
                print(f"Scan started successfully on {instance}")
            else:
                print(f"Warning: Scan start may have failed on {instance}")
                print(f"stderr: {stderr}")
        except subprocess.TimeoutExpired:
            # If it times out, assume the scan started successfully
            print(f"Scan appears to be running on {instance}")
            process.kill()

    except subprocess.CalledProcessError as e:
        print(f"Error during deployment: {e}")
        print(f"Error output: {e.stderr if hasattr(e, 'stderr') else 'No error output available'}")

def retrieve_scan_results(project_id: str, zone: str, instance: str) -> None:
    """Retrieve scan results from the instance."""
    print(f"\nRetrieving results from {instance} (Project: {project_id}, Zone: {zone})")
    try:
        # Create local results directory
        results_dir = SCRIPT_DIR / "results" / project_id / instance
        results_dir.mkdir(parents=True, exist_ok=True)

        # Copy results back
        scp_results_command = [
            'gcloud', 'compute', 'scp',
            f'--project={project_id}',
            f'--zone={zone}',
            '--quiet',
            '--tunnel-through-iap',
            f'{instance}:~/clamav-logs/*.log',
            str(results_dir)
        ]
        subprocess.run(scp_results_command, check=True)

        # Print findings
        findings_file = results_dir / "findings.log"
        if findings_file.exists():
            print("\nScan Findings:")
            print(findings_file.read_text())
        else:
            print("\nNo findings file found. Scan might still be running.")

    except subprocess.CalledProcessError as e:
        print(f"Error retrieving results: {e}")
        print(f"Error output: {e.stderr if hasattr(e, 'stderr') else 'No error output available'}")

def cleanup_instance(project_id: str, zone: str, instance: str) -> None:
    """Clean up all artifacts from the instance after scan completion."""
    print(f"\nCleaning up {instance} (Project: {project_id}, Zone: {zone})")
    cleanup_command = [
        'gcloud', 'compute', 'ssh',
        f'--project={project_id}',
        f'--zone={zone}',
        instance,
        '--command',
        'sudo rm -rf ~/clamav-logs ~/run_clamav_scan.sh',
        '--quiet',
        '--tunnel-through-iap'
    ]
    try:
        subprocess.run(cleanup_command, check=True)
        print(f"Cleanup completed on {instance}")
    except subprocess.CalledProcessError as e:
        print(f"Error during cleanup: {e}")
        print(f"Error output: {e.stderr if hasattr(e, 'stderr') else 'No error output available'}")

def check_scan_status(project_id: str, zone: str, instance: str) -> bool:
    """Check if the ClamAV scan is still running on the instance.
    Returns True if scan is complete, False if still running."""
    try:
        check_command = [
            'gcloud', 'compute', 'ssh',
            f'--project={project_id}',
            f'--zone={zone}',
            instance,
            '--command', 'sudo docker ps | grep "clamav-manual" || true',
            '--quiet',
            '--tunnel-through-iap'
        ]
        result = subprocess.run(check_command, capture_output=True, text=True, check=True)
        return len(result.stdout.strip()) == 0  # True if container not found (scan complete)
    except subprocess.CalledProcessError as e:
        print(f"Error checking scan status on {instance}: {e}")
        return True  # Assume complete on error to avoid infinite loops
    
def generate_report(instances_checked: List[tuple]) -> None:
    """Generate a comprehensive markdown report of all scan results."""
    report_time = time.strftime("%Y-%m-%d_%H-%M-%S")
    report_path = SCRIPT_DIR / f"InterstellarShield_Scan_Report_{report_time}.md"
    
    print(f"\nGenerating report at: {report_path}")
    
    with open(report_path, "w") as report:
        # Add InterstellarShield logo
        report.write("<p align=\"center\">\n")
        report.write("  <img width=\"300\" src=\"./img/interstellarshield.png\" alt=\"InterstellarShield Icon\">\n")
        report.write("</p>\n\n")

        report.write("<h1 align=\"center\">Generated by InterstellarShield</h1>\n\n")
        
        # Write header
        report.write("## Manual ClamAV Scan Results Report\n\n")
        report.write(f"Report generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Summary section
        report.write("### Summary\n\n")
        report.write(f"- Total projects scanned: {len(set(inst[0] for inst in instances_checked))}\n")
        report.write(f"- Total instances scanned: {len(instances_checked)}\n\n")
        
        # Results by instance
        report.write("### Detailed Results\n\n")
        
        for project_id, zone, instance in instances_checked:
            report.write(f"#### Instance: {instance}\n")
            report.write(f"- **Project**: {project_id}\n")
            report.write(f"- **Zone**: {zone}\n")
            
            # Check for scan results
            results_dir = SCRIPT_DIR / "results" / project_id / instance
            findings_file = results_dir / "findings.log"
            scan_log_file = results_dir / "scan.log"
            
            if findings_file.exists():
                report.write("\n**Findings:**\n")
                findings = findings_file.read_text().strip()
                if findings:
                    report.write(findings + "\n")
                    # Add the log path information when malware is detected
                    report.write(f"\nPlease review the full logs for more details: ./results/{project_id}/{instance}/scan.log\n")
                else:
                    report.write("No malware detected.\n")
            else:
                report.write("\n**Status**: No results file found. Scan may have failed or still be running.\n")
            
            report.write("\n---\n\n")
    
    print(f"Report generated successfully at: {report_path}")

    # Convert the markdown report to PDF
    pdf_path = SCRIPT_DIR / f"InterstellarShield_Scan_Report_{report_time}.pdf"
    convert_markdown_to_pdf(str(report_path), str(pdf_path))
    print(f"PDF report generated successfully at: {pdf_path}")

def main():
    projects = get_projects()
    print(f"Processing {len(projects)} projects...")

    # Track instances for result retrieval
    instances_to_check = []

    # First phase: Deploy and start scans
    for project_id in projects:
        print(f"\nChecking project: {project_id}")
        instances = get_instances(project_id)
        
        if not instances:
            continue

        filtered_instances = []
        for instance in instances:
            if any(filter_pattern.replace('*', '') in instance['name'] 
                  for filter_pattern in INSTANCE_FILTERS):
                filtered_instances.append(instance)

        for instance in filtered_instances:
            deploy_and_start_scan(
                project_id,
                instance['zone'].split('/')[-1],
                instance['name']
            )
            instances_to_check.append((
                project_id,
                instance['zone'].split('/')[-1],
                instance['name']
            ))

    # Second phase: Check status and retrieve results
    instances_pending = instances_to_check.copy()
    check_interval = 300  # 5 minutes in seconds

    while instances_pending:
        print(f"\nChecking scan status for {len(instances_pending)} instances...")
        still_running = []

        for project_id, zone, instance in instances_pending:
            if check_scan_status(project_id, zone, instance):
                print(f"Scan complete on {instance}, retrieving results...")
                retrieve_scan_results(project_id, zone, instance)
                cleanup_instance(project_id, zone, instance)
            else:
                print(f"Scan still running on {instance}")
                still_running.append((project_id, zone, instance))

        instances_pending = still_running
        if instances_pending:
            print(f"\nWaiting {check_interval/60} minutes before next check...")
            time.sleep(check_interval)
    
    # Generate the final report
    generate_report(instances_to_check)

if __name__ == '__main__':
    main()
    
