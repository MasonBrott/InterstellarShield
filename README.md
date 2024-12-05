<p align="center">
    <img width="300" src="./img/interstellarshield.png" alt="InterstellarShield Icon">
</p>

<h1 align="center">InterstellarShield - Manually Invoke ClamAV Scanner for GCP Instances</h1>

InterstellarShield is a Python-based tool that allows for manual invocation of ClamAV virus scanning across multiple Google Cloud Platform (GCP) instances. It deploys, executes, and collects scan results from specified instances across multiple projects.

## Features

- Automated deployment of ClamAV scans across multiple GCP projects
- Parallel scanning of multiple instances
- IAP tunnel support for secure connections
- Automatic result collection and cleanup
- Comprehensive markdown report generation
- Configurable instance filtering

## Prerequisites

- Python 3.6+
- Google Cloud SDK (gcloud) installed and configured
- Appropriate IAM permissions for target GCP projects
- Docker running on target instances
- Python packages: markdown, reportlab, beautifulsoup4

### Optimizing IAP TCP Performance

Google [officially recommends](https://cloud.google.com/iap/docs/using-tcp-forwarding#increasing_the_tcp_upload_bandwidth) installing NumPy on the machine where gcloud CLI is installed to improve upload bandwidth when using IAP TCP forwarding:

For Linux:
```bash
$(gcloud info --format="value(basic.python_location)") -m pip install numpy
export CLOUDSDK_PYTHON_SITEPACKAGES=1
```

For Windows (PowerShell):
```powershell
start (gcloud info --format="value(basic.python_location)") "-m pip install numpy"
$env:CLOUDSDK_PYTHON_SITEPACKAGES="1"
```

For permanent configuration on Linux, add the export command to your `.bashrc` file.

[Learn more about IAP TCP bandwidth optimization](https://cloud.google.com/iap/docs/using-tcp-forwarding#increasing_the_tcp_upload_bandwidth)

## Installation

1. Clone this repository:
```bash
git clone https://github.com/atx-defense/InterstellarShield.git
cd InterstellarShield
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

4. Make the script executable:
```bash
chmod +x ishield.py
```

## Configuration

Edit the following variables in `ishield.py` to match your environment:
```python
PROJECTS = ['project-1', 'project-2', 'project-3']
INSTANCE_FILTERS = ['instance-1', 'instance-2', 'instance-3'] # Can be wildcarded
```

## Usage

Run the script:
```bash
python3 ishield.py
```

The script will:
1. Deploy ClamAV scanner to matching instances
2. Execute scans in parallel
3. Monitor scan progress
4. Collect results
5. Generate comprehensive markdown and PDF reports

## Scan Results

Results are stored in the current working directory under:
- Individual scan logs: `./clamav-scripts/results/<project-id>/<instance-name>/`
- Summary reports: 
  - Markdown: `./clamav-scripts/InterstellarShield_Scan_Report_<timestamp>.md`
  - PDF: `./clamav-scripts/InterstellarShield_Scan_Report_<timestamp>.pdf`

The PDF report features:
- Dark mode theme for better readability
- Highlighted malware detections in red
- Organized sections by instance
- Direct links to detailed scan logs

## Excluded Directories

By default, the following directories are excluded from scanning:
- `/proc`
- `/sys`
- `/dev`
- `/var/cache`
- `/var/lib/docker`
- `/var/lib/containerd`
- `/run`
- `/boot`

## Limitations

- Maximum file size for scanning: 100MB
- Maximum scan size: 100MB
- Log files (*.log) and gzip files (*.gz) are excluded

## Security Considerations

- Uses IAP tunneling for secure connections
- Requires appropriate GCP IAM permissions
- Runs ClamAV in an isolated Docker container
- Automatically cleans up after scan completion
